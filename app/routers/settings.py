from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import database, schemas
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings(db: Session = Depends(database.get_db)):
    return SettingsService.get_settings(db)


@router.post("", response_model=schemas.SettingsUpdate)
def update_setting(setting: schemas.SettingsUpdate, db: Session = Depends(database.get_db)):
    return SettingsService.update_setting(db, setting)
