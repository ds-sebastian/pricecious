"""Price checks: claiming items, capture, extraction, persistence, alerts, and the scheduler loop."""

import asyncio
import logging
import os
import random
import time
from collections.abc import Coroutine, Iterable
from datetime import timedelta
from pathlib import Path

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai, database, forecast, notify, scraper
from app import settings as app_settings
from app.database import utcnow
from app.models import Item, PriceHistory
from app.settings import AppSettings

logger = logging.getLogger(__name__)

SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "screenshots"))
MAX_CONCURRENT_CHECKS = 5
MIN_INTERVAL_MINUTES = 5
CLAIM_TIMEOUT = timedelta(hours=1)
MAX_JITTER_SECONDS = 30
HEARTBEAT_SECONDS = 60
# A big jump reported with middling confidence is applied but flagged for review.
UNCERTAIN_CHANGE_PERCENT = 20
UNCERTAIN_CONFIDENCE = 0.7

_slots = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)
_tasks: set[asyncio.Task] = set()


def screenshot_file(item_id: int) -> Path:
    return SCREENSHOT_DIR / f"item_{item_id}.png"


def interval_minutes(item: Item, default: int) -> int:
    """Item interval, else its notification profile's, else the global default."""
    profile_interval = item.notification_profile.check_interval_minutes if item.notification_profile else None
    return max(item.check_interval_minutes or profile_interval or default, MIN_INTERVAL_MINUTES)


async def claim(db: AsyncSession, item_ids: Iterable[int] | None = None, *, active_only: bool = True) -> list[int]:
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


def enqueue(item_ids: Iterable[int], *, jitter: bool = False) -> None:
    for item_id in item_ids:
        spawn(check_item(item_id, jitter=jitter))


async def shutdown() -> None:
    for task in list(_tasks):
        task.cancel()
    await asyncio.gather(*_tasks, return_exceptions=True)


async def check_item(item_id: int, *, jitter: bool = False) -> None:
    """Run a check for an already-claimed item. The claim is released however it ends."""
    try:
        if jitter:  # spread scheduled checks out instead of hitting sites in bursts
            await asyncio.sleep(random.uniform(0, MAX_JITTER_SECONDS))
        async with _slots:
            await _check(item_id)
    except asyncio.CancelledError:
        await asyncio.shield(_release(item_id))
        raise
    except Exception:
        logger.exception(f"Check crashed for item {item_id}")
        await _release(item_id)


async def _check(item_id: int) -> None:
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
        await _record_failure(item_id, _describe(exc), "scrape_failed", settings)
        return
    await _save_screenshot(item_id, capture.screenshot)

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
        await _record_failure(item_id, f"AI extraction failed: {_describe(exc)}", "ai_failed", settings)
        return

    async with database.SessionLocal() as db:
        item = await db.get(Item, item_id)
        if item is None:
            return
        old_price, old_stock = item.current_price, item.in_stock
        if history := apply_extraction(item, extraction, settings):
            db.add(history)
        item.is_refreshing, item.refresh_started_at = False, None
        await db.commit()

    for title, body in notify.alerts(item, old_price, old_stock):
        await notify.send(item.notification_profile.apprise_url, title, body)


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
        item.last_error, item.error_type = "No price found on the page", "no_price"
        return None

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


async def _record_failure(item_id: int, message: str, error_type: str, settings: AppSettings) -> None:
    logger.warning(f"Check failed for item {item_id}: {message}")
    async with database.SessionLocal() as db:
        item = await db.get(Item, item_id)
        if item is None:
            return
        item.last_checked = utcnow()
        item.consecutive_failures += 1
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


def _describe(exc: Exception) -> str:
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
