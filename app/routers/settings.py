from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import database, schemas
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def get_settings(db: AsyncSession = Depends(database.get_db)):
    return await SettingsService.get_settings(db)


@router.post("", response_model=schemas.SettingsUpdate)
async def update_setting(setting: schemas.SettingsUpdate, db: AsyncSession = Depends(database.get_db)):
    return await SettingsService.update_setting(db, setting)
