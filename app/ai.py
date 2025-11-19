"""
AI-powered image analysis for price extraction.

This module handles all AI provider interactions using litellm,
with robust JSON parsing, validation, and fallback mechanisms.
"""

import asyncio
import base64
import io
import json
import logging
import re
from typing import Any

from litellm import acompletion
from PIL import Image
from pydantic import ValidationError

from app.ai_schema import (
    PROMPT_VERSION,
    AIExtractionMetadata,
    AIExtractionResponse,
    get_extraction_prompt,
    get_repair_prompt,
)
from app.database import SessionLocal

from . import models

# Default configuration (can be overridden by DB settings)
DEFAULT_PROVIDER = "ollama"
DEFAULT_MODEL = "gemma3:4b"
DEFAULT_API_BASE = "http://ollama:11434"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_TOKENS = 300
MAX_TEXT_LENGTH = 10000

logger = logging.getLogger(__name__)


def _process_image(image_path):
    """
    Synchronous image processing function to be run in an executor.
    """
    try:
        with Image.open(image_path) as img:
            # Resize if too large (e.g., max dimension 1024)
            max_size = 1024
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size))
                logger.info(f"Resized image to {img.size}")

            # Convert to RGB if necessary (e.g. for PNGs with alpha)
            if img.mode in ("RGBA", "P"):
                img_to_process = img.convert("RGB")
            else:
                img_to_process = img

            buffered = io.BytesIO()
            img_to_process.save(buffered, format="JPEG", quality=85)
            return base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        logger.error(f"Error encoding image: {e}")
        raise


async def encode_image(image_path):
    """
    Asynchronously encode image by running blocking code in a thread.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _process_image, image_path)


def clean_text(text: str) -> str:
    """
    Cleans the text by removing code blocks, HTML tags, and excessive whitespace.
    """
    if not text:
        return ""

    # Remove code blocks (```...```)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

    # Remove HTML tags (basic)
    text = re.sub(r"<[^>]+>", "", text)

    # Remove non-printable characters (keep newlines and tabs)
    text = re.sub(r"[^\x20-\x7E\n\t]", "", text)

    # Collapse excessive whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def get_ai_config():
    """
    Fetches AI configuration from the database.
    Returns a dict with: provider, model, api_key, api_base, temperature, max_tokens
    """
    session = SessionLocal()
    try:
        settings = session.query(models.Settings).all()
        settings_map = {s.key: s.value for s in settings}

        return {
            "provider": settings_map.get("ai_provider", DEFAULT_PROVIDER),
            "model": settings_map.get("ai_model", DEFAULT_MODEL),
            "api_key": settings_map.get("ai_api_key", ""),
            "api_base": settings_map.get("ai_api_base", DEFAULT_API_BASE),
            "temperature": float(settings_map.get("ai_temperature", str(DEFAULT_TEMPERATURE))),
            "max_tokens": int(settings_map.get("ai_max_tokens", str(DEFAULT_MAX_TOKENS))),
            "enable_json_repair": settings_map.get("enable_json_repair", "true").lower() == "true",
            "enable_multi_sample": settings_map.get("enable_multi_sample", "false").lower() == "true",
            "multi_sample_threshold": float(settings_map.get("multi_sample_confidence_threshold", "0.6")),
        }
    except Exception as e:
        logger.error(f"Error fetching AI config: {e}")
        return {
            "provider": DEFAULT_PROVIDER,
            "model": DEFAULT_MODEL,
            "api_key": "",
            "api_base": DEFAULT_API_BASE,
            "temperature": DEFAULT_TEMPERATURE,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "enable_json_repair": True,
            "enable_multi_sample": False,
            "multi_sample_threshold": 0.6,
        }
    finally:
        session.close()


def parse_and_validate_response(response_text: str) -> AIExtractionResponse:
    """
    Parse and validate AI response against schema.

    Pipeline:
    1. Extract JSON from response (handle markdown code blocks)
    2. Parse JSON
    3. Validate against Pydantic schema (includes normalization and clamping)

    Raises:
        ValidationError: If response doesn't match schema
        json.JSONDecodeError: If JSON is invalid
    """
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find raw JSON object
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = response_text

    # Parse JSON
    data = json.loads(json_str)

    # Validate and normalize through Pydantic
    return AIExtractionResponse(**data)


async def repair_json_response(
    raw_output: str, provider: str, model: str, api_key: str, api_base: str, temperature: float
) -> AIExtractionResponse:
    """
    Attempt to repair invalid JSON using a second LLM call.

    Args:
        raw_output: The raw AI output that failed parsing
        provider: AI provider name
        model: Model identifier
        api_key: API key
        api_base: API base URL
        temperature: Temperature setting

    Returns:
        Validated AIExtractionResponse

    Raises:
        Exception: If repair also fails
    """
    logger.warning("Attempting JSON repair with second LLM call")

    repair_prompt = get_repair_prompt(raw_output)

    # Use a simpler, cheaper model for repair if possible
    # For now, use the same model
    kwargs = {
        "model": model if provider != "ollama" else f"ollama/{model}",
        "messages": [{"role": "user", "content": repair_prompt}],
        "max_tokens": 300,
        "temperature": 0.0,  # Very deterministic for repair
    }

    if api_key:
        kwargs["api_key"] = api_key

    if provider == "ollama":
        kwargs["api_base"] = api_base
        kwargs["format"] = "json"
    elif provider == "openai" and api_base:
        kwargs["api_base"] = api_base

    response = await acompletion(**kwargs)
    repaired_text = response.choices[0].message.content

    # Validate repaired response
    return parse_and_validate_response(repaired_text)


async def call_llm(
    prompt: str,
    image_data_url: str,
    provider: str,
    model: str,
    api_key: str,
    api_base: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """
    Call LLM with structured output settings.

    Returns:
        Raw response text from the model
    """
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        }
    ]

    # Prepare kwargs for litellm
    kwargs: dict[str, Any] = {
        "model": model if provider != "ollama" else f"ollama/{model}",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    if api_key:
        kwargs["api_key"] = api_key

    # Provider-specific structured output features
    if provider == "ollama":
        kwargs["api_base"] = api_base
        kwargs["format"] = "json"  # Force JSON mode for Ollama
    elif provider == "openai":
        # Use OpenAI's JSON mode
        kwargs["response_format"] = {"type": "json_object"}
        if api_base:
            kwargs["api_base"] = api_base
    elif provider == "anthropic":
        # Anthropic doesn't have native JSON mode yet, rely on prompt
        if api_base:
            kwargs["api_base"] = api_base
    # Other providers - rely on prompt engineering
    elif api_base:
        kwargs["api_base"] = api_base

    # Call litellm asynchronously
    logger.info(f"Calling {provider}/{model} (temp={temperature}, max_tokens={max_tokens})")
    response = await acompletion(**kwargs)

    return response.choices[0].message.content


async def analyze_image(
    image_path: str,
    page_text: str = "",
) -> tuple[AIExtractionResponse, AIExtractionMetadata] | None:
    """
    Analyze image and extract price/stock information.

    Args:
        image_path: Path to screenshot
        page_text: Optional webpage text context

    Returns:
        Tuple of (AIExtractionResponse, AIExtractionMetadata) or None on failure
    """
    try:
        # Get AI config
        loop = asyncio.get_running_loop()
        config = await loop.run_in_executor(None, get_ai_config)

        provider = config["provider"]
        model = config["model"]
        api_key = config["api_key"]
        api_base = config["api_base"]
        temperature = config["temperature"]
        max_tokens = config["max_tokens"]
        enable_repair = config["enable_json_repair"]

        logger.info(f"Analyzing image with Provider: {provider}, Model: {model}")

        # Encode image
        base64_image = await encode_image(image_path)
        data_url = f"data:image/jpeg;base64,{base64_image}"

        # Prepare prompt with optional text context
        cleaned_text = ""
        if page_text:
            cleaned_text = clean_text(page_text)
            if len(cleaned_text) > MAX_TEXT_LENGTH:
                cleaned_text = cleaned_text[:MAX_TEXT_LENGTH] + "...(truncated)"
            logger.info(f"Added text context (original: {len(page_text)}, cleaned: {len(cleaned_text)})")

        prompt = get_extraction_prompt(cleaned_text if cleaned_text else None)

        # Call LLM
        response_text = await call_llm(prompt, data_url, provider, model, api_key, api_base, temperature, max_tokens)

        logger.info(f"AI Response: {response_text[:200]}...")

        # Parse and validate response
        repair_used = False
        try:
            extraction_result = parse_and_validate_response(response_text)
        except (ValidationError, json.JSONDecodeError) as e:
            logger.warning(f"Primary parsing failed: {e}")

            if enable_repair:
                try:
                    extraction_result = await repair_json_response(
                        response_text, provider, model, api_key, api_base, temperature
                    )
                    repair_used = True
                    logger.info("JSON repair successful")
                except Exception as repair_error:
                    logger.error(f"JSON repair also failed: {repair_error}")
                    raise
            else:
                raise

        # Create metadata
        metadata = AIExtractionMetadata(
            model_name=model,
            provider=provider,
            prompt_version=PROMPT_VERSION,
            repair_used=repair_used,
            multi_sample=False,
            sample_count=1,
        )

        logger.info(
            f"Extraction successful: price={extraction_result.price} (conf={extraction_result.price_confidence:.2f}), "
            f"stock={extraction_result.in_stock} (conf={extraction_result.in_stock_confidence:.2f})"
        )

        return extraction_result, metadata

    except Exception as e:
        logger.error(f"Error in analyze_image: {e}", exc_info=True)
        return None
