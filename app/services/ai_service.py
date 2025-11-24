import asyncio
import json
import logging
import re
from typing import Any, TypedDict

import litellm
from litellm import acompletion
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app import models
from app.ai_schema import (
    PROMPT_VERSION,
    AIExtractionMetadata,
    AIExtractionResponse,
    get_extraction_prompt,
    get_repair_prompt,
)
from app.database import SessionLocal
from app.utils.image import encode_image
from app.utils.text import clean_text

# Suppress verbose litellm logs
litellm.suppress_debug_info = True
litellm.set_verbose = False

# Default configuration
DEFAULT_PROVIDER = "ollama"
DEFAULT_MODEL = "gemma3:4b"
DEFAULT_API_BASE = "http://ollama:11434"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TIMEOUT = 30
MAX_TEXT_LENGTH = 5000
DEFAULT_REASONING_EFFORT = "low"

logger = logging.getLogger(__name__)


class AIConfig(TypedDict):
    provider: str
    model: str
    api_key: str
    api_base: str
    temperature: float
    max_tokens: int
    timeout: int
    enable_json_repair: bool
    enable_multi_sample: bool
    multi_sample_threshold: float
    reasoning_effort: str


MIN_API_KEY_LENGTH = 12


def _sanitize_api_key(key: str) -> str:
    """Redact API key for logging."""
    if not key or len(key) < MIN_API_KEY_LENGTH:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


class AIService:
    @staticmethod
    def get_ai_config() -> AIConfig:
        """Fetches AI configuration from the database."""
        try:
            with SessionLocal() as session:
                settings = session.query(models.Settings).all()
                settings_map = {s.key: s.value for s in settings}

            return {
                "provider": settings_map.get("ai_provider", DEFAULT_PROVIDER),
                "model": settings_map.get("ai_model", DEFAULT_MODEL),
                "api_key": settings_map.get("ai_api_key", ""),
                "api_base": settings_map.get("ai_api_base", DEFAULT_API_BASE),
                "temperature": _safe_float(settings_map.get("ai_temperature"), DEFAULT_TEMPERATURE),
                "max_tokens": _safe_int(settings_map.get("ai_max_tokens"), DEFAULT_MAX_TOKENS),
                "timeout": _safe_int(settings_map.get("ai_timeout"), DEFAULT_TIMEOUT),
                "enable_json_repair": settings_map.get("enable_json_repair", "true").lower() == "true",
                "enable_multi_sample": settings_map.get("enable_multi_sample", "false").lower() == "true",
                "multi_sample_threshold": _safe_float(settings_map.get("multi_sample_confidence_threshold"), 0.6),
                "reasoning_effort": settings_map.get("ai_reasoning_effort", DEFAULT_REASONING_EFFORT),
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
                "timeout": DEFAULT_TIMEOUT,
                "enable_json_repair": True,
                "enable_multi_sample": False,
                "multi_sample_threshold": 0.6,
                "reasoning_effort": DEFAULT_REASONING_EFFORT,
            }

    @staticmethod
    def parse_and_validate_response(response_text: str) -> AIExtractionResponse:
        """Parse and validate AI response against schema."""
        # Extract JSON from markdown code blocks or raw text
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            json_str = json_match.group(0) if json_match else response_text

        return AIExtractionResponse(**json.loads(json_str))

    @staticmethod
    def _prepare_llm_kwargs(config: AIConfig, messages: list[dict], is_repair: bool = False) -> dict[str, Any]:
        """Prepare arguments for litellm based on provider and config."""
        provider = config["provider"]
        model = config["model"]

        # Handle model prefixes
        if provider == "ollama" and not model.startswith("ollama/"):
            model = f"ollama/{model}"
        elif provider == "openrouter" and not model.startswith("openrouter/"):
            model = f"openrouter/{model}"

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": 300 if is_repair else config["max_tokens"],
            "temperature": 0.0 if is_repair else config["temperature"],
            "timeout": config["timeout"],
            "drop_params": True,
        }

        if config["api_key"]:
            kwargs["api_key"] = config["api_key"]

        # Provider-specific settings
        if provider == "ollama":
            kwargs["api_base"] = config["api_base"]
            kwargs["format"] = "json"
        elif provider == "openai":
            if not is_repair:
                kwargs["response_format"] = AIExtractionResponse
            if config["api_base"]:
                kwargs["api_base"] = config["api_base"]
            kwargs["reasoning_effort"] = config["reasoning_effort"]
        elif provider == "openrouter":
            if config["api_base"]:
                kwargs["api_base"] = config["api_base"]
            kwargs["extra_headers"] = {
                "HTTP-Referer": "https://github.com/ds-sebastian/pricecious",
                "X-Title": "Pricecious",
            }
        elif config["api_base"]:
            kwargs["api_base"] = config["api_base"]

        return kwargs

    @classmethod
    async def repair_json_response(cls, raw_output: str, config: AIConfig) -> AIExtractionResponse:
        """Attempt to repair invalid JSON using a second LLM call."""
        logger.warning("Attempting JSON repair with second LLM call")

        messages = [{"role": "user", "content": get_repair_prompt(raw_output)}]
        kwargs = cls._prepare_llm_kwargs(config, messages, is_repair=True)

        try:
            response = await acompletion(**kwargs)
            repaired_text = response.choices[0].message.content
            return cls.parse_and_validate_response(repaired_text)
        except Exception as e:
            if "LLM Provider NOT provided" in str(e):
                logger.error(f"Configuration Error: Model '{config['model']}' not supported by '{config['provider']}'")
            raise

    @staticmethod
    @retry(
        retry=retry_if_exception_type((TimeoutError, ConnectionError, ValueError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def call_llm(prompt: str, image_data_url: str, config: AIConfig) -> str:
        """Call LLM with structured output settings and retry logic."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        ]

        kwargs = AIService._prepare_llm_kwargs(config, messages)

        sanitized_key = _sanitize_api_key(config.get("api_key", ""))
        logger.info(
            f"Calling {config['provider']}/{config['model']} "
            f"(temp={kwargs['temperature']}, max_tokens={kwargs['max_tokens']}, "
            f"timeout={kwargs['timeout']}s, key={sanitized_key})"
        )

        try:
            response = await acompletion(**kwargs)
            logger.debug(f"LLM Response Metadata: {response}")

            content = response.choices[0].message.content
            if not content:
                finish_reason = response.choices[0].finish_reason
                raise ValueError(f"Empty response from LLM (finish_reason: {finish_reason})")

            return content
        except Exception as e:
            if "LLM Provider NOT provided" in str(e):
                logger.error(f"Configuration Error: Model '{config['model']}' not supported by '{config['provider']}'")
            raise

    @classmethod
    async def analyze_image(
        cls,
        image_path: str,
        page_text: str = "",
    ) -> tuple[AIExtractionResponse, AIExtractionMetadata] | None:
        """Analyze image and extract price/stock information."""
        try:
            loop = asyncio.get_running_loop()
            config = await loop.run_in_executor(None, cls.get_ai_config)

            logger.info(f"Analyzing image with {config['provider']}/{config['model']}")

            base64_image = await encode_image(image_path)
            data_url = f"data:image/jpeg;base64,{base64_image}"

            cleaned_text = ""
            if page_text:
                cleaned_text = clean_text(page_text)
                if len(cleaned_text) > MAX_TEXT_LENGTH:
                    cleaned_text = cleaned_text[:MAX_TEXT_LENGTH] + "...(truncated)"
                logger.info(f"Added text context (original: {len(page_text)}, cleaned: {len(cleaned_text)})")

            prompt = get_extraction_prompt(cleaned_text if cleaned_text else None)
            response_text = await cls.call_llm(prompt, data_url, config)
            logger.info(f"AI Response: {response_text[:200]}...")

            repair_used = False
            try:
                extraction_result = cls.parse_and_validate_response(response_text)
            except (ValidationError, json.JSONDecodeError) as e:
                logger.warning(f"Primary parsing failed: {e}")
                if config["enable_json_repair"]:
                    try:
                        extraction_result = await cls.repair_json_response(response_text, config)
                        repair_used = True
                        logger.info("JSON repair successful")
                    except Exception as repair_error:
                        logger.error(f"JSON repair also failed: {repair_error}")
                        raise
                else:
                    raise

            metadata = AIExtractionMetadata(
                model_name=config["model"],
                provider=config["provider"],
                prompt_version=PROMPT_VERSION,
                repair_used=repair_used,
                multi_sample=False,
                sample_count=1,
            )

            logger.info(
                f"Extraction successful: price={extraction_result.price} "
                f"(conf={extraction_result.price_confidence:.2f}), "
                f"stock={extraction_result.in_stock} (conf={extraction_result.in_stock_confidence:.2f})"
            )

            return extraction_result, metadata

        except Exception as e:
            logger.error(f"Error in analyze_image: {e}", exc_info=True)
            return None
