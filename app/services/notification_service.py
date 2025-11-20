from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models, notification_sender, schemas


class NotificationService:
    @staticmethod
    def get_notification_profiles(db: Session):
        return db.query(models.NotificationProfile).all()

    @staticmethod
    def create_notification_profile(db: Session, profile: schemas.NotificationProfileCreate):
        db_profile = models.NotificationProfile(**profile.model_dump())
        db.add(db_profile)
        db.commit()
        db.refresh(db_profile)
        return db_profile

    @staticmethod
    def delete_notification_profile(db: Session, profile_id: int):
        profile = db.query(models.NotificationProfile).filter(models.NotificationProfile.id == profile_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        db.delete(profile)
        db.commit()
        db.delete(profile)
        db.commit()
        return {"ok": True}

    @staticmethod
    def update_notification_profile(db: Session, profile_id: int, profile_data: schemas.NotificationProfileUpdate):
        profile = db.query(models.NotificationProfile).filter(models.NotificationProfile.id == profile_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        for key, value in profile_data.model_dump().items():
            setattr(profile, key, value)

        db.commit()
        db.refresh(profile)
        return profile

    @staticmethod
    async def send_item_notifications(
        item_data: dict,
        price: float | None,
        old_price: float | None,
        in_stock: bool | None,
        old_stock: bool | None,
    ):
        profile = item_data["notification_profile"]
        if not profile:
            return

        if profile["notify_on_price_drop"] and price is not None and old_price is not None:
            if price < old_price:
                drop_percent = ((old_price - price) / old_price) * 100
                if drop_percent >= profile["price_drop_threshold_percent"]:
                    await notification_sender.send_notification(
                        [profile["apprise_url"]],
                        f"Price Drop Alert: {item_data['name']}",
                        f"Price dropped by {drop_percent:.1f}%! Now ${price} (was ${old_price})",
                    )

        if (
            profile["notify_on_target_price"]
            and price is not None
            and item_data["target_price"]
            and price <= item_data["target_price"]
        ):
            await notification_sender.send_notification(
                [profile["apprise_url"]],
                f"Target Price Alert: {item_data['name']}",
                f"Price is ${price} (Target: ${item_data['target_price']})",
            )

        if (
            profile["notify_on_stock_change"]
            and in_stock is not None
            and old_stock is not None
            and in_stock != old_stock
        ):
            status = "In Stock" if in_stock else "Out of Stock"
            await notification_sender.send_notification(
                [profile["apprise_url"]],
                f"Stock Alert: {item_data['name']}",
                f"Item is now {status}",
            )
