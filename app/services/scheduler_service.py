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

PRICE_CHANGE_THRESHOLD_PERCENT = 20.0
LOW_CONFIDENCE_THRESHOLD = 0.7


def _get_thresholds():
    with database.SessionLocal() as session:
        settings = {s.key: s.value for s in session.query(models.Settings).all()}
        return {
            "price": float(settings.get("confidence_threshold_price", "0.5")),
            "stock": float(settings.get("confidence_threshold_stock", "0.5")),
        }


def _update_db_result(
    item_id: int,
    extraction: AIExtractionResponse,
    metadata: AIExtractionMetadata,
    thresholds: dict,
    screenshot_path: str,
):
    with database.SessionLocal() as session:
        item = session.query(models.Item).filter(models.Item.id == item_id).first()
        if not item:
            return None, None

        old_price, old_stock = item.current_price, item.in_stock
        price, in_stock = extraction.price, extraction.in_stock
        p_conf, s_conf = extraction.price_confidence, extraction.in_stock_confidence

        if price is not None:
            if p_conf >= thresholds["price"]:
                if (
                    old_price
                    and (abs(price - old_price) / old_price * 100 > PRICE_CHANGE_THRESHOLD_PERCENT)
                    and p_conf < LOW_CONFIDENCE_THRESHOLD
                ):
                    item.last_error = f"Uncertain: Large price change with low confidence ({p_conf:.2f})"
                else:
                    item.last_error = None
                item.current_price = price
                item.current_price_confidence = p_conf

            session.add(
                models.PriceHistory(
                    item_id=item.id,
                    price=price,
                    screenshot_path=screenshot_path,
                    price_confidence=p_conf,
                    in_stock_confidence=s_conf,
                    ai_model=metadata.model_name,
                    ai_provider=metadata.provider,
                    prompt_version=metadata.prompt_version,
                    repair_used=metadata.repair_used,
                )
            )

        if in_stock is not None and s_conf >= thresholds["stock"]:
            item.in_stock = in_stock
            item.in_stock_confidence = s_conf

        item.last_checked = datetime.now(UTC)
        item.is_refreshing = False
        if item.last_error and not item.last_error.startswith("Uncertain:"):
            item.last_error = None

        session.commit()
        return old_price, old_stock


def _update_db_error(item_id, error_msg):
    with database.SessionLocal() as session:
        if item := session.query(models.Item).filter(models.Item.id == item_id).first():
            item.is_refreshing = False
            item.last_error = error_msg
            session.commit()


async def process_item_check(item_id: int):
    loop = asyncio.get_running_loop()
    with database.SessionLocal() as session:
        item_data, config = await loop.run_in_executor(None, ItemService.get_item_data_for_checking, session, item_id)

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

        if not (ai_result := await AIService.analyze_image(screenshot_path, page_text=page_text)):
            raise Exception("AI analysis failed")

        extraction, metadata = ai_result
        thresholds = await loop.run_in_executor(None, _get_thresholds)
        old_price, old_stock = await loop.run_in_executor(
            None, _update_db_result, item_id, extraction, metadata, thresholds, screenshot_path
        )

        await NotificationService.send_item_notifications(
            item_data, extraction.price, old_price, extraction.in_stock, old_stock
        )

    except Exception as e:
        logger.error(f"Error in process_item_check: {e}")
        await loop.run_in_executor(None, _update_db_error, item_id, str(e))


async def scheduled_refresh():
    logger.info("Heartbeat: Checking for items due for refresh")
    loop = asyncio.get_running_loop()
    try:
        with database.SessionLocal() as session:
            due_items = await loop.run_in_executor(None, ItemService.get_due_items, session)

        for item_id, _, _ in due_items:
            await process_item_check(item_id)
    except Exception as e:
        logger.error(f"Error in scheduled refresh: {e}", exc_info=True)
