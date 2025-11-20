from sqlalchemy.orm import Session

from app import models, schemas


class SettingsService:
    @staticmethod
    def get_settings(db: Session):
        return db.query(models.Settings).all()

    @staticmethod
    def update_setting(db: Session, setting: schemas.SettingsUpdate):
        db_setting = db.query(models.Settings).filter(models.Settings.key == setting.key).first()
        if db_setting:
            db_setting.value = setting.value
        else:
            db_setting = models.Settings(key=setting.key, value=setting.value)
            db.add(db_setting)
        db.commit()
        return db_setting

    @staticmethod
    def get_setting_value(db: Session, key: str, default: str | None = None):
        setting = db.query(models.Settings).filter(models.Settings.key == key).first()
        return setting.value if setting else default
