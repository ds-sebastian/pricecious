from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, schemas


class SettingsService:
    @staticmethod
    async def get_settings(db: AsyncSession):
        result = await db.execute(select(models.Settings))
        return result.scalars().all()

    @staticmethod
    async def update_setting(db: AsyncSession, setting: schemas.SettingsUpdate):
        result = await db.execute(select(models.Settings).where(models.Settings.key == setting.key))
        db_setting = result.scalars().first()

        if db_setting:
            db_setting.value = setting.value
        else:
            db_setting = models.Settings(key=setting.key, value=setting.value)
            db.add(db_setting)
        await db.commit()
        return db_setting

    @staticmethod
    async def get_setting_value(db: AsyncSession, key: str, default: str | None = None):
        result = await db.execute(select(models.Settings).where(models.Settings.key == key))
        setting = result.scalars().first()
        return setting.value if setting else default

    @staticmethod
    async def get_all_settings(db: AsyncSession) -> dict[str, str]:
        result = await db.execute(select(models.Settings))
        return {s.key: s.value for s in result.scalars().all()}
