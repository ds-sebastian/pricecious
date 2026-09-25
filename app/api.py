import asyncio
import time
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import case, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai, analytics, checks, forecast, notify, scraper
from app import settings as app_settings
from app.database import Base, get_db, utcnow
from app.models import Item, NotificationProfile, PriceForecast, PriceHistory
from app.schemas import (
    AITest,
    AITestResult,
    Analytics,
    BulkResult,
    HistoryBulk,
    HistoryFilters,
    HistoryPage,
    HistoryQuery,
    HistoryUpdate,
    ItemIn,
    ItemOut,
    NotificationTest,
    ProfileIn,
    ProfileOut,
)
from app.urls import UnsafeURLError, validate_url_async

router = APIRouter(prefix="/api")
DB = Annotated[AsyncSession, Depends(get_db)]


async def _get[T: Base](db: AsyncSession, model: type[T], object_id: int) -> T:
    obj = await db.get(model, object_id, populate_existing=True)
    if obj is None:
        raise HTTPException(404, f"{model.__name__} {object_id} not found")
    return obj


async def _items_out(db: AsyncSession, items: list[Item]) -> list[ItemOut]:
    settings = await app_settings.load(db)
    deals = await analytics.deals(db, items, settings.confidence_threshold_price)
    return [_item_out(item, settings.refresh_interval_minutes, deals.get(item.id)) for item in items]


def _item_out(item: Item, default_interval: int, deal: str | None) -> ItemOut:
    interval = checks.interval_minutes(item, default_interval)
    screenshot = checks.screenshot_file(item.id)
    version = int(item.last_checked.timestamp()) if item.last_checked else 0
    columns = {column.key: getattr(item, column.key) for column in Item.__table__.columns}
    return ItemOut(
        **columns | {"currency": item.currency or ai.infer_currency(item.url)},
        interval=interval,
        next_check=item.last_checked + timedelta(minutes=interval) if item.last_checked else None,
        screenshot_url=f"/screenshots/{screenshot.name}?v={version}" if screenshot.exists() else None,
        deal=deal,
    )


async def _validate_item(db: AsyncSession, data: ItemIn, current_url: str | None = None) -> None:
    if data.url != current_url:
        try:
            await validate_url_async(data.url)
        except UnsafeURLError as exc:
            raise HTTPException(422, str(exc)) from None
    if data.notification_profile_id is not None:
        await _get(db, NotificationProfile, data.notification_profile_id)


# Items


@router.get("/items")
async def list_items(db: DB) -> list[ItemOut]:
    return await _items_out(db, list(await db.scalars(select(Item).order_by(Item.id))))


@router.post("/items", status_code=201)
async def create_item(data: ItemIn, db: DB) -> ItemOut:
    await _validate_item(db, data)
    item = Item(**data.model_dump())
    db.add(item)
    await db.commit()
    item = await _get(db, Item, item.id)
    return (await _items_out(db, [item]))[0]


@router.put("/items/{item_id}")
async def update_item(item_id: int, data: ItemIn, db: DB) -> ItemOut:
    item = await _get(db, Item, item_id)
    await _validate_item(db, data, current_url=item.url)
    if data.is_active and not item.is_active:  # resuming a paused item gives it a fresh start
        item.consecutive_failures = 0
        if item.error_type == "auto_deactivated":
            item.last_error = item.error_type = None
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    item.page_fingerprint = None  # edits (prompt, selector, price) deserve a fresh AI check
    await db.commit()
    item = await _get(db, Item, item_id)
    return (await _items_out(db, [item]))[0]


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(item_id: int, db: DB) -> None:
    await _get(db, Item, item_id)
    await db.execute(delete(PriceHistory).where(PriceHistory.item_id == item_id))
    await db.execute(delete(PriceForecast).where(PriceForecast.item_id == item_id))
    await db.execute(delete(Item).where(Item.id == item_id))
    await db.commit()
    checks.screenshot_file(item_id).unlink(missing_ok=True)


@router.post("/items/check-all")
async def check_all_items(db: DB) -> dict:
    """Check every active item except those checked in the last few minutes, so repeated clicks cost nothing."""
    cutoff = utcnow() - checks.CHECK_ALL_SKIPS_RECENT
    claimed = await checks.claim(db, checked_before=cutoff)
    checks.enqueue(claimed)
    recent = await db.scalar(
        select(func.count()).select_from(Item).where(Item.is_active.is_(True), Item.last_checked >= cutoff)
    )
    return {"queued": len(claimed), "recently_checked": recent}


@router.post("/items/{item_id}/check")
async def check_item(item_id: int, db: DB) -> dict:
    await _get(db, Item, item_id)
    claimed = await checks.claim(db, [item_id], active_only=False)
    checks.enqueue(claimed, force_ai=True)
    return {"queued": bool(claimed)}


@router.get("/items/{item_id}/analytics")
async def item_analytics(
    item_id: int,
    db: DB,
    days: Annotated[int | None, Query(ge=1)] = None,
    std_dev_threshold: Annotated[float | None, Query(gt=0)] = None,
) -> Analytics:
    item = await _get(db, Item, item_id)
    return Analytics.model_validate(await analytics.item_analytics(db, item, days, std_dev_threshold))


# Price history


def _history_conditions(item_id: int, filters: HistoryFilters) -> list:
    conditions = [PriceHistory.item_id == item_id]
    if filters.min_price is not None:
        conditions.append(PriceHistory.price >= filters.min_price)
    if filters.max_price is not None:
        conditions.append(PriceHistory.price <= filters.max_price)
    if filters.stock:
        stock = {"in": True, "out": False, "unknown": None}[filters.stock]
        conditions.append(PriceHistory.in_stock.is_(stock))
    # Readings without a confidence (entered by hand or very old) match neither confidence filter.
    if filters.min_confidence is not None:
        conditions.append(PriceHistory.price_confidence >= filters.min_confidence)
    if filters.confidence_below is not None:
        conditions.append(PriceHistory.price_confidence < filters.confidence_below)
    return conditions


def _manual_values(data: HistoryUpdate) -> dict:
    """Column values for a correction by hand. A corrected reading has no AI confidence, so it counts as trusted."""
    values: dict[Any, Any] = {}
    if data.price is not None:
        values |= {
            PriceHistory.price: data.price,
            PriceHistory.price_confidence: None,
            # Keep the range top and "was" price only while they still make sense above the new price.
            PriceHistory.price_high: case((PriceHistory.price_high > data.price, PriceHistory.price_high)),
            PriceHistory.regular_price: case((PriceHistory.regular_price > data.price, PriceHistory.regular_price)),
        }
    if data.in_stock is not None:
        values |= {PriceHistory.in_stock: data.in_stock, PriceHistory.in_stock_confidence: None}
    return values


@router.get("/items/{item_id}/history")
async def item_history(item_id: int, query: Annotated[HistoryQuery, Query()], db: DB) -> HistoryPage:
    await _get(db, Item, item_id)
    conditions = _history_conditions(item_id, query)
    total = await db.scalar(select(func.count()).select_from(PriceHistory).where(*conditions))
    records = await db.scalars(
        select(PriceHistory)
        .where(*conditions)
        .order_by(PriceHistory.timestamp.desc())
        .offset((query.page - 1) * query.size)
        .limit(query.size)
    )
    return HistoryPage(items=records.all(), total=total, page=query.page, size=query.size)


@router.post("/items/{item_id}/history/bulk")
async def bulk_history(item_id: int, data: HistoryBulk, db: DB) -> BulkResult:
    await _get(db, Item, item_id)
    if data.filters is not None:
        conditions = _history_conditions(item_id, data.filters)
    else:
        conditions = [PriceHistory.item_id == item_id, PriceHistory.id.in_(data.ids)]
    if data.action == "delete":
        result = await db.execute(delete(PriceHistory).where(*conditions))
    else:
        result = await db.execute(update(PriceHistory).where(*conditions).values(_manual_values(data)))
    await _sync_latest(db, item_id)
    return BulkResult(count=result.rowcount)


@router.put("/history/{record_id}")
async def update_history(record_id: int, data: HistoryUpdate, db: DB) -> dict:
    record = await _get(db, PriceHistory, record_id)
    if values := _manual_values(data):
        await db.execute(update(PriceHistory).where(PriceHistory.id == record_id).values(values))
    await _sync_latest(db, record.item_id)
    return {"ok": True}


@router.delete("/history/{record_id}", status_code=204)
async def delete_history(record_id: int, db: DB) -> None:
    record = await _get(db, PriceHistory, record_id)
    await db.delete(record)
    await _sync_latest(db, record.item_id)


async def _sync_latest(db: AsyncSession, item_id: int) -> None:
    """Keep the item's current price and stock in line with its newest history record."""
    await db.flush()
    latest = await db.scalar(
        select(PriceHistory).where(PriceHistory.item_id == item_id).order_by(PriceHistory.timestamp.desc()).limit(1)
    )
    await db.execute(
        update(Item)
        .where(Item.id == item_id)
        .values(
            {
                field: latest and getattr(latest, field)
                for field in ("price_high", "regular_price", "promotion", "in_stock")
            }
            | {"current_price": latest and latest.price}
        )
    )
    await db.commit()


# Settings and jobs


@router.get("/settings")
async def get_settings(db: DB) -> dict[str, Any]:
    return app_settings.public(await app_settings.load(db))


@router.put("/settings")
async def update_settings(changes: dict[str, Any], db: DB) -> dict[str, Any]:
    try:
        saved = await app_settings.save(db, changes)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from None
    return app_settings.public(saved)


@router.post("/settings/test-ai")
async def test_ai(data: AITest, db: DB) -> AITestResult:
    """Run one extraction for an item with the given (possibly unsaved) settings, as a real check would."""
    item = await _get(db, Item, data.item_id)
    try:
        settings = app_settings.merge(await app_settings.load(db), data.settings)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from None

    # The saved screenshot is enough unless the model should also get the page text, which isn't kept.
    screenshot_path = checks.screenshot_file(item.id)
    page_text = None
    if screenshot_path.exists() and not settings.text_context_enabled:
        screenshot = await asyncio.to_thread(screenshot_path.read_bytes)
    else:
        try:
            capture = await scraper.capture(
                item.url,
                selector=item.selector,
                scroll_pixels=settings.smart_scroll_pixels if settings.smart_scroll_enabled else 0,
                timeout_ms=settings.scraper_timeout,
            )
        except scraper.ScrapeError as exc:
            raise HTTPException(502, f"Couldn't load the page: {exc}") from None
        screenshot = capture.screenshot
        if settings.text_context_enabled:
            page_text = capture.text[: settings.text_context_length]

    started = time.monotonic()
    try:
        reply = await ai.ask(
            screenshot,
            settings,
            url=item.url,
            page_text=page_text,
            custom_prompt=item.custom_prompt,
            last_price=item.current_price,
        )
    except Exception as exc:
        raise HTTPException(502, f"The model call failed: {checks.describe(exc)}") from None
    seconds = round(time.monotonic() - started, 1)
    try:
        extraction = ai.parse_response(reply).model_dump()
    except ai.ExtractionError as exc:
        return AITestResult(seconds=seconds, reply=reply, extraction=None, error=str(exc))
    return AITestResult(seconds=seconds, reply=reply, extraction=extraction, error=None)


@router.post("/forecasts/refresh")
async def refresh_forecasts() -> dict:
    if forecast.is_running():
        return {"started": False}
    checks.spawn(forecast.forecast_all())
    return {"started": True}


# Notification profiles


@router.get("/notification-profiles")
async def list_profiles(db: DB) -> list[ProfileOut]:
    profiles = await db.scalars(select(NotificationProfile).order_by(NotificationProfile.name))
    return [ProfileOut.model_validate(profile) for profile in profiles]


@router.post("/notification-profiles", status_code=201)
async def create_profile(data: ProfileIn, db: DB) -> ProfileOut:
    profile = NotificationProfile()
    await _save_profile(db, profile, data)
    return ProfileOut.model_validate(profile)


@router.put("/notification-profiles/{profile_id}")
async def update_profile(profile_id: int, data: ProfileIn, db: DB) -> ProfileOut:
    profile = await _get(db, NotificationProfile, profile_id)
    if data.apprise_url == notify.mask(profile.apprise_url):
        data.apprise_url = profile.apprise_url  # unchanged, the client only ever saw the mask
    await _save_profile(db, profile, data)
    return ProfileOut.model_validate(profile)


async def _save_profile(db: AsyncSession, profile: NotificationProfile, data: ProfileIn) -> None:
    if not notify.is_valid_url(data.apprise_url):
        raise HTTPException(422, "Not a valid Apprise URL")
    for key, value in data.model_dump().items():
        setattr(profile, key, value)
    db.add(profile)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, f"A profile named '{data.name}' already exists") from None


@router.delete("/notification-profiles/{profile_id}", status_code=204)
async def delete_profile(profile_id: int, db: DB) -> None:
    profile = await _get(db, NotificationProfile, profile_id)
    await db.execute(
        update(Item).where(Item.notification_profile_id == profile_id).values(notification_profile_id=None)
    )
    await db.delete(profile)
    await db.commit()


@router.post("/notification-profiles/test", status_code=204)
async def test_notification(data: NotificationTest) -> Response:
    return await _send_test(data.apprise_url)


@router.post("/notification-profiles/{profile_id}/test", status_code=204)
async def test_saved_notification(profile_id: int, db: DB) -> Response:
    profile = await _get(db, NotificationProfile, profile_id)
    return await _send_test(profile.apprise_url)


async def _send_test(url: str) -> Response:
    if not await notify.send(url, "Pricecious test", "Notifications are working."):
        raise HTTPException(502, "The notification could not be delivered; check the Apprise URL")
    return Response(status_code=204)
