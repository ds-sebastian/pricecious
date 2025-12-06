import logging
import os
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import database, models, schemas
from app.services.settings_service import SettingsService
from app.url_validation import URLValidationError, validate_url

logger = logging.getLogger(__name__)


class ItemService:
    @staticmethod
    def get_items(db: Session):
        items = db.query(models.Item).all()
        global_interval = int(SettingsService.get_setting_value(db, "refresh_interval_minutes", "60"))

        result = []
        for item in items:
            # Determine interval
            if item.check_interval_minutes:
                interval = item.check_interval_minutes
            elif item.notification_profile and item.notification_profile.check_interval_minutes:
                interval = item.notification_profile.check_interval_minutes
            else:
                interval = global_interval

            interval = max(interval, 5)

            next_check = None
            if item.last_checked:
                last_checked = item.last_checked
                if last_checked.tzinfo is not None:
                    last_checked = last_checked.astimezone().replace(tzinfo=None)
                next_check = last_checked + timedelta(minutes=interval)

            item_dict = {k: v for k, v in item.__dict__.items() if not k.startswith("_sa_")}

            result.append(
                {
                    **item_dict,
                    "screenshot_url": f"/screenshots/item_{item.id}.png",
                    "next_check": next_check,
                    "interval": interval,
                }
            )

        return result

    @staticmethod
    def create_item(db: Session, item: schemas.ItemCreate):
        logger.info(f"Creating item: {item.name} - {item.url}")
        try:
            validate_url(item.url)
        except URLValidationError as e:
            raise HTTPException(status_code=400, detail=f"Invalid URL: {e}") from e

        db_item = models.Item(**item.model_dump())
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item

    @staticmethod
    def update_item(db: Session, item_id: int, item_update: schemas.ItemCreate):
        db_item = db.query(models.Item).filter(models.Item.id == item_id).first()
        if not db_item:
            raise HTTPException(status_code=404, detail="Item not found")

        for key, value in item_update.model_dump().items():
            setattr(db_item, key, value)

        db.commit()
        db.refresh(db_item)
        return db_item

    @staticmethod
    def delete_item(db: Session, item_id: int):
        item = db.query(models.Item).filter(models.Item.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        # Clean up screenshot if it exists (best effort)
        screenshot_path = f"screenshots/item_{item_id}.png"
        if os.path.exists(screenshot_path):
            try:
                os.remove(screenshot_path)
            except OSError:
                pass

        db.delete(item)
        db.commit()
        return {"ok": True}

    @staticmethod
    def get_item(db: Session, item_id: int):
        return db.query(models.Item).filter(models.Item.id == item_id).first()

    @staticmethod
    def get_item_data_for_checking(db: Session, item_id: int):
        item = db.query(models.Item).filter(models.Item.id == item_id).first()
        if not item:
            return None, None

        settings = {s.key: s.value for s in db.query(models.Settings).all()}
        profile = item.notification_profile

        item_data = {
            "id": item.id,
            "url": item.url,
            "selector": item.selector,
            "name": item.name,
            "current_price": item.current_price,
            "in_stock": item.in_stock,
            "target_price": item.target_price,
            "custom_prompt": item.custom_prompt,
            "notification_profile": profile.__dict__ if profile else None,
        }

        # Parse settings with defaults
        smart_scroll = settings.get("smart_scroll_enabled", "false").lower() == "true"
        text_context = settings.get("text_context_enabled", "false").lower() == "true"

        config = {
            "smart_scroll": smart_scroll,
            "smart_scroll_pixels": int(settings.get("smart_scroll_pixels", "350")),
            "text_length": int(settings.get("text_context_length", "5000")) if text_context else 0,
            "scraper_timeout": int(settings.get("scraper_timeout", "90000")),
        }
        return item_data, config

    @staticmethod
    def get_due_items():
        """Get items due for refresh. Creates and manages its own session."""
        with database.SessionLocal() as db:
            items = db.query(models.Item).filter(models.Item.is_active).all()
            global_interval = int(SettingsService.get_setting_value(db, "refresh_interval_minutes", "60"))
            due_items = []
            now = datetime.now()

            for item in items:
                if item.is_refreshing:
                    continue

                # Determine interval
                if item.check_interval_minutes:
                    interval = item.check_interval_minutes
                elif item.notification_profile and item.notification_profile.check_interval_minutes:
                    interval = item.notification_profile.check_interval_minutes
                else:
                    interval = global_interval

                # Enforce minimum interval of 5 minutes
                interval = max(interval, 5)

                # Check if due
                if not item.last_checked:
                    logger.info(f"Item {item.id} due: Never checked (Interval: {interval}m)")
                    due_items.append((item.id, interval, -1))
                    continue

                # Use naive comparison (Local Time) to match DB storage
                last_checked = item.last_checked
                if last_checked.tzinfo is not None:
                    # If somehow we get an aware datetime, convert to naive local
                    last_checked = last_checked.astimezone().replace(tzinfo=None)

                # Calculate time since last check
                time_since = (now - last_checked).total_seconds() / 60

                if time_since >= interval:
                    logger.info(f"Item {item.id} due: Last checked {time_since:.1f}m ago (Interval: {interval}m)")
                    due_items.append((item.id, interval, int(time_since)))

            return due_items

    @staticmethod
    def get_analytics_data(db: Session, item_id: int, std_dev_threshold: float | None = None, days_back: int | None = None):
        item = db.query(models.Item).filter(models.Item.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        history_query = (
            db.query(models.PriceHistory)
            .filter(models.PriceHistory.item_id == item_id)
            .order_by(models.PriceHistory.timestamp.asc())
        )

        if days_back:
            start_date = datetime.now() - timedelta(days=days_back)
            history_query = history_query.filter(models.PriceHistory.timestamp >= start_date)
        
        history_records = history_query.all()

        if not history_records:
            return {
                "item_id": item.id,
                "item_name": item.name,
                "stats": {
                    "min_price": 0.0,
                    "max_price": 0.0,
                    "avg_price": 0.0,
                    "std_dev": 0.0,
                    "latest_price": item.current_price or 0.0,
                    "price_change_24h": 0.0,
                },
                "history": [],
            }

        prices = [h.price for h in history_records]

        # Basic Statistics
        import statistics

        try:
            mean = statistics.mean(prices)
            stdev = statistics.stdev(prices) if len(prices) > 1 else 0.0
        except statistics.StatisticsError:
            mean = 0.0
            stdev = 0.0

        min_price = min(prices)
        max_price = max(prices)
        latest_price = prices[-1]

        # Calculate 24h change
        yesterday = datetime.now() - timedelta(days=1)
        # Find price closest to 24h ago
        price_24h_ago = None
        for h in reversed(history_records):
            if h.timestamp <= yesterday:
                price_24h_ago = h.price
                break

        price_change = 0.0
        if price_24h_ago:
            price_change = ((latest_price - price_24h_ago) / price_24h_ago) * 100

        # Outlier Filtering
        final_history = history_records
        if std_dev_threshold and stdev > 0:
            lower_bound = mean - (std_dev_threshold * stdev)
            upper_bound = mean + (std_dev_threshold * stdev)
            final_history = [h for h in history_records if lower_bound <= h.price <= upper_bound]
            # Recalculate basic stats for the filtered set?
            # Usually "stats" show the raw data stats, but the "graph" might show filtered.
            # But the user wants to see stats OF the graph.
            # Let's keep stats based on RAW data (true history) but return FILTERED history points.
            # Or maybe provide both?
            # The prompt says "default filter for a threshold ... to have multiple products show on the same chart"
            # I will return the filtered history but the stats of the FULL dataset so they know what "Normal" is?
            # actually better to return stats of the filtered dataset if that's what's being visualized.
            # But standard deviation OF the filtered dataset is circular/different.
            # Let's return stats of the RAW data, and let the frontend show the filtered points.

        return {
            "item_id": item.id,
            "item_name": item.name,
            "stats": {
                "min_price": min_price,
                "max_price": max_price,
                "avg_price": round(mean, 2),
                "std_dev": round(stdev, 2),
                "latest_price": latest_price,
                "price_change_24h": round(price_change, 2),
            },
            "history": final_history,
        }
