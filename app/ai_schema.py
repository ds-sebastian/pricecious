"""
Unified JSON schema for AI extraction responses.

This module defines the canonical schema for all AI model responses,
including confidence scores and metadata tracking.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Schema version for tracking prompt/schema changes
PROMPT_VERSION = "v2.0"

# Default confidence thresholds
DEFAULT_PRICE_CONFIDENCE_THRESHOLD = 0.5
DEFAULT_STOCK_CONFIDENCE_THRESHOLD = 0.5
DEFAULT_MULTI_SAMPLE_THRESHOLD = 0.6


class AIExtractionResponse(BaseModel):
    """
    Canonical schema for AI extraction responses.

    All AI models must return data matching this schema.
    """

    price: float | None = Field(
        None,
        description="Extracted price as a number, or null if no price found",
    )
    currency: str = Field(
        "USD",
        description="Currency code (ISO 4217)",
    )
    in_stock: bool | None = Field(
        None,
        description="Stock status: true if in stock, false if out of stock, null if unclear",
    )
    price_confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in price extraction (0.0 to 1.0)",
    )
    in_stock_confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in stock status extraction (0.0 to 1.0)",
    )
    source_type: Literal["image", "text", "both"] = Field(
        "image",
        description="Source of extraction: image, text, or both",
    )

    @field_validator("price_confidence", "in_stock_confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v):
        """Clamp confidence values to [0.0, 1.0] range."""
        if v is None:
            return 0.0
        return max(0.0, min(1.0, float(v)))

    @field_validator("price", mode="before")
    @classmethod
    def normalize_price(cls, v):
        """Normalize price to float or None."""
        if v is None or v in ("null", ""):
            return None
        if isinstance(v, str):
            # Remove currency symbols and commas
            import re

            cleaned = re.sub(r"[^\d.]", "", v)
            if cleaned:
                return float(cleaned)
            return None
        return float(v)

    @field_validator("in_stock", mode="before")
    @classmethod
    def normalize_stock(cls, v):
        """Normalize stock status to boolean or None."""
        if v is None or v == "null":
            return None
        if isinstance(v, str):
            v_lower = v.lower().strip()
            if v_lower in ("true", "yes", "in stock", "available", "1"):
                return True
            if v_lower in ("false", "no", "out of stock", "unavailable", "0"):
                return False
            return None
        return bool(v)


class AIExtractionMetadata(BaseModel):
    """
    Metadata about an AI extraction operation.

    Tracks which model was used, whether repair was needed, etc.
    """

    model_name: str = Field(..., description="AI model identifier (e.g., 'gpt-4o')")
    provider: str = Field(..., description="AI provider (e.g., 'openai', 'ollama')")
    prompt_version: str = Field(PROMPT_VERSION, description="Version of the extraction prompt used")
    repair_used: bool = Field(False, description="Whether JSON repair fallback was used")
    multi_sample: bool = Field(False, description="Whether multi-sample validation was used")
    sample_count: int = Field(1, description="Number of samples generated (for multi-sample)")


# Prompt template for schema-first extraction
EXTRACTION_PROMPT_TEMPLATE = """You are a price extraction assistant. Extract the product price and stock status from the provided image and optional text context.

**Extraction Rules:**
1. **Price**:
   - Choose the main current price (usually the largest, most prominent price)
   - Ignore crossed-out/struck-through prices (those are old prices)
   - If multiple prices (e.g., sale price and regular price), choose the current/sale price
   - If no clear price is visible, set price to null and price_confidence below 0.5
   - Extract only the numeric value (no currency symbols)

2. **Stock Status**:
   - Set in_stock to true if: "Add to Cart", "Buy Now", "Available", "In Stock" buttons/text are visible
   - Set in_stock to false if: "Out of Stock", "Unavailable", "Sold Out", "Notify Me" are shown
   - Set in_stock to null if stock status is unclear or not shown
   - If unclear, set in_stock_confidence below 0.5

3. **Confidence Scores**:
   - price_confidence: Your subjective probability (0.0 to 1.0) that the extracted price is correct
   - in_stock_confidence: Your subjective probability (0.0 to 1.0) that the stock status is correct
   - Be honest: if the image is blurry, text is unclear, or multiple prices are confusing, use lower confidence
   - Confidence of 0.9-1.0 means you're very certain
   - Confidence of 0.5-0.8 means you're moderately certain
   - Confidence below 0.5 means you're unsure

**Output Format:**
Respond ONLY with valid JSON matching this exact schema. No markdown, no prose, no explanation.

{{
  "price": <number or null>,
  "currency": "<ISO currency code, default USD>",
  "in_stock": <true, false, or null>,
  "price_confidence": <number from 0.0 to 1.0>,
  "in_stock_confidence": <number from 0.0 to 1.0>,
  "source_type": "<image, text, or both>"
}}

{context_section}"""

# Repair prompt template
REPAIR_PROMPT_TEMPLATE = """Convert the following text into valid JSON matching this schema:

{{
  "price": <number or null>,
  "currency": "<ISO currency code, default USD>",
  "in_stock": <true, false, or null>,
  "price_confidence": <number from 0.0 to 1.0>,
  "in_stock_confidence": <number from 0.0 to 1.0>,
  "source_type": "<image, text, or both>"
}}

Rules:
- Extract numeric price value only (no symbols)
- Boolean values must be true, false, or null (not strings)
- Confidence values must be numbers between 0.0 and 1.0
- Respond with ONLY the JSON object, no other text

Text to convert:
{raw_output}"""


def get_extraction_prompt(page_text: str | None = None) -> str:
    """
    Generate the extraction prompt with optional text context.

    Args:
        page_text: Optional webpage text to include as context

    Returns:
        Formatted prompt string
    """
    if page_text:
        context_section = f"""**Context from webpage text:**
{page_text[:2000]}{"...(truncated)" if len(page_text) > 2000 else ""}"""
    else:
        context_section = ""

    return EXTRACTION_PROMPT_TEMPLATE.format(context_section=context_section)


def get_repair_prompt(raw_output: str) -> str:
    """
    Generate the repair prompt for fixing invalid JSON.

    Args:
        raw_output: Raw AI output that failed parsing

    Returns:
        Formatted repair prompt
    """
    return REPAIR_PROMPT_TEMPLATE.format(raw_output=raw_output[:1000])
