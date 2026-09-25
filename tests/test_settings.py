import pytest
from pydantic import ValidationError

from app import settings
from app.models import Setting


async def test_invalid_stored_values_fall_back_to_defaults(db):
    db.add_all(
        [
            Setting(key="ai_max_tokens", value="NaN"),
            Setting(key="ai_temperature", value="0.3"),
            Setting(key="smart_scroll_enabled", value="true"),
            Setting(key="enable_multi_sample", value="true"),  # retired setting
        ]
    )
    await db.commit()

    loaded = await settings.load(db)

    assert loaded.ai_max_tokens == 1000
    assert loaded.ai_temperature == 0.3
    assert loaded.smart_scroll_enabled is True


@pytest.mark.parametrize(
    ("stored", "thinking", "effort"),
    [
        ({}, False, "low"),
        ({"ai_provider": "openai"}, False, "low"),  # the old default level is now just the default
        ({"ai_provider": "openai", "ai_reasoning_effort": "medium"}, True, "medium"),  # a chosen level keeps thinking
        ({"ai_provider": "openai", "ai_reasoning_effort": "minimal"}, False, "low"),
        ({"ai_provider": "ollama", "ai_reasoning_effort": "high"}, False, "high"),  # never applied to Ollama
        ({"ai_provider": "openai", "ai_reasoning_effort": "high", "ai_thinking": "false"}, False, "high"),
    ],
)
async def test_thinking_carries_over_openai_reasoning_effort(db, stored, thinking, effort):
    db.add_all(Setting(key=key, value=value) for key, value in stored.items())
    await db.commit()

    loaded = await settings.load(db)

    assert (loaded.ai_thinking, loaded.ai_reasoning_effort) == (thinking, effort)


async def test_save_stores_only_changes_as_strings(db):
    await settings.save(db, {"price_outlier_threshold_enabled": True, "ai_model": "llava"})

    stored = dict((await db.execute(Setting.__table__.select())).tuples().all())
    assert stored == {"price_outlier_threshold_enabled": "true", "ai_model": "llava"}


async def test_save_rejects_invalid_values_without_writing(db):
    with pytest.raises(ValidationError):
        await settings.save(db, {"ai_model": "llava", "confidence_threshold_price": 2})
    assert (await settings.load(db)).ai_model == "gemma3:4b"
