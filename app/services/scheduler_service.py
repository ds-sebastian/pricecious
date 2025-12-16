import asyncio
import logging
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import database, models
from app.ai_schema import AIExtractionMetadata, AIExtractionResponse
from app.services.ai_service import AIService
from app.services.forecasting_service import ForecastingService
from app.services.item_service import ItemService
from app.services.notification_service import NotificationService
from app.services.scraper_service import ScrapeConfig, ScraperService

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

PRICE_CHANGE_THRESHOLD_PERCENT = 20.0
LOW_CONFIDENCE_THRESHOLD = 0.7
MAX_CONCURRENT_CHECKS = 5
DEFAULT_OUTLIER_THRESHOLD = 500.0


@dataclass
class UpdateData:
    """Data needed to update item after AI analysis."""

    extraction: AIExtractionResponse
    metadata: AIExtractionMetadata
    thresholds: dict
    screenshot_path: str


async def _get_thresholds(session: AsyncSession) -> dict[str, float]:
    """Fetch only necessary threshold settings."""
    # Optimization: Only fetch specific keys instead of all settings
    keys = [
        "confidence_threshold_price",
        "confidence_threshold_stock",
        "price_outlier_threshold_percent",
        "price_outlier_threshold_enabled",
    ]
    result = await session.execute(
        select(models.Settings.key, models.Settings.value).where(models.Settings.key.in_(keys))
    )
    settings_map = {k: v for k, v in result.all()}
    return {
        "price": float(settings_map.get("confidence_threshold_price", "0.5")),
        "stock": float(settings_map.get("confidence_threshold_stock", "0.5")),
        "outlier_percent": float(settings_map.get("price_outlier_threshold_percent", str(DEFAULT_OUTLIER_THRESHOLD))),
        "outlier_enabled": settings_map.get("price_outlier_threshold_enabled", "false").lower() == "true",
    }


async def _update_item_in_db(
    item_id: int, update_data: UpdateData, session: AsyncSession
) -> tuple[float | None, bool | None]:
    """Update item in DB with new data. Returns (old_price, old_stock)."""
    result = await session.execute(select(models.Item).where(models.Item.id == item_id))
    item = result.scalars().first()
    if not item:
        return None, None

    old_price, old_stock = item.current_price, item.in_stock
    price, in_stock = update_data.extraction.price, update_data.extraction.in_stock
    p_conf, s_conf = update_data.extraction.price_confidence, update_data.extraction.in_stock_confidence

    if price is not None:
        # Outlier Check - Only if enabled
        if update_data.thresholds["outlier_enabled"] and old_price and old_price > 0:
            percent_diff = ((price - old_price) / old_price) * 100
            if percent_diff > update_data.thresholds["outlier_percent"]:
                error_msg = (
                    f"Price rejected: {percent_diff:.1f}% increase exceeds outlier threshold "
                    f"({update_data.thresholds['outlier_percent']}%)"
                )
                logger.warning(f"Item {item_id}: {error_msg}")
                item.last_error = error_msg
                item.last_checked = datetime.now(UTC).replace(tzinfo=None)
                item.is_refreshing = False
                await session.commit()
                return old_price, old_stock

        if p_conf >= update_data.thresholds["price"]:
            # Check for suspicious price changes (warning only)
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
                in_stock=in_stock,
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
    item.last_checked = datetime.now(UTC).replace(tzinfo=None)
    item.is_refreshing = False
    if item.last_error and not item.last_error.startswith("Uncertain:"):
        item.last_error = None

    await session.commit()
    logger.info(
        f"Updated item {item_id}: price={price}, stock={in_stock} "
        f"(last_checked: {old_timestamp} -> {item.last_checked})"
    )
    return old_price, old_stock


async def _handle_error(item_id: int, error_msg: str):
    """Log error and update item status in DB."""
    logger.error(f"Error checking item {item_id}: {error_msg}")
    async with database.AsyncSessionLocal() as session:
        result = await session.execute(select(models.Item).where(models.Item.id == item_id))
        if item := result.scalars().first():
            item.is_refreshing = False
            item.last_error = str(error_msg)
            item.last_checked = datetime.now(UTC).replace(tzinfo=None)
            await session.commit()


async def _process_single_item_data(item_id: int, session: AsyncSession):
    """Fetch item data and config."""
    item_data, config = await ItemService.get_item_data_for_checking(session, item_id)
    if not item_data:
        return None

    # Pre-fetch thresholds while we have the session
    thresholds = await _get_thresholds(session)

    return item_data, config, thresholds


async def process_item_check(item_id: int, semaphore: asyncio.Semaphore | None = None):
    """Process a single item check with concurrency limit."""
    async with semaphore if semaphore else nullcontext():
        await _execute_check(item_id)


async def _execute_check(item_id: int):
    try:
        # Use a single session for the entire check process
        async with database.AsyncSessionLocal() as session:
            # 1. Fetch Data
            result = await _process_single_item_data(item_id, session)
            if not result:
                logger.error(f"Item {item_id} not found")
                return
            item_data, config, thresholds = result
            logger.info(f"Checking item: {item_data['name']} ({item_data['url']})")

            # 2. Scrape (outside session is fine - no DB calls)
            scrape_config = ScrapeConfig(
                smart_scroll=config["smart_scroll"],
                scroll_pixels=config["smart_scroll_pixels"],
                text_length=config["text_length"],
                timeout=config["scraper_timeout"],
            )
            screenshot_path, page_text = await ScraperService.scrape_item(
                item_data["url"], item_data["selector"], item_id, scrape_config
            )
            if not screenshot_path:
                raise Exception("Failed to capture screenshot")

            # 3. Analyze with AI
            ai_result = await AIService.analyze_image(
                screenshot_path, page_text=page_text, custom_prompt=item_data.get("custom_prompt")
            )
            if not ai_result:
                raise Exception("AI analysis failed")
            extraction, metadata = ai_result

            # 4. Update Database (now inside session scope!)
            update_data = UpdateData(
                extraction=extraction, metadata=metadata, thresholds=thresholds, screenshot_path=screenshot_path
            )
            old_price, old_stock = await _update_item_in_db(item_id, update_data, session)

            # 5. Notify
            await NotificationService.send_item_notifications(
                item_data, extraction.price, old_price, extraction.in_stock, old_stock
            )

    except Exception as e:
        await _handle_error(item_id, str(e))


async def scheduled_refresh():
    """Periodic task to check for items due for refresh."""
    logger.debug("Heartbeat: Checking for items due for refresh")

    try:
        # Fetch due items
        due_items = await ItemService.get_due_items()

        if not due_items:
            return

        logger.info(f"Found {len(due_items)} items due for refresh")
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)

        # due_items is list of (id, interval, last_checked_mins)
        tasks = [process_item_check(item_id, semaphore) for item_id, _, _ in due_items]
        await asyncio.gather(*tasks)

    except Exception as e:
        logger.error(f"Error in scheduled refresh: {e}", exc_info=True)


async def scheduled_forecasting():
    """Daily task to generate forecasts for all items."""
    logger.info("Starting scheduled forecasting job")
    try:
        async with database.AsyncSessionLocal() as session:
            result = await session.execute(select(models.Item.id).where(models.Item.is_active))
            item_ids = result.scalars().all()

        logger.info(f"Forecasting for {len(item_ids)} active items")

        # Process sequentially to avoid memory spikes with Prophet
        for item_id in item_ids:
            try:
                await ForecastingService.generate_forecast(item_id)
            except Exception as e:
                logger.error(f"Forecasting failed for item {item_id}: {e}")

    except Exception as e:
        logger.error(f"Error in scheduled forecasting: {e}", exc_info=True)
