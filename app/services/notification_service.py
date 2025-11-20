from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models, schemas


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
        return {"ok": True}
