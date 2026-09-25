from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app import ai
from app.ai import Extraction, ExtractionError, build_prompt, infer_currency, parse_price, parse_response
from app.settings import AppSettings


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$1,234.56", 1234.56),
        ("1.234,56 €", 1234.56),
        ("12,99", 12.99),
        ("1,234", 1234.0),
        ("1.234.567", 1234567.0),
        ("£ 49", 49.0),
        (".99", 0.99),
        ("free", None),
        ("", None),
    ],
)
def test_parse_price(text, expected):
    assert parse_price(text) == expected


def test_extraction_normalizes_model_output():
    extraction = Extraction.model_validate(
        {"price": "$1,299.00", "in_stock": "Out of Stock", "price_confidence": 1.7, "in_stock_confidence": None}
    )
    assert extraction.price == 1299.0
    assert extraction.in_stock is False
    assert extraction.price_confidence == 1.0
    assert extraction.in_stock_confidence == 0.0
    assert Extraction(in_stock="maybe").in_stock is None


@pytest.mark.parametrize(
    "text",
    [
        '```json\n{"price": 19.99, "in_stock": true, "price_confidence": 0.9}\n```',
        'Sure! {"price": 19.99, "in_stock": true, "price_confidence": 0.9,}',
        '[{"price": 19.99, "in_stock": true, "price_confidence": 0.9}]',
    ],
)
def test_parse_response_repairs_common_mistakes(text):
    extraction = parse_response(text)
    assert (extraction.price, extraction.in_stock, extraction.price_confidence) == (19.99, True, 0.9)


@pytest.mark.parametrize("text", ["no json here", "[1, 2]", '{"price_confidence": "very"}'])
def test_parse_response_rejects_garbage(text):
    with pytest.raises(ExtractionError):
        parse_response(text)


@pytest.mark.parametrize(
    ("url", "currency"),
    [
        ("https://www.amazon.co.uk/dp/1", "GBP"),
        ("https://shop.de/x", "EUR"),
        ("https://www.amazon.com.au/x", "AUD"),
        ("https://store.co.jp/x", "JPY"),
        ("https://example.com/x", "USD"),
        ("https://uk.example.com/x", "USD"),
        ("not a url", "USD"),
    ],
)
def test_infer_currency(url, currency):
    assert infer_currency(url) == currency


def test_prompt_includes_context_and_appends_custom_instructions():
    prompt = build_prompt(
        "https://shop.de/item",
        page_text="Header " * 400 + "Price: 19,99 € In Stock " + "Footer " * 400,
        custom_prompt="Ignore the refurbished price. {context_section}",
        last_price=21.5,
    )
    assert '"currency": "EUR"' in prompt
    assert "Previously seen price: 21.50" in prompt
    assert "19,99 € In Stock" in prompt
    assert len(prompt) < 3500  # page text was trimmed to the relevant part
    assert prompt.endswith("Additional instructions:\nIgnore the refurbished price.")
    assert "Respond ONLY with JSON" in prompt  # custom instructions no longer replace the format rules


def test_relevant_text_falls_back_to_start_of_page():
    assert ai.relevant_text("nothing useful here", limit=7) == "nothing"


def _response(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


async def test_extract_retries_without_json_mode_when_response_is_empty(monkeypatch, png):
    completion = AsyncMock(side_effect=[_response(""), _response('{"price": 5, "price_confidence": 0.8}')])
    monkeypatch.setattr(ai.litellm, "acompletion", completion)

    extraction = await ai.extract(png, AppSettings(), url="https://example.com")

    assert extraction.price == 5
    first, second = (call.kwargs for call in completion.await_args_list)
    assert first["format"] == "json" and "format" not in second
    assert first["model"] == "ollama/gemma3:4b"
    assert first["api_base"] == ai.OLLAMA_DEFAULT_BASE


async def test_extract_fails_when_model_stays_silent(monkeypatch, png):
    monkeypatch.setattr(ai.litellm, "acompletion", AsyncMock(return_value=_response(None)))
    with pytest.raises(ExtractionError, match="empty response"):
        await ai.extract(png, AppSettings(), url="https://example.com")


async def test_openai_uses_structured_output_and_no_ollama_base(monkeypatch, png):
    completion = AsyncMock(return_value=_response('{"price": 5}'))
    monkeypatch.setattr(ai.litellm, "acompletion", completion)

    await ai.extract(png, AppSettings(ai_provider="openai", ai_model="gpt-5-mini", ai_api_key="k"), url="https://x.com")

    kwargs = completion.await_args.kwargs
    assert kwargs["response_format"] is Extraction
    assert kwargs["reasoning_effort"] == "low"
    assert kwargs["api_key"] == "k"
    assert "api_base" not in kwargs
