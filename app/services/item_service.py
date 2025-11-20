import logging
import os
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.services.settings_service import SettingsService
from app.url_validation import URLValidationError, validate_url

logger = logging.getLogger(__name__)


class ItemService:
    @staticmethod
    def get_items(db: Session):
        items = db.query(models.Item).all()
        # Manually inject screenshot URL since it's not in DB
        response_items = []
        for item in items:
            item_dict = item.__dict__
            item_dict["screenshot_url"] = schemas.ItemResponse.resolve_screenshot_url(item.id)
            response_items.append(item_dict)
        return response_items

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
        logger.info(f"Item created with ID: {db_item.id}")
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

        # Delete screenshot if exists
        try:
            if os.path.exists(f"screenshots/item_{item_id}.png"):
                os.remove(f"screenshots/item_{item_id}.png")
        except Exception as e:
            logger.error(f"Error deleting screenshot: {e}")

        db.delete(item)
        db.commit()
        return {"ok": True}

    @staticmethod
    def get_item(db: Session, item_id: int):
        item = db.query(models.Item).filter(models.Item.id == item_id).first()
        if not item:
            return None
        return item

    @staticmethod
    def get_item_data_for_checking(db: Session, item_id: int):
        item = db.query(models.Item).filter(models.Item.id == item_id).first()
        if not item:
            return None, None

        profile = item.notification_profile
        settings_map = {s.key: s.value for s in db.query(models.Settings).all()}

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

    @staticmethod
    def get_due_items(db: Session):
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
