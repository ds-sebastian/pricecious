import cachetools
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, schemas

# Cache all settings for 30 seconds — avoids O(N) DB queries per refresh cycle
_settings_cache: cachetools.TTLCache = cachetools.TTLCache(maxsize=1, ttl=30)
_SETTINGS_CACHE_KEY = "all_settings"


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

        # Invalidate settings cache on write
        _settings_cache.clear()

        return db_setting

    @staticmethod
    async def get_setting_value(db: AsyncSession, key: str, default: str | None = None):
        all_settings = await SettingsService.get_all_settings(db)
        return all_settings.get(key, default)

    @staticmethod
    async def get_all_settings(db: AsyncSession) -> dict[str, str]:
        if _SETTINGS_CACHE_KEY in _settings_cache:
            return _settings_cache[_SETTINGS_CACHE_KEY]

        result = await db.execute(select(models.Settings))
        settings = {s.key: s.value for s in result.scalars().all()}
        _settings_cache[_SETTINGS_CACHE_KEY] = settings
        return settings
