import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from app import database, models
from app.ai_schema import AIExtractionMetadata, AIExtractionResponse
from app.services.ai_service import AIService
from app.services.item_service import ItemService
from app.services.notification_service import NotificationService
from app.services.scraper_service import ScrapeConfig, ScraperService

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

PRICE_CHANGE_THRESHOLD_PERCENT = 20.0
LOW_CONFIDENCE_THRESHOLD = 0.7
MAX_CONCURRENT_CHECKS = 5


@dataclass
class UpdateData:
    """Data needed to update item after AI analysis."""

    extraction: AIExtractionResponse
    metadata: AIExtractionMetadata
    thresholds: dict
    screenshot_path: str


def _get_thresholds(session: Session) -> dict[str, float]:
    """Fetch only necessary threshold settings."""
    # Optimization: Only fetch specific keys instead of all settings
    keys = ["confidence_threshold_price", "confidence_threshold_stock"]
    settings = session.query(models.Settings.key, models.Settings.value).filter(models.Settings.key.in_(keys)).all()
    settings_map = {k: v for k, v in settings}
    return {
        "price": float(settings_map.get("confidence_threshold_price", "0.5")),
        "stock": float(settings_map.get("confidence_threshold_stock", "0.5")),
    }


def _update_item_in_db(item_id: int, update_data: UpdateData) -> tuple[float | None, bool | None]:
    """Update item in DB with new data. Returns (old_price, old_stock)."""
    with database.SessionLocal() as session:
        item = session.query(models.Item).filter(models.Item.id == item_id).first()
        if not item:
            return None, None

        old_price, old_stock = item.current_price, item.in_stock
        price, in_stock = update_data.extraction.price, update_data.extraction.in_stock
        p_conf, s_conf = update_data.extraction.price_confidence, update_data.extraction.in_stock_confidence

        if price is not None:
            if p_conf >= update_data.thresholds["price"]:
                # Check for suspicious price changes
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
                    screenshot_path=update_data.screenshot_path,
                    price_confidence=p_conf,
                    in_stock_confidence=s_conf,
                    ai_model=update_data.metadata.model_name,
                    ai_provider=update_data.metadata.provider,
                    prompt_version=update_data.metadata.prompt_version,
                    repair_used=update_data.metadata.repair_used,
                )
            )

        if in_stock is not None and s_conf >= update_data.thresholds["stock"]:
            item.in_stock = in_stock
            item.in_stock_confidence = s_conf

        old_timestamp = item.last_checked
        item.last_checked = datetime.now(UTC)
        item.is_refreshing = False
        if item.last_error and not item.last_error.startswith("Uncertain:"):
            item.last_error = None

        session.commit()
        logger.info(
            f"Updated item {item_id}: price={price}, stock={in_stock} "
            f"(last_checked: {old_timestamp} -> {item.last_checked})"
        )
        return old_price, old_stock


def _handle_error(item_id: int, error_msg: str):
    """Log error and update item status in DB."""
    logger.error(f"Error checking item {item_id}: {error_msg}")
    with database.SessionLocal() as session:
        if item := session.query(models.Item).filter(models.Item.id == item_id).first():
            item.is_refreshing = False
            item.last_error = str(error_msg)
            item.last_checked = datetime.now(UTC)
            session.commit()


def _process_single_item_sync(item_id: int):
    """Synchronous part of item processing to run in executor."""
    # 1. Fetch Item Data (New session for thread safety)
    with database.SessionLocal() as session:
        item_data, config = ItemService.get_item_data_for_checking(session, item_id)
        if not item_data:
            return None

        # Pre-fetch thresholds while we have the session
        thresholds = _get_thresholds(session)

    return item_data, config, thresholds


async def process_item_check(item_id: int, semaphore: asyncio.Semaphore | None = None):
    """Process a single item check with concurrency limit."""
    if semaphore:
        async with semaphore:
            await _execute_check(item_id)
    else:
        await _execute_check(item_id)


async def _execute_check(item_id: int):
    loop = asyncio.get_running_loop()

    try:
        # 1. Fetch Data (Thread-safe)
        result = await loop.run_in_executor(None, _process_single_item_sync, item_id)
        if not result:
            logger.error(f"Item {item_id} not found")
            return
        item_data, config, thresholds = result

        logger.info(f"Checking item: {item_data['name']} ({item_data['url']})")

        # 2. Scrape
        scrape_config = ScrapeConfig(
            smart_scroll=config["smart_scroll"],
            scroll_pixels=config["smart_scroll_pixels"],
            text_length=config["text_length"],
            timeout=config["scraper_timeout"],
        )
        screenshot_path, page_text = await ScraperService.scrape_item(
            item_data["url"],
            item_data["selector"],
            item_id,
            scrape_config,
        )

        if not screenshot_path:
            raise Exception("Failed to capture screenshot")

        # 3. Analyze with AI
        if not (ai_result := await AIService.analyze_image(screenshot_path, page_text=page_text)):
            raise Exception("AI analysis failed")

        extraction, metadata = ai_result

        # 4. Update Database (Thread-safe)
        update_data = UpdateData(
            extraction=extraction,
            metadata=metadata,
            thresholds=thresholds,
            screenshot_path=screenshot_path,
        )

        old_price, old_stock = await loop.run_in_executor(None, _update_item_in_db, item_id, update_data)

        # 5. Notify
        await NotificationService.send_item_notifications(
            item_data, extraction.price, old_price, extraction.in_stock, old_stock
        )

    except Exception as e:
        await loop.run_in_executor(None, _handle_error, item_id, str(e))


async def scheduled_refresh():
    """Periodic task to check for items due for refresh."""
    logger.info("Heartbeat: Checking for items due for refresh")
    loop = asyncio.get_running_loop()

    try:
        # Fetch due items in a new session that gets closed immediately
        # This avoids holding a session open with stale data during processing
        due_items = await loop.run_in_executor(None, ItemService.get_due_items)

        if not due_items:
            return

        logger.info(f"Found {len(due_items)} items due for refresh")
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)

        # due_items is list of (id, interval, last_checked_mins)
        tasks = [process_item_check(item_id, semaphore) for item_id, _, _ in due_items]
        await asyncio.gather(*tasks)

    except Exception as e:
        logger.error(f"Error in scheduled refresh: {e}", exc_info=True)
