import asyncio
import logging
from statistics import median
from typing import TypedDict

import json_repair
import litellm
from litellm import acompletion
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

# Multi-sample consensus constants
MULTI_SAMPLE_COUNT = 3
MULTI_SAMPLE_TEMPERATURE = 0.3
MULTI_SAMPLE_PRICE_TOLERANCE = 0.02  # 2% tolerance for price agreement
MULTI_SAMPLE_MIN_CONSENSUS = 2  # Minimum samples that must agree


class AIConfig(TypedDict):
    provider: str
    model: str
    api_key: str
    api_base: str
    temperature: float
    max_tokens: int
    timeout: int
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
                "enable_multi_sample": get("enable_multi_sample", "false") == "true",
                "multi_sample_threshold": get("multi_sample_confidence_threshold", 0.6, float),
                "reasoning_effort": get("ai_reasoning_effort", "low"),
            }
        except Exception as e:
            logger.error(f"Config load error: {e}")
            return DEFAULT_CONFIG.copy()

    @staticmethod
    def parse_response(text: str) -> AIExtractionResponse:
        """Extract and parse JSON from response using json_repair."""
        # json_repair handles markdown blocks, trailing commas, and more automatically
        data = json_repair.loads(text)
        if isinstance(data, list):
            # Handle rare case where list is returned instead of dict
            if data and isinstance(data[0], dict):
                data = data[0]
            else:
                raise ValueError(f"Parsed JSON is a list, expected dictionary. Content snippet: {str(data)[:200]}")

        if not isinstance(data, dict):
            # Include snippet of what was actually parsed (or the original text
            # if parsing failed to produce a structure)
            snippet = str(data)[:200] if data else text[:200]
            raise ValueError(f"Parsed JSON is not a dictionary: {type(data)}. Content snippet: {snippet}")

        return AIExtractionResponse(**data)

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
        elif not is_repair:
            # Universal attempt to enable JSON mode for other providers
            # This is safer than passing a Pydantic class which many providers via OpenRouter don't support well yet
            kwargs["response_format"] = {"type": "json_object"}

        if config["provider"]:
            kwargs["custom_llm_provider"] = config["provider"]
        elif "ollama" in config.get("api_base", ""):
            # Fallback: if provider is missing but api_base has ollama, assume ollama
            kwargs["custom_llm_provider"] = "ollama"

        try:
            response = await acompletion(**kwargs)
            content = response.choices[0].message.content

            # Robustness: If content is empty and we asked for JSON format, try again without it
            # Some models (e.g. nova-2-lite) fail to output anything when forced into json mode
            has_json_format = kwargs.get("response_format") or kwargs.get("format") == "json"
            if not content and not is_repair and has_json_format:
                logger.warning(f"LLM returned empty content with JSON format. Retrying raw. Model: {model}")
                kwargs.pop("response_format", None)
                kwargs.pop("format", None)
                response = await acompletion(**kwargs)
                content = response.choices[0].message.content

            if not content:
                error_msg = f"LLM returned empty content. Model: {model}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            return content
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    @classmethod
    async def _multi_sample_analyze(
        cls,
        messages: list,
        config: AIConfig,
        n: int = MULTI_SAMPLE_COUNT,
    ) -> tuple[AIExtractionResponse, AIExtractionMetadata] | None:
        """Run N parallel extractions and return consensus result.

        The function sends ``n`` parallel LLM requests at a slightly higher
        temperature and then applies a majority-vote strategy on the
        extracted prices.  A price is accepted if at least 2 samples agree
        within ``MULTI_SAMPLE_PRICE_TOLERANCE`` (2 %).
        """
        multi_config = {**config, "temperature": MULTI_SAMPLE_TEMPERATURE}
        logger.info(f"Running multi-sample analysis with {n} samples")

        # Fire N parallel calls
        tasks = [cls.call_llm(messages, multi_config) for _ in range(n)]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Parse successful responses
        parsed: list[AIExtractionResponse] = []
        for r in raw_results:
            if isinstance(r, Exception):
                logger.debug(f"Multi-sample call failed: {r}")
                continue
            try:
                parsed.append(cls.parse_response(r))
            except Exception as e:
                logger.debug(f"Multi-sample parse failed: {e}")

        if not parsed:
            logger.warning("All multi-sample calls failed")
            return None

        # Extract prices and find consensus
        prices = [p.price for p in parsed if p.price is not None]

        if not prices:
            # All samples returned None price — use first result
            best = parsed[0]
        elif len(prices) == 1:
            # Only one price extracted — use it
            best = next(p for p in parsed if p.price is not None)
        else:
            # Find the median price and count how many agree within tolerance
            med = median(prices)
            agreeing = [p for p in prices if abs(p - med) / med <= MULTI_SAMPLE_PRICE_TOLERANCE] if med > 0 else prices
            if len(agreeing) >= MULTI_SAMPLE_MIN_CONSENSUS:
                # Consensus reached — use the sample closest to median
                best = min(
                    [p for p in parsed if p.price is not None],
                    key=lambda p: abs(p.price - med),
                )
                # Boost confidence since we have consensus
                best.price_confidence = min(1.0, best.price_confidence + 0.1)
                logger.info(f"Multi-sample consensus: {len(agreeing)}/{len(prices)} agree on ~${med:.2f}")
            else:
                # No consensus — pick the response with highest confidence
                best = max(
                    [p for p in parsed if p.price is not None],
                    key=lambda p: p.price_confidence,
                )
                logger.warning(f"Multi-sample: no consensus (prices: {prices}), using highest confidence")

        meta = AIExtractionMetadata(
            model_name=config["model"],
            provider=config["provider"],
            prompt_version=PROMPT_VERSION,
            repair_used=False,
            multi_sample=True,
            sample_count=len(parsed),
        )

        return best, meta

    @classmethod
    async def analyze_image(
        cls,
        image_path: str,
        page_text: str = "",
        custom_prompt: str | None = None,
        last_known_price: float | None = None,
        url: str | None = None,
    ) -> tuple[AIExtractionResponse, AIExtractionMetadata] | None:
        try:
            config = await cls.get_ai_config()
            base64_image = await encode_image(image_path)
            prompt = get_extraction_prompt(
                clean_text(page_text) if page_text else None,
                custom_prompt,
                last_known_price=last_known_price,
                url=url,
            )

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                    ],
                }
            ]

            @retry(
                retry=retry_if_exception_type((TimeoutError, ConnectionError, ValueError)),
                stop=stop_after_attempt(3),
                wait=wait_exponential(min=1, max=5),
            )
            async def protected_call():
                return await cls.call_llm(messages, config)

            def make_meta(repair_used: bool) -> AIExtractionMetadata:
                return AIExtractionMetadata(
                    model_name=config["model"],
                    provider=config["provider"],
                    prompt_version=PROMPT_VERSION,
                    repair_used=repair_used,
                    multi_sample=False,
                    sample_count=1,
                )

            response_text = await protected_call()
            logger.debug(f"Raw AI Response: {response_text}")

            try:
                result = cls.parse_response(response_text)
            except Exception as e:
                logger.info(f"Parsing failed: {e}. Attempting LLM repair...")
                repair_msg = [{"role": "user", "content": get_repair_prompt(response_text)}]
                repaired = await cls.call_llm(repair_msg, config, is_repair=True)
                return cls.parse_response(repaired), make_meta(True)

            # If multi-sample is enabled and single-sample confidence is below threshold,
            # run multi-sample consensus for higher reliability
            if (
                config["enable_multi_sample"]
                and result.price_confidence < config["multi_sample_threshold"]
                and result.price is not None
            ):
                logger.info(
                    f"Single-sample confidence ({result.price_confidence:.2f}) below threshold "
                    f"({config['multi_sample_threshold']:.2f}), running multi-sample..."
                )
                multi_result = await cls._multi_sample_analyze(messages, config)
                if multi_result:
                    return multi_result

            return result, make_meta(False)

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return None
