import asyncio
import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app import database, models
from app.ai_schema import AIExtractionMetadata, AIExtractionResponse
from app.services.ai_service import AIService
from app.services.item_service import ItemService
from app.services.notification_service import NotificationService
from app.services.scraper_service import ScraperService

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# Constants
PRICE_CHANGE_THRESHOLD_PERCENT = 20.0
LOW_CONFIDENCE_THRESHOLD = 0.7


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


async def process_item_check(item_id: int):
    """
    Background task to check an item's price/stock.
    Creates its own DB session to ensure thread safety.
    """
    loop = asyncio.get_running_loop()

    # Use a new session for this operation
    SessionLocal = database.SessionLocal
    session = SessionLocal()
    try:
        item_data, config = await loop.run_in_executor(None, ItemService.get_item_data_for_checking, session, item_id)
    finally:
        session.close()

    if not item_data:
        logger.error(f"process_item_check: Item ID {item_id} not found")
        return

    try:
        logger.info(f"Checking item: {item_data['name']} ({item_data['url']})")

        screenshot_path, page_text = await ScraperService.scrape_item(
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

        ai_result = await AIService.analyze_image(screenshot_path, page_text=page_text)
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
        await NotificationService.send_item_notifications(
            item_data, extraction.price, old_price, extraction.in_stock, old_stock
        )

    except Exception as e:
        logger.error(f"Error in process_item_check: {e}")
        await loop.run_in_executor(None, _update_db_error, item_id, str(e))


async def scheduled_refresh():
    """Background job that runs every minute to check for items due for refresh."""
    logger.info("Heartbeat: Checking for items due for refresh")
    loop = asyncio.get_running_loop()

    try:
        SessionLocal = database.SessionLocal
        session = SessionLocal()
        try:
            due_items = await loop.run_in_executor(None, ItemService.get_due_items, session)
        finally:
            session.close()

        for item_id, _, _ in due_items:
            await process_item_check(item_id)
    except Exception as e:
        logger.error(f"Error in scheduled refresh: {e}", exc_info=True)
