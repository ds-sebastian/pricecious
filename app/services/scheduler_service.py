import asyncio
import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app import ai, database, models, notifications, scraper
from app.ai_schema import AIExtractionMetadata, AIExtractionResponse
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# Constants
PRICE_CHANGE_THRESHOLD_PERCENT = 20.0
LOW_CONFIDENCE_THRESHOLD = 0.7
DEFAULT_REFRESH_INTERVAL = 60


def _get_item_data(item_id: int):
    SessionLocal = database.SessionLocal
    session = SessionLocal()
    try:
        item = session.query(models.Item).filter(models.Item.id == item_id).first()
        if not item:
            return None, None

        profile = item.notification_profile
        settings_map = {s.key: s.value for s in session.query(models.Settings).all()}

        item_data = {
            "id": item.id,
            "url": item.url,
            "selector": item.selector,
            "name": item.name,
            "current_price": item.current_price,
            "in_stock": item.in_stock,
            "target_price": item.target_price,
            "notification_profile": {
                "apprise_url": profile.apprise_url,
                "notify_on_price_drop": profile.notify_on_price_drop,
                "price_drop_threshold_percent": profile.price_drop_threshold_percent,
                "notify_on_target_price": profile.notify_on_target_price,
                "notify_on_stock_change": profile.notify_on_stock_change,
            }
            if profile
            else None,
        }

        config = {
            "smart_scroll": settings_map.get("smart_scroll_enabled", "false").lower() == "true",
            "smart_scroll_pixels": int(settings_map.get("smart_scroll_pixels", "350")),
            "text_context_enabled": settings_map.get("text_context_enabled", "false").lower() == "true",
            "text_length": int(settings_map.get("text_context_length", "5000"))
            if settings_map.get("text_context_enabled", "false").lower() == "true"
            else 0,
            "scraper_timeout": int(settings_map.get("scraper_timeout", "90000")),
        }
        return item_data, config
    finally:
        session.close()


def _get_thresholds():
    SessionLocal = database.SessionLocal
    session = SessionLocal()
    try:
        settings_map = {s.key: s.value for s in session.query(models.Settings).all()}
        return {
            "price": float(settings_map.get("confidence_threshold_price", "0.5")),
            "stock": float(settings_map.get("confidence_threshold_stock", "0.5")),
        }
    finally:
        session.close()


def _update_db_result(
    item_id: int,
    extraction: AIExtractionResponse,
    metadata: AIExtractionMetadata,
    thresholds: dict,
    screenshot_path: str,
):
    SessionLocal = database.SessionLocal
    session = SessionLocal()
    try:
        item = session.query(models.Item).filter(models.Item.id == item_id).first()
        if not item:
            return None, None

        old_price = item.current_price
        old_stock = item.in_stock

        price = extraction.price
        in_stock = extraction.in_stock
        price_confidence = extraction.price_confidence
        in_stock_confidence = extraction.in_stock_confidence

        if price is not None:
            if price_confidence >= thresholds["price"]:
                # Check for large price change with low confidence
                if old_price is not None:
                    price_change_pct = abs(price - old_price) / old_price * 100
                    if (
                        price_change_pct > PRICE_CHANGE_THRESHOLD_PERCENT
                        and price_confidence < LOW_CONFIDENCE_THRESHOLD
                    ):
                        item.last_error = (
                            f"Uncertain: Large price change ({price_change_pct:.1f}%) "
                            f"with low confidence ({price_confidence:.2f})"
                        )
                        item.current_price = price
                        item.current_price_confidence = price_confidence
                    else:
                        item.current_price = price
                        item.current_price_confidence = price_confidence
                else:
                    item.current_price = price
                    item.current_price_confidence = price_confidence

        if in_stock is not None and in_stock_confidence >= thresholds["stock"]:
            item.in_stock = in_stock
            item.in_stock_confidence = in_stock_confidence

        if price is not None:
            history = models.PriceHistory(
                item_id=item.id,
                price=price,
                screenshot_path=screenshot_path,
                price_confidence=price_confidence,
                in_stock_confidence=in_stock_confidence,
                ai_model=metadata.model_name,
                ai_provider=metadata.provider,
                prompt_version=metadata.prompt_version,
                repair_used=metadata.repair_used,
            )
            session.add(history)

        item.last_checked = datetime.now(UTC)
        item.is_refreshing = False
        if not item.last_error or not item.last_error.startswith("Uncertain:"):
            item.last_error = None
        session.commit()
        return old_price, old_stock
    finally:
        session.close()


def _update_db_error(item_id, error_msg):
    SessionLocal = database.SessionLocal
    session = SessionLocal()
    try:
        item = session.query(models.Item).filter(models.Item.id == item_id).first()
        if item:
            item.is_refreshing = False
            item.last_error = error_msg
            session.commit()
    finally:
        session.close()


async def _handle_notifications(item_data, price, old_price, in_stock, old_stock):
    profile = item_data["notification_profile"]
    if not profile:
        return

    if profile["notify_on_price_drop"] and price is not None and old_price is not None:
        if price < old_price:
            drop_percent = ((old_price - price) / old_price) * 100
            if drop_percent >= profile["price_drop_threshold_percent"]:
                await notifications.send_notification(
                    [profile["apprise_url"]],
                    f"Price Drop Alert: {item_data['name']}",
                    f"Price dropped by {drop_percent:.1f}%! Now ${price} (was ${old_price})",
                )

    if (
        profile["notify_on_target_price"]
        and price is not None
        and item_data["target_price"]
        and price <= item_data["target_price"]
    ):
        await notifications.send_notification(
            [profile["apprise_url"]],
            f"Target Price Alert: {item_data['name']}",
            f"Price is ${price} (Target: ${item_data['target_price']})",
        )

    if profile["notify_on_stock_change"] and in_stock is not None and old_stock is not None and in_stock != old_stock:
        status = "In Stock" if in_stock else "Out of Stock"
        await notifications.send_notification(
            [profile["apprise_url"]],
            f"Stock Alert: {item_data['name']}",
            f"Item is now {status}",
        )


async def process_item_check(item_id: int):
    """
    Background task to check an item's price/stock.
    Creates its own DB session to ensure thread safety.
    """
    loop = asyncio.get_running_loop()

    item_data, config = await loop.run_in_executor(None, _get_item_data, item_id)

    if not item_data:
        logger.error(f"process_item_check: Item ID {item_id} not found")
        return

    try:
        logger.info(f"Checking item: {item_data['name']} ({item_data['url']})")

        screenshot_path, page_text = await scraper.scrape_item(
            item_data["url"],
            item_data["selector"],
            item_id,
            smart_scroll=config["smart_scroll"],
            scroll_pixels=config["smart_scroll_pixels"],
            text_length=config["text_length"],
            timeout=config["scraper_timeout"],
        )

        if not screenshot_path:
            raise Exception("Failed to capture screenshot")

        ai_result = await ai.analyze_image(screenshot_path, page_text=page_text)
        if not ai_result:
            raise Exception("AI analysis failed to return a result")

        extraction, metadata = ai_result

        thresholds = await loop.run_in_executor(None, _get_thresholds)

        old_price, old_stock = await loop.run_in_executor(
            None,
            _update_db_result,
            item_id,
            extraction,
            metadata,
            thresholds,
            screenshot_path,
        )

        # Notifications
        await _handle_notifications(item_data, extraction.price, old_price, extraction.in_stock, old_stock)

    except Exception as e:
        logger.error(f"Error in process_item_check: {e}")
        await loop.run_in_executor(None, _update_db_error, item_id, str(e))


def _get_due_items():
    SessionLocal = database.SessionLocal
    db = SessionLocal()
    try:
        items = db.query(models.Item).filter(models.Item.is_active).all()
        global_interval = int(SettingsService.get_setting_value(db, "refresh_interval_minutes", "60"))

        due_items = []
        for item in items:
            if item.is_refreshing:
                continue

            interval = global_interval
            if item.notification_profile and item.notification_profile.check_interval_minutes:
                interval = item.notification_profile.check_interval_minutes

            if item.last_checked:
                last_checked_aware = (
                    item.last_checked.replace(tzinfo=UTC) if item.last_checked.tzinfo is None else item.last_checked
                )
                time_since_check = (datetime.now(UTC) - last_checked_aware).total_seconds() / 60
                if time_since_check >= interval:
                    due_items.append((item.id, interval, int(time_since_check)))
            else:
                due_items.append((item.id, interval, -1))
        return due_items
    finally:
        db.close()


async def scheduled_refresh():
    """Background job that runs every minute to check for items due for refresh."""
    logger.info("Heartbeat: Checking for items due for refresh")
    loop = asyncio.get_running_loop()

    try:
        due_items = await loop.run_in_executor(None, _get_due_items)
        for item_id, _, _ in due_items:
            await process_item_check(item_id)
    except Exception as e:
        logger.error(f"Error in scheduled refresh: {e}", exc_info=True)
