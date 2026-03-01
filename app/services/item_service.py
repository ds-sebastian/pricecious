import logging
import os
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import database, models, schemas
from app.services.settings_service import SettingsService
from app.url_validation import URLValidationError, validate_url

logger = logging.getLogger(__name__)


class ItemService:
    @staticmethod
    async def get_items(db: AsyncSession) -> list[dict]:
        """Fetch all items with computed next_check times."""
        result = await db.execute(select(models.Item).options(selectinload(models.Item.notification_profile)))
        items = result.scalars().all()

        global_interval = int(await SettingsService.get_setting_value(db, "refresh_interval_minutes", "60"))

        return [ItemService._enrich_item(item, global_interval) for item in items]

    @staticmethod
    def _enrich_item(item: models.Item, global_interval: int) -> dict:
        """Add computed fields to item dictionary."""
        profile_int = item.notification_profile.check_interval_minutes if item.notification_profile else None
        interval = ItemService._get_effective_interval(item.check_interval_minutes, profile_int, global_interval)

        next_check = None
        if item.last_checked:
            last_checked = item.last_checked.replace(tzinfo=UTC) if not item.last_checked.tzinfo else item.last_checked
            next_check = last_checked + timedelta(minutes=interval)

        # Efficient dict creation skipping sqlalchemy internal state
        data = {k: v for k, v in item.__dict__.items() if not k.startswith("_")}
        data.update(
            {
                "screenshot_url": f"/screenshots/item_{item.id}.png",
                "next_check": next_check,
                "interval": interval,
                "notification_profile": item.notification_profile,
            }
        )
        return data

    @staticmethod
    async def create_item(db: AsyncSession, item: schemas.ItemCreate) -> models.Item:
        logger.info(f"Creating item: {item.name} - {item.url}")
        try:
            validate_url(item.url)
        except URLValidationError as e:
            raise HTTPException(status_code=400, detail=f"Invalid URL: {e}") from e

        db_item = models.Item(**item.model_dump())
        db.add(db_item)
        await db.commit()
        await db.refresh(db_item)
        return db_item

    @staticmethod
    async def update_item(db: AsyncSession, item_id: int, item_update: schemas.ItemCreate) -> models.Item:
        db_item = await db.get(models.Item, item_id)
        if not db_item:
            raise HTTPException(status_code=404, detail="Item not found")

        try:
            validate_url(item_update.url)
        except URLValidationError as e:
            raise HTTPException(status_code=400, detail=f"Invalid URL: {e}") from e

        for key, value in item_update.model_dump().items():
            setattr(db_item, key, value)

        await db.commit()
        await db.refresh(db_item)
        return db_item

    @staticmethod
    async def delete_item(db: AsyncSession, item_id: int) -> dict[str, bool]:
        item = await db.get(models.Item, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        # Best effort screenshot cleanup
        try:
            path = f"screenshots/item_{item_id}.png"
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

        await db.delete(item)
        await db.commit()
        return {"ok": True}

    @staticmethod
    async def get_item(db: AsyncSession, item_id: int) -> models.Item | None:
        return await db.get(models.Item, item_id)

    @staticmethod
    async def get_item_data_for_checking(db: AsyncSession, item_id: int) -> tuple[dict | None, dict | None]:
        result = await db.execute(
            select(models.Item).options(selectinload(models.Item.notification_profile)).where(models.Item.id == item_id)
        )
        item = result.scalars().first()
        if not item:
            return None, None

        settings = await SettingsService.get_all_settings(db)

        # Parse settings
        smart_scroll = settings.get("smart_scroll_enabled", "false").lower() == "true"
        text_context = settings.get("text_context_enabled", "false").lower() == "true"

        config = {
            "smart_scroll": smart_scroll,
            "smart_scroll_pixels": int(settings.get("smart_scroll_pixels", "350")),
            "text_length": int(settings.get("text_context_length", "5000")) if text_context else 0,
            "scraper_timeout": int(settings.get("scraper_timeout", "90000")),
        }

        # Construct item dict manually to ensure flat structure/expected keys
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

        return item_data, config

    @staticmethod
    def _get_effective_interval(item_int: int | None, profile_int: int | None, global_int: int) -> int:
        """Calculate effective check interval based on hierarchy: Item > Profile > Global."""
        return max((item_int or profile_int or global_int), 5)

    @staticmethod
    async def get_due_items() -> list[tuple[int, int, int]]:
        """
        Get items due for refresh.
        Returns list of (item_id, interval, overdue_minutes).
        """
        async with database.AsyncSessionLocal() as db:
            global_int = int(await SettingsService.get_setting_value(db, "refresh_interval_minutes", "60"))

            stmt = (
                select(
                    models.Item.id,
                    models.Item.check_interval_minutes,
                    models.Item.last_checked,
                    models.NotificationProfile.check_interval_minutes.label("profile_interval"),
                )
                .outerjoin(models.Item.notification_profile)
                .where(models.Item.is_active == True)  # noqa: E712
                .where(models.Item.is_refreshing == False)  # noqa: E712
            )

            rows = (await db.execute(stmt)).all()
            now = datetime.now(UTC)
            due_items = []

            for row in rows:
                interval = ItemService._get_effective_interval(
                    row.check_interval_minutes, row.profile_interval, global_int
                )

                if not row.last_checked:
                    due_items.append((row.id, interval, -1))
                    continue

                last_checked = row.last_checked.replace(tzinfo=UTC) if not row.last_checked.tzinfo else row.last_checked
                time_since = (now - last_checked).total_seconds() / 60

                if time_since >= interval:
                    due_items.append((row.id, interval, int(time_since)))

            return due_items
