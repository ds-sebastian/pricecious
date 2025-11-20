import asyncio
import json
import logging
import re
import time
from typing import Any, TypedDict

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

# Default configuration (can be overridden by DB settings)
DEFAULT_PROVIDER = "ollama"
DEFAULT_MODEL = "gemma3:4b"
DEFAULT_API_BASE = "http://ollama:11434"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_TOKENS = 300
DEFAULT_TIMEOUT = 30  # seconds
MAX_TEXT_LENGTH = 5000  # Will be filtered to ~1500-2000 relevant chars

# Config caching
_config_cache: dict[str, Any] = {"data": None, "timestamp": 0.0}
CONFIG_CACHE_TTL = 60  # seconds

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


MIN_API_KEY_LENGTH = 12


def _sanitize_api_key(key: str) -> str:
    """Redact API key for logging (show first/last 4 chars only)."""
    if not key or len(key) < MIN_API_KEY_LENGTH:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


class AIService:
    @staticmethod
    def get_ai_config() -> AIConfig:
        """
        Fetches AI configuration from the database with caching.
        Returns a dict with: provider, model, api_key, api_base, temperature, max_tokens, timeout
        """
        # Check cache
        now = time.time()
        if _config_cache["data"] and (now - _config_cache["timestamp"]) < CONFIG_CACHE_TTL:
            return _config_cache["data"]  # type: ignore

        # Fetch from DB
        session = SessionLocal()
        try:
            settings = session.query(models.Settings).all()
            settings_map = {s.key: s.value for s in settings}

            config: AIConfig = {
                "provider": settings_map.get("ai_provider", DEFAULT_PROVIDER),
                "model": settings_map.get("ai_model", DEFAULT_MODEL),
                "api_key": settings_map.get("ai_api_key", ""),
                "api_base": settings_map.get("ai_api_base", DEFAULT_API_BASE),
                "temperature": float(settings_map.get("ai_temperature", str(DEFAULT_TEMPERATURE))),
                "max_tokens": int(settings_map.get("ai_max_tokens", str(DEFAULT_MAX_TOKENS))),
                "timeout": int(settings_map.get("ai_timeout", str(DEFAULT_TIMEOUT))),
                "enable_json_repair": settings_map.get("enable_json_repair", "true").lower() == "true",
                "enable_multi_sample": settings_map.get("enable_multi_sample", "false").lower() == "true",
                "multi_sample_threshold": float(settings_map.get("multi_sample_confidence_threshold", "0.6")),
            }

            # Update cache
            _config_cache["data"] = config  # type: ignore
            _config_cache["timestamp"] = now

            return config
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
            }
        finally:
            session.close()

    @staticmethod
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

    @classmethod
    async def repair_json_response(
        cls,
        raw_output: str,
        config: AIConfig,
    ) -> AIExtractionResponse:
        """
        Attempt to repair invalid JSON using a second LLM call.

        Args:
            raw_output: The raw AI output that failed parsing
            config: AI configuration dict

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
            "model": config["model"] if config["provider"] != "ollama" else f"ollama/{config['model']}",
            "messages": [{"role": "user", "content": repair_prompt}],
            "max_tokens": 300,
            "temperature": 0.0,  # Very deterministic for repair
            "timeout": config["timeout"],
        }

        if config["api_key"]:
            kwargs["api_key"] = config["api_key"]

        if config["provider"] == "ollama":
            kwargs["api_base"] = config["api_base"]
            kwargs["format"] = "json"
        elif config["provider"] == "openai" and config["api_base"]:
            kwargs["api_base"] = config["api_base"]

        response = await acompletion(**kwargs)
        repaired_text = response.choices[0].message.content

        # Validate repaired response
        return cls.parse_and_validate_response(repaired_text)

    @staticmethod
    @retry(
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def call_llm(
        prompt: str,
        image_data_url: str,
        config: AIConfig,
    ) -> str:
        """
        Call LLM with structured output settings and retry logic.

        Returns:
            Raw response text from the model

        Raises:
            TimeoutError: If request times out after retries
            ConnectionError: If connection fails after retries
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
            "model": config["model"] if config["provider"] != "ollama" else f"ollama/{config['model']}",
            "messages": messages,
            "max_tokens": config["max_tokens"],
            "temperature": config["temperature"],
            "timeout": config["timeout"],
        }

        if config["api_key"]:
            kwargs["api_key"] = config["api_key"]

        # Provider-specific structured output features
        if config["provider"] == "ollama":
            kwargs["api_base"] = config["api_base"]
            kwargs["format"] = "json"  # Force JSON mode for Ollama
        elif config["provider"] == "openai":
            # Use OpenAI's JSON mode
            kwargs["response_format"] = {"type": "json_object"}
            if config["api_base"]:
                kwargs["api_base"] = config["api_base"]
        elif config["provider"] == "anthropic":
            # Anthropic doesn't have native JSON mode yet, rely on prompt
            if config["api_base"]:
                kwargs["api_base"] = config["api_base"]
        # Other providers - rely on prompt engineering
        elif config["api_base"]:
            kwargs["api_base"] = config["api_base"]

        # Call litellm asynchronously
        sanitized_key = _sanitize_api_key(config["api_key"]) if config["api_key"] else "(none)"
        logger.info(
            f"Calling {config['provider']}/{config['model']} "
            f"(temp={config['temperature']}, max_tokens={config['max_tokens']}, "
            f"timeout={config['timeout']}s, key={sanitized_key})"
        )
        response = await acompletion(**kwargs)

        content = response.choices[0].message.content
        return content or ""

    @classmethod
    async def analyze_image(
        cls,
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
            config = await loop.run_in_executor(None, cls.get_ai_config)

            logger.info(
                f"Analyzing image with Provider: {config['provider']}, "
                f"Model: {config['model']}, Timeout: {config['timeout']}s"
            )

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
            response_text = await cls.call_llm(prompt, data_url, config)

            logger.info(f"AI Response: {response_text[:200]}...")

            # Parse and validate response
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

            # Create metadata
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
