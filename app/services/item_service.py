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
        return [
            {
                **item.__dict__,
                "screenshot_url": f"/screenshots/item_{item.id}.png"
                if os.path.exists(f"screenshots/item_{item.id}.png")
                else None,
            }
            for item in items
        ]

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

        if os.path.exists(f"screenshots/item_{item_id}.png"):
            try:
                os.remove(f"screenshots/item_{item_id}.png")
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
            "notification_profile": profile.__dict__ if profile else None,
        }

        config = {
            "smart_scroll": settings.get("smart_scroll_enabled", "false").lower() == "true",
            "smart_scroll_pixels": int(settings.get("smart_scroll_pixels", "350")),
            "text_context_enabled": settings.get("text_context_enabled", "false").lower() == "true",
            "text_length": int(settings.get("text_context_length", "5000"))
            if settings.get("text_context_enabled", "false").lower() == "true"
            else 0,
            "scraper_timeout": int(settings.get("scraper_timeout", "90000")),
        }
        return item_data, config

    @staticmethod
    def get_due_items(db: Session):
        items = db.query(models.Item).filter(models.Item.is_active).all()
        global_interval = int(SettingsService.get_setting_value(db, "refresh_interval_minutes", "60"))
        due_items = []
        now = datetime.now(UTC)

        for item in items:
            if item.is_refreshing:
                continue

            if item.check_interval_minutes:
                interval = item.check_interval_minutes
            elif item.notification_profile and item.notification_profile.check_interval_minutes:
                interval = item.notification_profile.check_interval_minutes
            else:
                interval = global_interval

            # Enforce minimum interval of 5 minutes to prevent loop
            interval = max(interval, 5)

            if not item.last_checked:
                logger.info(f"Item {item.id} due: Never checked (Interval: {interval}m)")
                due_items.append((item.id, interval, -1))
                continue

            last_checked = (
                item.last_checked.replace(tzinfo=UTC) if item.last_checked.tzinfo is None else item.last_checked
            )
            time_since = (now - last_checked).total_seconds() / 60

            if time_since >= interval:
                logger.info(f"Item {item.id} due: Last checked {time_since:.1f}m ago (Interval: {interval}m)")
                due_items.append((item.id, interval, int(time_since)))

        return due_items
