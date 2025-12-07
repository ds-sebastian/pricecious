import json
import logging
import re
from typing import TypedDict

import litellm
from litellm import acompletion
from pydantic import ValidationError
from sqlalchemy import select
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app import models
from app.ai_schema import (
    PROMPT_VERSION,
    AIExtractionMetadata,
    AIExtractionResponse,
    get_extraction_prompt,
    get_repair_prompt,
)
from app.database import AsyncSessionLocal
from app.utils.image import encode_image
from app.utils.text import clean_text

# Configure litellm
litellm.suppress_debug_info = True
litellm.set_verbose = False

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


DEFAULT_CONFIG: AIConfig = {
    "provider": "ollama",
    "model": "gemma3:4b",
    "api_key": "",
    "api_base": "http://ollama:11434",
    "temperature": 0.1,
    "max_tokens": 1000,
    "timeout": 30,
    "enable_json_repair": True,
    "enable_multi_sample": False,
    "multi_sample_threshold": 0.6,
    "reasoning_effort": "low",
}


class AIService:
    @staticmethod
    async def get_ai_config() -> AIConfig:
        """Fetch AI configuration from the database."""
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(models.Settings))
                settings = {s.key: s.value for s in result.scalars().all()}

            def get(key, default, type_=str):
                val = settings.get(key)
                if val is None:
                    return default
                try:
                    return type_(val)
                except ValueError:
                    return default

            return {
                "provider": get("ai_provider", DEFAULT_CONFIG["provider"]),
                "model": get("ai_model", DEFAULT_CONFIG["model"]),
                "api_key": get("ai_api_key", ""),
                "api_base": get("ai_api_base", DEFAULT_CONFIG["api_base"]),
                "temperature": get("ai_temperature", DEFAULT_CONFIG["temperature"], float),
                "max_tokens": get("ai_max_tokens", DEFAULT_CONFIG["max_tokens"], int),
                "timeout": get("ai_timeout", DEFAULT_CONFIG["timeout"], int),
                "enable_json_repair": get("enable_json_repair", "true") == "true",
                "enable_multi_sample": get("enable_multi_sample", "false") == "true",
                "multi_sample_threshold": get("multi_sample_confidence_threshold", 0.6, float),
                "reasoning_effort": get("ai_reasoning_effort", "low"),
            }
        except Exception as e:
            logger.error(f"Config load error: {e}")
            return DEFAULT_CONFIG.copy()

    @staticmethod
    def parse_response(text: str) -> AIExtractionResponse:
        """Extract and parse JSON from response."""
        # Try finding JSON block
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL) or re.search(r"\{.*\}", text, re.DOTALL)
        json_str = match.group(1 if match.lastindex else 0) if match else text
        return AIExtractionResponse(**json.loads(json_str))

    @staticmethod
    async def call_llm(messages: list, config: AIConfig, is_repair: bool = False) -> str:
        """Execute LLM call using litellm."""
        model = config["model"]
        if config["provider"] == "ollama" and not model.startswith("ollama/"):
            model = f"ollama/{model}"

        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": 300 if is_repair else config["max_tokens"],
            "temperature": 0.0 if is_repair else config["temperature"],
            "timeout": config["timeout"],
            "drop_params": True,
        }

        if config["api_key"]:
            kwargs["api_key"] = config["api_key"]
        if config["api_base"]:
            kwargs["api_base"] = config["api_base"]

        # Provider specifics
        if config["provider"] == "ollama":
            kwargs["format"] = "json"
        elif config["provider"] == "openai" and not is_repair:
            kwargs["response_format"] = AIExtractionResponse
            kwargs["reasoning_effort"] = config["reasoning_effort"]

        response = await acompletion(**kwargs)
        return response.choices[0].message.content

    @classmethod
    async def analyze_image(
        cls, image_path: str, page_text: str = "", custom_prompt: str | None = None
    ) -> tuple[AIExtractionResponse, AIExtractionMetadata] | None:
        try:
            config = await cls.get_ai_config()
            base64_image = await encode_image(image_path)

            text_context = clean_text(page_text)[:5000] if page_text else None
            prompt = get_extraction_prompt(text_context, custom_prompt)

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                    ],
                }
            ]

            # Retry wrapper for the call
            @retry(
                retry=retry_if_exception_type((TimeoutError, ConnectionError, ValueError)),
                stop=stop_after_attempt(3),
                wait=wait_exponential(min=1, max=5),
            )
            async def protected_call():
                return await cls.call_llm(messages, config)

            response_text = await protected_call()

            # Parsing & Repair
            repair_used = False
            try:
                result = cls.parse_response(response_text)
            except (ValidationError, json.JSONDecodeError):
                if not config["enable_json_repair"]:
                    raise
                logger.info("Reparing JSON...")
                repair_msg = [{"role": "user", "content": get_repair_prompt(response_text)}]
                repaired = await cls.call_llm(repair_msg, config, is_repair=True)
                result = cls.parse_response(repaired)
                repair_used = True

            return result, AIExtractionMetadata(
                model_name=config["model"],
                provider=config["provider"],
                prompt_version=PROMPT_VERSION,
                repair_used=repair_used,
                multi_sample=False,
                sample_count=1,
            )

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return None
