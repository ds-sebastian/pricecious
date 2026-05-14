import asyncio
import logging
from contextlib import nullcontext
from dataclasses import dataclass

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
from app.utils.datetime_utils import utc_now_naive

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

PRICE_CHANGE_THRESHOLD_PERCENT = 20.0
LOW_CONFIDENCE_THRESHOLD = 0.7
MAX_CONCURRENT_CHECKS = 5
DEFAULT_OUTLIER_THRESHOLD = 500.0

# Consecutive failure constants
DEFAULT_MAX_CONSECUTIVE_FAILURES = 20

# Absolute price sanity defaults
DEFAULT_PRICE_MIN_FLOOR = 0.01
DEFAULT_PRICE_MAX_CEILING = 100_000.0


# Error type constants for structured classification
class ErrorType:
    SCRAPE_FAILED = "scrape_failed"
    AI_FAILED = "ai_failed"
    LOW_CONFIDENCE = "low_confidence"
    OUTLIER_REJECTED = "outlier_rejected"
    PRICE_OUT_OF_BOUNDS = "price_out_of_bounds"
    AUTO_DEACTIVATED = "auto_deactivated"


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
        "price_min_floor",
        "price_max_ceiling",
        "max_consecutive_failures",
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
        "price_min_floor": float(settings_map.get("price_min_floor", str(DEFAULT_PRICE_MIN_FLOOR))),
        "price_max_ceiling": float(settings_map.get("price_max_ceiling", str(DEFAULT_PRICE_MAX_CEILING))),
        "max_consecutive_failures": int(
            settings_map.get("max_consecutive_failures", str(DEFAULT_MAX_CONSECUTIVE_FAILURES))
        ),
    }


def _check_price_rejection(
    price: float, old_price: float | None, thresholds: dict, item_id: int
) -> tuple[str | None, str | None]:
    """Check if a price should be rejected due to bounds or outlier rules.

    Returns (error_msg, error_type) or (None, None) if price is acceptable.
    """
    # Absolute price sanity bounds
    if price < thresholds["price_min_floor"] or price > thresholds["price_max_ceiling"]:
        return (
            f"Price rejected: ${price:.2f} outside sanity bounds "
            f"(${thresholds['price_min_floor']:.2f} - ${thresholds['price_max_ceiling']:.2f})",
            ErrorType.PRICE_OUT_OF_BOUNDS,
        )

    # Bidirectional outlier check
    if thresholds["outlier_enabled"] and old_price and old_price > 0:
        percent_diff = ((price - old_price) / old_price) * 100
        if abs(percent_diff) > thresholds["outlier_percent"]:
            direction = "increase" if percent_diff > 0 else "decrease"
            return (
                f"Price rejected: {abs(percent_diff):.1f}% {direction} exceeds outlier threshold "
                f"({thresholds['outlier_percent']}%)",
                ErrorType.OUTLIER_REJECTED,
            )

    return None, None


async def _update_item_in_db(
    item_id: int, update_data: UpdateData, session: AsyncSession
) -> tuple[float | None, bool | None]:
    """Update item in DB with new data. Returns (old_price, old_stock).

    All mutations are committed in a single transaction at the end.
    """
    result = await session.execute(select(models.Item).where(models.Item.id == item_id))
    item = result.scalars().first()
    if not item:
        return None, None

    old_price, old_stock = item.current_price, item.in_stock
    price, in_stock = update_data.extraction.price, update_data.extraction.in_stock
    p_conf, s_conf = update_data.extraction.price_confidence, update_data.extraction.in_stock_confidence

    rejected = False

    if price is not None:
        reject_msg, reject_type = _check_price_rejection(price, old_price, update_data.thresholds, item_id)
        if reject_msg:
            logger.warning(f"Item {item_id}: {reject_msg}")
            item.last_error = reject_msg
            item.error_type = reject_type
            rejected = True
        else:
            _apply_price_update(item, update_data, session)

    if not rejected and in_stock is not None and s_conf >= update_data.thresholds["stock"]:
        item.in_stock = in_stock
        item.in_stock_confidence = s_conf

    old_timestamp = item.last_checked
    item.last_checked = utc_now_naive()
    item.is_refreshing = False
    item.consecutive_failures = 0

    if not rejected:
        if item.last_error and not item.last_error.startswith("Uncertain:"):
            item.last_error = None
            item.error_type = None

        if price is not None and p_conf < update_data.thresholds["price"]:
            item.last_error = (
                f"Low confidence: price found ({price:.2f}) but confidence ({p_conf:.2f}) "
                f"is below threshold ({update_data.thresholds['price']:.2f})"
            )
            item.error_type = ErrorType.LOW_CONFIDENCE

    await session.commit()
    logger.info(
        f"Updated item {item_id}: price={price}, stock={in_stock} "
        f"(last_checked: {old_timestamp} -> {item.last_checked})"
    )
    return old_price, old_stock


def _apply_price_update(item, update_data: UpdateData, session):
    """Apply a valid (non-rejected) price update to the item and history."""
    price = update_data.extraction.price
    in_stock = update_data.extraction.in_stock
    p_conf = update_data.extraction.price_confidence
    s_conf = update_data.extraction.in_stock_confidence

    if p_conf >= update_data.thresholds["price"]:
        old_price = item.current_price
        if (
            old_price
            and (abs(price - old_price) / old_price * 100 > PRICE_CHANGE_THRESHOLD_PERCENT)
            and p_conf < LOW_CONFIDENCE_THRESHOLD
        ):
            item.last_error = f"Uncertain: Large price change with low confidence ({p_conf:.2f})"
            item.error_type = ErrorType.LOW_CONFIDENCE
        else:
            item.last_error = None
            item.error_type = None
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


async def _handle_error(item_id: int, error_msg: str, error_type: str = ErrorType.SCRAPE_FAILED):
    """Log error, update item status, and track consecutive failures."""
    logger.error(f"Error checking item {item_id}: {error_msg}")
    async with database.AsyncSessionLocal() as session:
        result = await session.execute(select(models.Item).where(models.Item.id == item_id))
        if item := result.scalars().first():
            item.is_refreshing = False
            item.last_error = str(error_msg)
            item.error_type = error_type
            item.last_checked = utc_now_naive()

            # Increment consecutive failures
            item.consecutive_failures = (item.consecutive_failures or 0) + 1

            # Fetch max failures threshold
            thresholds = await _get_thresholds(session)
            max_failures = thresholds["max_consecutive_failures"]

            # Auto-deactivate if too many consecutive failures
            if item.consecutive_failures >= max_failures:
                item.is_active = False
                item.error_type = ErrorType.AUTO_DEACTIVATED
                item.last_error = (
                    f"Auto-deactivated after {item.consecutive_failures} consecutive failures. "
                    f"Last error: {error_msg}"
                )
                logger.warning(
                    f"Item {item_id} auto-deactivated after {item.consecutive_failures} consecutive failures"
                )

            await session.commit()


async def _process_single_item_data(item_id: int, session: AsyncSession):
    """Fetch item data and config."""
    item_data, config = await ItemService.get_item_data_for_checking(session, item_id)
    if not item_data:
        return None

    # Pre-fetch thresholds while we have the session
    thresholds = await _get_thresholds(session)

    return item_data, config, thresholds


async def process_item_check(item_id: int, semaphore: asyncio.Semaphore | None = None, is_scheduled: bool = False):
    """Process a single item check with concurrency limit."""
    async with semaphore if semaphore else nullcontext():
        await _execute_check(item_id, is_scheduled=is_scheduled)


async def _execute_check(item_id: int, is_scheduled: bool = False):
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

            # 2. Scrape (outside session is fine — no DB calls)
            scrape_config = ScrapeConfig(
                smart_scroll=config["smart_scroll"],
                scroll_pixels=config["smart_scroll_pixels"],
                text_length=config["text_length"],
                timeout=config["scraper_timeout"],
                jitter=is_scheduled,  # Only jitter for scheduled checks, not manual ones
            )
            screenshot_path, page_text = await ScraperService.scrape_item(
                item_data["url"], item_data["selector"], item_id, scrape_config
            )
            if not screenshot_path:
                raise ScrapeError("Failed to capture screenshot")

            # 3. Analyze with AI — pass last known price for anchoring + URL for currency
            ai_result = await AIService.analyze_image(
                screenshot_path,
                page_text=page_text,
                custom_prompt=item_data.get("custom_prompt"),
                last_known_price=item_data.get("current_price"),
                url=item_data["url"],
            )
            if not ai_result:
                raise AIError("AI analysis failed")
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

    except ScrapeError as e:
        await _handle_error(item_id, str(e), ErrorType.SCRAPE_FAILED)
    except AIError as e:
        await _handle_error(item_id, str(e), ErrorType.AI_FAILED)
    except Exception as e:
        await _handle_error(item_id, str(e))


class ScrapeError(Exception):
    """Raised when scraping fails."""


class AIError(Exception):
    """Raised when AI analysis fails."""


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
        tasks = [process_item_check(item_id, semaphore, is_scheduled=True) for item_id, _, _ in due_items]
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
