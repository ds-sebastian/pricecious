from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import database, schemas
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notification-profiles", tags=["notifications"])


@router.get("", response_model=list[schemas.NotificationProfileResponse])
def get_notification_profiles(db: Session = Depends(database.get_db)):
    return NotificationService.get_notification_profiles(db)


@router.post("", response_model=schemas.NotificationProfileResponse)
def create_notification_profile(profile: schemas.NotificationProfileCreate, db: Session = Depends(database.get_db)):
    return NotificationService.create_notification_profile(db, profile)


@router.delete("/{profile_id}")
def delete_notification_profile(profile_id: int, db: Session = Depends(database.get_db)):
    return NotificationService.delete_notification_profile(db, profile_id)


@router.put("/{profile_id}", response_model=schemas.NotificationProfileResponse)
def update_notification_profile(
    profile_id: int, profile: schemas.NotificationProfileUpdate, db: Session = Depends(database.get_db)
):
    return NotificationService.update_notification_profile(db, profile_id, profile)
