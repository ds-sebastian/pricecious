"""Price checks: claiming items, capture, extraction, persistence, alerts, and the scheduler loop."""

import asyncio
import hashlib
import json
import logging
import os
import random
import re
import time
from collections.abc import Coroutine, Iterable
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai, analytics, database, forecast, notify, scraper
from app import settings as app_settings
from app.database import utcnow
from app.models import Item, PriceHistory
from app.settings import AppSettings

logger = logging.getLogger(__name__)

SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "screenshots"))
MAX_CONCURRENT_CHECKS = 5
MIN_INTERVAL_MINUTES = 5
CLAIM_TIMEOUT = timedelta(hours=1)
CHECK_ALL_SKIPS_RECENT = timedelta(minutes=5)
MAX_JITTER_SECONDS = 30
HEARTBEAT_SECONDS = 60
# Even an unchanged page gets a real AI check this often, as a safety net.
AI_RECHECK = timedelta(hours=24)
# A big jump reported with middling confidence is applied but flagged for review.
UNCERTAIN_CHANGE_PERCENT = 20
UNCERTAIN_CONFIDENCE = 0.7

PRICE_TEXT = re.compile(r"[$€£¥₹₩]\s?\d[\d.,]*|\d[\d.,]*\s?(?:[$€£¥₹₩]|\b(?:USD|EUR|GBP|CAD|AUD)\b)")
STOCK_PHRASES = (
    "add to cart",
    "add to basket",
    "add to bag",
    "buy now",
    "in stock",
    "out of stock",
    "sold out",
    "unavailable",
    "notify me",
    "pre-order",
)

_slots = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)
_tasks: set[asyncio.Task] = set()


def screenshot_file(item_id: int) -> Path:
    return SCREENSHOT_DIR / f"item_{item_id}.png"


def interval_minutes(item: Item, default: int) -> int:
    """Item interval, else its notification profile's, else the global default."""
    profile_interval = item.notification_profile.check_interval_minutes if item.notification_profile else None
    return max(item.check_interval_minutes or profile_interval or default, MIN_INTERVAL_MINUTES)


async def claim(
    db: AsyncSession,
    item_ids: Iterable[int] | None = None,
    *,
    active_only: bool = True,
    checked_before: datetime | None = None,
) -> list[int]:
    """Atomically mark idle (or stale) items as refreshing and return the IDs claimed."""
    now = utcnow()
    query = update(Item).where(
        or_(
            Item.is_refreshing.is_(False),
            Item.refresh_started_at.is_(None),
            Item.refresh_started_at < now - CLAIM_TIMEOUT,
        )
    )
    if active_only:
        query = query.where(Item.is_active.is_(True))
    if item_ids is not None:
        query = query.where(Item.id.in_(list(item_ids)))
    if checked_before is not None:
        query = query.where(or_(Item.last_checked.is_(None), Item.last_checked < checked_before))
    result = await db.execute(query.values(is_refreshing=True, refresh_started_at=now).returning(Item.id))
    claimed = list(result.scalars())
    await db.commit()
    return claimed


async def claim_due(db: AsyncSession, settings: AppSettings) -> list[int]:
    now = utcnow()
    items = (await db.scalars(select(Item).where(Item.is_active.is_(True)))).all()
    due = [
        item.id
        for item in items
        if item.last_checked is None
        or now - item.last_checked >= timedelta(minutes=interval_minutes(item, settings.refresh_interval_minutes))
    ]
    return await claim(db, due) if due else []


async def release_all_claims() -> None:
    """Nothing can be running at startup, so clear claims left behind by a crash or restart."""
    async with database.SessionLocal() as db:
        await db.execute(
            update(Item).where(Item.is_refreshing.is_(True)).values(is_refreshing=False, refresh_started_at=None)
        )
        await db.commit()


def spawn(coro: Coroutine) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return task


def enqueue(item_ids: Iterable[int], *, jitter: bool = False, force_ai: bool = False) -> None:
    for item_id in item_ids:
        spawn(check_item(item_id, jitter=jitter, force_ai=force_ai))


async def shutdown() -> None:
    for task in list(_tasks):
        task.cancel()
    await asyncio.gather(*_tasks, return_exceptions=True)


async def check_item(item_id: int, *, jitter: bool = False, force_ai: bool = False) -> None:
    """Run a check for an already-claimed item. The claim is released however it ends.

    force_ai asks the model even if the page looks unchanged, as someone clicking "Check now" expects.
    """
    try:
        if jitter:  # spread scheduled checks out instead of hitting sites in bursts
            await asyncio.sleep(random.uniform(0, MAX_JITTER_SECONDS))
        async with _slots:
            await _check(item_id, force_ai)
    except asyncio.CancelledError:
        await asyncio.shield(_release(item_id))
        raise
    except Exception:
        logger.exception(f"Check crashed for item {item_id}")
        await _release(item_id)


async def _check(item_id: int, force_ai: bool = False) -> None:
    async with database.SessionLocal() as db:
        item = await db.get(Item, item_id)
        settings = await app_settings.load(db)
    if item is None:
        return
    logger.info(f"Checking item {item_id}: {item.name}")

    try:
        capture = await scraper.capture(
            item.url,
            selector=item.selector,
            scroll_pixels=settings.smart_scroll_pixels if settings.smart_scroll_enabled else 0,
            timeout_ms=settings.scraper_timeout,
        )
    except Exception as exc:
        if isinstance(exc, scraper.ScrapeError) and exc.capture:
            await _save_screenshot(item_id, exc.capture.screenshot)
        await _record_failure(item_id, describe(exc), "scrape_failed", settings)
        return
    await _save_screenshot(item_id, capture.screenshot)

    fingerprint = page_fingerprint(capture)
    if not force_ai and can_skip_ai(item, capture, fingerprint, settings):
        await _record_skip(item_id)
        return

    try:
        extraction = await ai.extract(
            capture.screenshot,
            settings,
            url=item.url,
            page_text=capture.text[: settings.text_context_length] if settings.text_context_enabled else None,
            custom_prompt=item.custom_prompt,
            last_price=item.current_price,
        )
    except Exception as exc:
        await _record_failure(item_id, f"AI extraction failed: {describe(exc)}", "ai_failed", settings, ai_call=True)
        return

    async with database.SessionLocal() as db:
        item = await db.get(Item, item_id)
        if item is None:  # deleted while it was being checked
            screenshot_file(item_id).unlink(missing_ok=True)
            return
        old_price, old_stock = item.current_price, item.in_stock
        previous_low = await analytics.previous_low(db, item_id, settings.confidence_threshold_price)
        if history := apply_extraction(item, extraction, settings):
            db.add(history)
        if not item.name:
            item.name = scraper.product_name(capture.title)
        item.page_fingerprint, item.ai_checked_at = fingerprint, utcnow()
        item.ai_calls += 1
        item.is_refreshing, item.refresh_started_at = False, None
        await db.commit()

    for title, body in notify.alerts(item, old_price, old_stock, previous_low):
        await notify.send(item.notification_profile.apprise_url, title, body)


def page_fingerprint(capture: scraper.Capture) -> str:
    """Hash of the prices and stock wording on the page: what a check cares about, ignoring everything else."""
    prices = sorted({re.sub(r"\s", "", match) for match in PRICE_TEXT.findall(capture.selector_text or capture.text)})
    lowered = capture.text.lower()
    stock = [phrase for phrase in STOCK_PHRASES if phrase in lowered]
    return hashlib.sha256(json.dumps([prices, stock]).encode()).hexdigest()


def can_skip_ai(item: Item, capture: scraper.Capture, fingerprint: str, settings: AppSettings) -> bool:
    """True only when the page provably still shows what the last AI check found."""
    if not settings.skip_unchanged_pages or item.page_fingerprint != fingerprint:
        return False
    if item.ai_checked_at is None or utcnow() - item.ai_checked_at >= AI_RECHECK:
        return False
    # Only repeat clean results, and only when the known price is visibly on the page (not drawn in an image).
    if item.last_error or item.current_price is None:
        return False
    shown = (ai.parse_price(match) for match in PRICE_TEXT.findall(capture.selector_text or capture.text))
    return any(price is not None and abs(price - item.current_price) < 0.005 for price in shown)


def apply_extraction(item: Item, extraction: ai.Extraction, settings: AppSettings) -> PriceHistory | None:
    """Update an item from a successful extraction and return the history row to store, if any."""
    price, price_confidence = extraction.price, extraction.price_confidence
    now = utcnow()
    item.last_checked = now
    item.consecutive_failures = 0
    item.last_error = item.error_type = None

    if price is not None and (problem := _price_problem(price, item.current_price, settings)):
        item.last_error, item.error_type = problem
        return None

    if extraction.in_stock is not None and extraction.in_stock_confidence >= settings.confidence_threshold_stock:
        item.in_stock, item.in_stock_confidence = extraction.in_stock, extraction.in_stock_confidence

    if price is None:
        if extraction.in_stock is not False:  # sold-out pages often hide the price
            item.last_error, item.error_type = "No price found on the page", "no_price"
        return None

    if not item.currency:  # detected once; after that it's the user's to change
        item.currency = extraction.currency or ai.infer_currency(item.url)

    if price_confidence < settings.confidence_threshold_price:
        item.last_error = f"Found {price:.2f} with only {price_confidence:.0%} confidence, so it wasn't applied"
        item.error_type = "low_confidence"
    else:
        old_price = item.current_price
        if (
            old_price
            and abs(price - old_price) / old_price * 100 > UNCERTAIN_CHANGE_PERCENT
            and price_confidence < UNCERTAIN_CONFIDENCE
        ):
            item.last_error = f"Large price change with only {price_confidence:.0%} confidence; please verify"
            item.error_type = "low_confidence"
        item.current_price, item.current_price_confidence = price, price_confidence

    return PriceHistory(
        item_id=item.id,
        timestamp=now,
        price=price,
        price_confidence=price_confidence,
        in_stock=extraction.in_stock,
        in_stock_confidence=extraction.in_stock_confidence,
        ai_model=settings.ai_model,
        ai_provider=settings.ai_provider,
    )


def _price_problem(price: float, old_price: float | None, settings: AppSettings) -> tuple[str, str] | None:
    low, high = settings.price_min_floor, settings.price_max_ceiling
    if not low <= price <= high:
        return f"Rejected {price:.2f}: outside the allowed range {low:g} to {high:g}", "price_out_of_bounds"
    if settings.price_outlier_threshold_enabled and old_price:
        change = (price - old_price) / old_price * 100
        limit = settings.price_outlier_threshold_percent
        if abs(change) > limit:
            message = f"Rejected {price:.2f}: a {change:+.0f}% change exceeds the {limit:g}% outlier limit"
            return message, "outlier_rejected"
    return None


async def _record_skip(item_id: int) -> None:
    logger.info(f"Item {item_id}: page unchanged, skipped the AI")
    async with database.SessionLocal() as db:
        await db.execute(
            update(Item)
            .where(Item.id == item_id)
            .values(
                last_checked=utcnow(),
                consecutive_failures=0,
                ai_skips=Item.ai_skips + 1,
                is_refreshing=False,
                refresh_started_at=None,
            )
        )
        await db.commit()


async def _record_failure(
    item_id: int, message: str, error_type: str, settings: AppSettings, *, ai_call: bool = False
) -> None:
    logger.warning(f"Check failed for item {item_id}: {message}")
    async with database.SessionLocal() as db:
        item = await db.get(Item, item_id)
        if item is None:
            return
        item.last_checked = utcnow()
        item.consecutive_failures += 1
        item.ai_calls += int(ai_call)
        item.last_error, item.error_type = message, error_type
        if item.consecutive_failures >= settings.max_consecutive_failures:
            item.is_active = False
            item.last_error = f"Paused after {item.consecutive_failures} failed checks in a row. Last error: {message}"
            item.error_type = "auto_deactivated"
        item.is_refreshing, item.refresh_started_at = False, None
        await db.commit()


async def _release(item_id: int) -> None:
    async with database.SessionLocal() as db:
        await db.execute(update(Item).where(Item.id == item_id).values(is_refreshing=False, refresh_started_at=None))
        await db.commit()


async def _save_screenshot(item_id: int, png: bytes) -> None:
    def write() -> None:
        path = screenshot_file(item_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(png)
        tmp.replace(path)  # atomic, so the UI never serves a half-written file

    await asyncio.to_thread(write)


def describe(exc: Exception) -> str:
    """First line of an exception's message, short enough to show in the UI."""
    message = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    return message[:300]


async def run_scheduler() -> None:
    """Every minute, start checks for items that are due, and refresh forecasts on their interval."""
    last_forecast = time.monotonic()
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        try:
            async with database.SessionLocal() as db:
                settings = await app_settings.load(db)
                due = await claim_due(db, settings)
            if due:
                logger.info(f"{len(due)} items due for a check")
                enqueue(due, jitter=True)
            if time.monotonic() - last_forecast >= settings.forecasting_interval_hours * 3600:
                last_forecast = time.monotonic()
                spawn(forecast.forecast_all())
        except Exception:
            logger.exception("Scheduler tick failed")
