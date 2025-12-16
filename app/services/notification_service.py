from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, notification_sender, schemas


class NotificationService:
    @staticmethod
    async def get_notification_profiles(db: AsyncSession):
        result = await db.execute(select(models.NotificationProfile))
        return result.scalars().all()

    @staticmethod
    async def create_notification_profile(db: AsyncSession, profile: schemas.NotificationProfileCreate):
        db_profile = models.NotificationProfile(**profile.model_dump())
        db.add(db_profile)
        await db.commit()
        await db.refresh(db_profile)
        return db_profile

    @staticmethod
    async def delete_notification_profile(db: AsyncSession, profile_id: int):
        result = await db.execute(select(models.NotificationProfile).where(models.NotificationProfile.id == profile_id))
        profile = result.scalars().first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        await db.delete(profile)
        await db.commit()
        return {"ok": True}

    @staticmethod
    async def update_notification_profile(
        db: AsyncSession, profile_id: int, profile_data: schemas.NotificationProfileUpdate
    ):
        result = await db.execute(select(models.NotificationProfile).where(models.NotificationProfile.id == profile_id))
        profile = result.scalars().first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        for key, value in profile_data.model_dump().items():
            setattr(profile, key, value)

        await db.commit()
        await db.refresh(profile)
        return profile

    @staticmethod
    async def send_item_notifications(
        item_data: dict,
        price: float | None,
        old_price: float | None,
        in_stock: bool | None,
        old_stock: bool | None,
    ):
        if not (profile := item_data.get("notification_profile")):
            return

        # Price drop notification
        if (
            profile["notify_on_price_drop"]
            and price is not None
            and old_price is not None
            and price < old_price
            and (drop := (old_price - price) / old_price * 100) >= profile["price_drop_threshold_percent"]
        ):
            await notification_sender.send_notification(
                [profile["apprise_url"]],
                f"Price Drop Alert: {item_data['name']}",
                f"Price dropped by {drop:.1f}%! Now ${price} (was ${old_price})",
            )

        # Target price notification
        if (
            profile["notify_on_target_price"]
            and price is not None
            and (target := item_data.get("target_price"))
            and price <= target
        ):
            await notification_sender.send_notification(
                [profile["apprise_url"]],
                f"Target Price Alert: {item_data['name']}",
                f"Price is ${price} (Target: ${target})",
            )

        # Stock change notification
        if (
            profile["notify_on_stock_change"]
            and in_stock is not None
            and old_stock is not None
            and in_stock != old_stock
        ):
            status = "In Stock" if in_stock else "Out of Stock"
            await notification_sender.send_notification(
                [profile["apprise_url"]], f"Stock Alert: {item_data['name']}", f"Item is now {status}"
            )
