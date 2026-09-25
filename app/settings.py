"""User-editable settings, stored as strings in the `settings` table."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Setting

SECRET_MASK = "********"
SECRET_KEYS = {"ai_api_key"}


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ai_provider: Literal["ollama", "openai", "anthropic", "gemini", "openrouter"] = "ollama"
    ai_model: str = "gemma3:4b"
    ai_api_key: str = ""
    ai_api_base: str = ""
    ai_temperature: float = Field(0.1, ge=0, le=2)
    ai_max_tokens: int = Field(1000, ge=16)
    ai_timeout: int = Field(30, ge=1)
    ai_reasoning_effort: Literal["minimal", "low", "medium", "high"] = "low"

    confidence_threshold_price: float = Field(0.5, ge=0, le=1)
    confidence_threshold_stock: float = Field(0.5, ge=0, le=1)
    price_outlier_threshold_enabled: bool = False
    price_outlier_threshold_percent: float = Field(500, gt=0)
    price_min_floor: float = Field(0.01, ge=0)
    price_max_ceiling: float = Field(100_000, gt=0)
    max_consecutive_failures: int = Field(20, ge=1)
    skip_unchanged_pages: bool = True

    smart_scroll_enabled: bool = False
    smart_scroll_pixels: int = Field(350, ge=0)
    text_context_enabled: bool = False
    text_context_length: int = Field(5000, ge=0)
    scraper_timeout: int = Field(90_000, ge=1000)

    refresh_interval_minutes: int = Field(60, ge=1)
    forecasting_interval_hours: int = Field(24, ge=1)


def _parse(raw: dict[str, Any]) -> AppSettings:
    """Validate stored values, falling back to defaults for any that are invalid."""
    data = {k: v for k, v in raw.items() if k in AppSettings.model_fields}
    while True:
        try:
            return AppSettings.model_validate(data)
        except ValidationError as exc:
            for error in exc.errors():
                data.pop(error["loc"][0], None)


def _serialize(value: Any) -> str:
    return str(value).lower() if isinstance(value, bool) else str(value)


async def load(db: AsyncSession) -> AppSettings:
    rows = await db.execute(select(Setting.key, Setting.value))
    return _parse(dict(rows.tuples().all()))


def merge(current: AppSettings, changes: dict[str, Any]) -> AppSettings:
    """Apply a partial update without saving it. Raises ValidationError on bad input."""
    return AppSettings.model_validate(current.model_dump() | _unmasked(changes))


async def save(db: AsyncSession, changes: dict[str, Any]) -> AppSettings:
    """Validate and persist a partial update. Raises ValidationError on bad input."""
    updated = merge(await load(db), changes)
    for key in _unmasked(changes).keys() & AppSettings.model_fields.keys():
        await db.merge(Setting(key=key, value=_serialize(getattr(updated, key))))
    await db.commit()
    return updated


def _unmasked(changes: dict[str, Any]) -> dict[str, Any]:
    """Drop secrets sent back as the mask: the client never saw them, so they're unchanged."""
    return {k: v for k, v in changes.items() if not (k in SECRET_KEYS and v == SECRET_MASK)}


def public(settings: AppSettings) -> dict[str, Any]:
    data = settings.model_dump()
    for key in SECRET_KEYS:
        data[key] = SECRET_MASK if data[key] else ""
    return data
