from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import database, schemas
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notification-profiles", tags=["notifications"])


@router.get("", response_model=list[schemas.NotificationProfileResponse])
async def get_notification_profiles(db: AsyncSession = Depends(database.get_db)):
    return await NotificationService.get_notification_profiles(db)


@router.post("", response_model=schemas.NotificationProfileResponse)
async def create_notification_profile(
    profile: schemas.NotificationProfileCreate, db: AsyncSession = Depends(database.get_db)
):
    return await NotificationService.create_notification_profile(db, profile)


@router.delete("/{profile_id}")
async def delete_notification_profile(profile_id: int, db: AsyncSession = Depends(database.get_db)):
    return await NotificationService.delete_notification_profile(db, profile_id)


@router.put("/{profile_id}", response_model=schemas.NotificationProfileResponse)
async def update_notification_profile(
    profile_id: int, profile: schemas.NotificationProfileUpdate, db: AsyncSession = Depends(database.get_db)
):
    return await NotificationService.update_notification_profile(db, profile_id, profile)
