import asyncio
import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from app import models, database, ai, scraper, notifications
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def process_item_check(item_id: int):
    """
    Background task to check an item's price/stock.
    Creates its own DB session to ensure thread safety.
    """
    SessionLocal = database.SessionLocal
    loop = asyncio.get_running_loop()

    def get_item_data():
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
                } if profile else None,
            }

            config = {
                "smart_scroll": settings_map.get("smart_scroll_enabled", "false").lower() == "true",
                "smart_scroll_pixels": int(settings_map.get("smart_scroll_pixels", "350")),
                "text_context_enabled": settings_map.get("text_context_enabled", "false").lower() == "true",
                "text_length": int(settings_map.get("text_context_length", "5000")) if settings_map.get("text_context_enabled", "false").lower() == "true" else 0,
                "scraper_timeout": int(settings_map.get("scraper_timeout", "90000")),
            }
            return item_data, config
        finally:
            session.close()

    item_data, config = await loop.run_in_executor(None, get_item_data)

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

        if screenshot_path:
            ai_result = await ai.analyze_image(screenshot_path, page_text=page_text)
            if ai_result:
                extraction, metadata = ai_result
                price = extraction.price
                in_stock = extraction.in_stock
                price_confidence = extraction.price_confidence
                in_stock_confidence = extraction.in_stock_confidence

                # Get confidence thresholds
                def get_thresholds():
                    session = SessionLocal()
                    try:
                        settings_map = {s.key: s.value for s in session.query(models.Settings).all()}
                        return {
                            "price": float(settings_map.get("confidence_threshold_price", "0.5")),
                            "stock": float(settings_map.get("confidence_threshold_stock", "0.5")),
                        }
                    finally:
                        session.close()

                thresholds = await loop.run_in_executor(None, get_thresholds)

                # Update DB
                def update_db():
                    session = SessionLocal()
                    try:
                        item = session.query(models.Item).filter(models.Item.id == item_id).first()
                        if not item:
                            return None, None

                        old_price = item.current_price
                        old_stock = item.in_stock

                        if price is not None:
                            if price_confidence >= thresholds["price"]:
                                # Check for large price change with low confidence
                                if old_price is not None:
                                    price_change_pct = abs(price - old_price) / old_price * 100
                                    if price_change_pct > 20 and price_confidence < 0.7:
                                        item.last_error = f"Uncertain: Large price change ({price_change_pct:.1f}%) with low confidence ({price_confidence:.2f})"
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

                old_price, old_stock = await loop.run_in_executor(None, update_db)

                # Notifications
                profile = item_data["notification_profile"]
                if profile:
                    if profile["notify_on_price_drop"] and price is not None and old_price is not None:
                        if price < old_price:
                            drop_percent = ((old_price - price) / old_price) * 100
                            if drop_percent >= profile["price_drop_threshold_percent"]:
                                await notifications.send_notification(
                                    [profile["apprise_url"]],
                                    f"Price Drop Alert: {item_data['name']}",
                                    f"Price dropped by {drop_percent:.1f}%! Now ${price} (was ${old_price})",
                                )

                    if profile["notify_on_target_price"] and price is not None and item_data["target_price"] and price <= item_data["target_price"]:
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
            else:
                raise Exception("AI analysis failed to return a result")
        else:
            raise Exception("Failed to capture screenshot")

    except Exception as e:
        logger.error(f"Error in process_item_check: {e}")
        def update_db_error():
            session = SessionLocal()
            try:
                item = session.query(models.Item).filter(models.Item.id == item_id).first()
                if item:
                    item.is_refreshing = False
                    item.last_error = str(e)
                    session.commit()
            finally:
                session.close()
        await loop.run_in_executor(None, update_db_error)


async def scheduled_refresh():
    """Background job that runs every minute to check for items due for refresh."""
    logger.info("Heartbeat: Checking for items due for refresh")
    SessionLocal = database.SessionLocal
    loop = asyncio.get_running_loop()

    def get_due_items():
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
                    last_checked_aware = item.last_checked.replace(tzinfo=UTC) if item.last_checked.tzinfo is None else item.last_checked
                    time_since_check = (datetime.now(UTC) - last_checked_aware).total_seconds() / 60
                    if time_since_check >= interval:
                        due_items.append((item.id, interval, int(time_since_check)))
                else:
                    due_items.append((item.id, interval, -1))
            return due_items
        finally:
            db.close()

    try:
        due_items = await loop.run_in_executor(None, get_due_items)
        for item_id, _, _ in due_items:
            await process_item_check(item_id)
    except Exception as e:
        logger.error(f"Error in scheduled refresh: {e}", exc_info=True)
