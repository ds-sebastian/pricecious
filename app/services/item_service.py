import logging
import os
from datetime import UTC, datetime

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app import models, schemas
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
