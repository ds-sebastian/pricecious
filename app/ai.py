"""Price and stock extraction from a page screenshot with a vision model (via LiteLLM)."""

import asyncio
import base64
import io
import logging
import re
from urllib.parse import urlparse

import json_repair
import litellm
from PIL import Image
from pydantic import BaseModel, ValidationError, field_validator

from app.settings import AppSettings

litellm.suppress_debug_info = True
logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 1024
TEXT_CONTEXT_CHARS = 1500
OLLAMA_DEFAULT_BASE = "http://ollama:11434"

PROMPT = """Extract the product's price and stock status from the screenshot.

PRICE
- Use the main current price of the product. Ignore crossed-out prices and prices of other products.
- Return a plain number without currency symbols, or null if no price is visible.

STOCK
- true: "Add to Cart", "Buy Now", "In Stock", "Available"
- false: "Out of Stock", "Sold Out", "Unavailable", "Notify Me"
- null: unclear or not shown

CONFIDENCE (0.0 to 1.0): 0.9+ very certain, 0.5-0.8 moderately certain, below 0.5 unsure.

Respond ONLY with JSON:
{{"price": <number or null>, "currency": "{currency}", "in_stock": <true, false, or null>, \
"price_confidence": <0.0-1.0>, "in_stock_confidence": <0.0-1.0>}}"""

_RELEVANT_TEXT = re.compile(
    r"[$€£¥]|\d[\d.,]*\s?(?:usd|eur|gbp|cad)\b|price|cost|sale|msrp|save|discount|add to (?:cart|bag|basket)"
    r"|buy now|purchase|order now|in stock|out of stock|available|sold out|notify me|pre-order|ships|delivery"
    r"|get it by",
    re.IGNORECASE,
)

_TLD_CURRENCY = {
    tld: currency
    for currency, tlds in {
        "GBP": "uk co.uk org.uk",
        "EUR": "eu de fr es it nl be at pt ie fi gr",
        "JPY": "jp co.jp",
        "KRW": "kr co.kr",
        "INR": "in co.in",
        "AUD": "au com.au",
        "BRL": "br com.br",
        "MXN": "mx com.mx",
        "TRY": "tr com.tr",
        "NZD": "nz co.nz",
        "ZAR": "za co.za",
        "CNY": "cn",
        "CAD": "ca",
        "SEK": "se",
        "NOK": "no",
        "DKK": "dk",
        "CHF": "ch",
        "PLN": "pl",
        "CZK": "cz",
        "RUB": "ru",
        "SGD": "sg",
        "HKD": "hk",
        "TWD": "tw",
        "THB": "th",
        "MYR": "my",
        "ILS": "il",
        "AED": "ae",
        "SAR": "sa",
    }.items()
    for tld in tlds.split()
}


class ExtractionError(Exception):
    pass


class Extraction(BaseModel):
    price: float | None = None
    currency: str | None = None
    in_stock: bool | None = None
    price_confidence: float = 0.0
    in_stock_confidence: float = 0.0

    @field_validator("price_confidence", "in_stock_confidence", mode="before")
    @classmethod
    def _clamp(cls, value):
        return 0.0 if value is None else max(0.0, min(1.0, float(value)))

    @field_validator("currency", mode="before")
    @classmethod
    def _currency(cls, value):
        code = value.strip().upper() if isinstance(value, str) else ""
        return code if re.fullmatch(r"[A-Z]{3}", code) else None

    @field_validator("price", mode="before")
    @classmethod
    def _price(cls, value):
        return parse_price(value) if isinstance(value, str) else value

    @field_validator("in_stock", mode="before")
    @classmethod
    def _stock(cls, value):
        if not isinstance(value, str):
            return value
        value = value.strip().lower()
        if value in {"true", "yes", "in stock", "available", "1"}:
            return True
        if value in {"false", "no", "out of stock", "unavailable", "0"}:
            return False
        return None


def parse_price(text: str) -> float | None:
    """Parse '$1,234.56', '1.234,56 €', '12,99' and friends."""
    digits = re.sub(r"[^\d.,]", "", text)
    if not re.search(r"\d", digits):
        return None
    decimal = max(digits.rfind("."), digits.rfind(","))
    if decimal != -1:
        separator = digits[decimal]
        is_thousands = digits.count(separator) > 1 or (
            separator == "," and "." not in digits and len(digits) - decimal - 1 == 3
        )
        if is_thousands:
            decimal = -1
    if decimal == -1:
        return float(re.sub(r"\D", "", digits))
    whole = re.sub(r"\D", "", digits[:decimal]) or "0"
    return float(f"{whole}.{digits[decimal + 1 :]}")


def infer_currency(url: str) -> str:
    labels = (urlparse(url).hostname or "").lower().split(".")
    for size in (2, 1):
        if len(labels) > size and (currency := _TLD_CURRENCY.get(".".join(labels[-size:]))):
            return currency
    return "USD"


def relevant_text(text: str, limit: int = TEXT_CONTEXT_CHARS, window: int = 100) -> str:
    """Keep only the parts of the page text near price and stock keywords."""
    spans: list[list[int]] = []
    for match in _RELEVANT_TEXT.finditer(text):
        start, end = max(0, match.start() - window), min(len(text), match.end() + window)
        if spans and start <= spans[-1][1] + 50:
            spans[-1][1] = max(spans[-1][1], end)
        else:
            spans.append([start, end])
    if not spans:
        return text[:limit]
    return " ... ".join(text[start:end].strip() for start, end in spans)[:limit]


def build_prompt(
    url: str, page_text: str | None = None, custom_prompt: str | None = None, last_price: float | None = None
) -> str:
    currency = infer_currency(url)
    sections = [PROMPT.format(currency=currency)]
    if last_price is not None:
        sections.append(f"Previously seen price: {last_price:.2f} (context only; report what the page shows now).")
    if page_text:
        sections.append(f"Relevant text from the page:\n{relevant_text(page_text)}")
    if custom_prompt and (custom := custom_prompt.replace("{context_section}", "").strip()):
        sections.append(f"Additional instructions:\n{custom.replace('{currency_hint}', currency)}")
    return "\n\n".join(sections)


def parse_response(text: str) -> Extraction:
    data = json_repair.loads(text)
    if isinstance(data, list):
        data = next((entry for entry in data if isinstance(entry, dict)), None)
    if not isinstance(data, dict):
        raise ExtractionError(f"Model did not return JSON: {text[:200]!r}")
    try:
        return Extraction.model_validate(data)
    except ValidationError as exc:
        raise ExtractionError(f"Model returned invalid values: {data}") from exc


def _encode_image(png: bytes) -> str:
    with Image.open(io.BytesIO(png)) as image:
        image.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE))
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode()


async def _call_model(messages: list[dict], settings: AppSettings, json_mode: bool = True) -> str:
    provider = settings.ai_provider
    model = settings.ai_model
    if provider == "ollama" and not model.startswith("ollama/"):
        model = f"ollama/{model}"
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "custom_llm_provider": provider,
        "max_tokens": settings.ai_max_tokens,
        "temperature": settings.ai_temperature,
        "timeout": settings.ai_timeout,
        "num_retries": 2,
        "drop_params": True,
    }
    if settings.ai_api_key:
        kwargs["api_key"] = settings.ai_api_key
    if api_base := settings.ai_api_base or (OLLAMA_DEFAULT_BASE if provider == "ollama" else ""):
        kwargs["api_base"] = api_base
    if provider == "openai":
        kwargs["reasoning_effort"] = settings.ai_reasoning_effort
    if json_mode:
        if provider == "ollama":
            kwargs["format"] = "json"
        elif provider == "openai":
            kwargs["response_format"] = Extraction
        else:
            kwargs["response_format"] = {"type": "json_object"}

    response = await litellm.acompletion(**kwargs)
    return response.choices[0].message.content or ""


async def ask(
    screenshot: bytes,
    settings: AppSettings,
    *,
    url: str,
    page_text: str | None = None,
    custom_prompt: str | None = None,
    last_price: float | None = None,
) -> str:
    """Send the screenshot and prompt to the model and return its raw reply."""
    image = await asyncio.to_thread(_encode_image, screenshot)
    prompt = build_prompt(url, page_text, custom_prompt, last_price)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}},
            ],
        }
    ]
    content = await _call_model(messages, settings)
    if not content:
        # Some models return nothing when forced into JSON mode.
        logger.warning(f"{settings.ai_model} returned an empty response in JSON mode; retrying without it")
        content = await _call_model(messages, settings, json_mode=False)
    if not content:
        raise ExtractionError(f"{settings.ai_model} returned an empty response")
    logger.debug(f"Model response: {content}")
    return content


async def extract(screenshot: bytes, settings: AppSettings, **context) -> Extraction:
    return parse_response(await ask(screenshot, settings, **context))
