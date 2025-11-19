"""
Unified JSON schema for AI extraction responses.

This module defines the canonical schema for all AI model responses,
including confidence scores and metadata tracking.
"""

import re
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
EXTRACTION_PROMPT_TEMPLATE = """Extract product price and stock status from the image.

**PRICE:**
- Find the main current price
- Ignore crossed-out prices
- Extract number only (no symbols)
- If unclear: set null and confidence < 0.5

**STOCK:**
- TRUE if: "Add to Cart", "Buy Now", "In Stock", "Available"
- FALSE if: "Out of Stock", "Sold Out", "Unavailable", "Notify Me"
- NULL if unclear or not shown

**CONFIDENCE (0.0 to 1.0):**
- 0.9-1.0: Very certain
- 0.5-0.8: Moderately certain
- Below 0.5: Unsure

Respond ONLY with valid JSON:
{{
  "price": <number or null>,
  "currency": "USD",
  "in_stock": <true, false, or null>,
  "price_confidence": <0.0 to 1.0>,
  "in_stock_confidence": <0.0 to 1.0>,
  "source_type": "both"
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


def filter_relevant_text(text: str, max_length: int = 2000) -> str:
    """
    Filter text to extract only relevant snippets around price and stock indicators.

    Args:
        text: Full cleaned webpage text
        max_length: Maximum total length of filtered output

    Returns:
        Filtered text containing only relevant snippets
    """
    if not text:
        return ""

    # Keywords to search for (case-insensitive)
    price_keywords = [
        r"\$\d+\.?\d*",  # $XX.XX pattern
        r"\d+\.\d{2}\s*(usd|eur|gbp|cad)",  # XX.XX USD pattern
        "price:",
        "cost:",
        "sale:",
        "msrp:",
        "save:",
        "discount:",
        r"\$",  # Any dollar sign
    ]

    stock_keywords = [
        "add to cart",
        "buy now",
        "purchase",
        "order now",
        "in stock",
        "out of stock",
        "available",
        "unavailable",
        "sold out",
        "notify me",
        "back in stock",
        "pre-order",
        "ships",
        "delivery",
        "get it by",
    ]

    all_keywords = price_keywords + stock_keywords
    snippets = []
    context_window = 100  # Characters before and after match

    text_lower = text.lower()

    # Find all matches and extract context
    for keyword in all_keywords:
        # Use regex for pattern-based keywords
        if keyword.startswith("r\\"):
            pattern = keyword[1:]  # Remove 'r' prefix
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                start = max(0, match.start() - context_window)
                end = min(len(text), match.end() + context_window)
                snippet = text[start:end].strip()
                if snippet and len(snippet) > 10:  # Avoid tiny snippets
                    snippets.append((start, snippet))
        else:
            # Simple substring search
            pos = 0
            while True:
                pos = text_lower.find(keyword.lower(), pos)
                if pos == -1:
                    break
                start = max(0, pos - context_window)
                end = min(len(text), pos + len(keyword) + context_window)
                snippet = text[start:end].strip()
                if snippet and len(snippet) > 10:
                    snippets.append((start, snippet))
                pos += 1

    if not snippets:
        # No matches found, return beginning of text
        return text[:max_length]

    # Sort by position and deduplicate overlapping snippets
    snippets.sort(key=lambda x: x[0])
    merged_snippets = []
    current_start, current_text = snippets[0]
    current_end = current_start + len(current_text)

    for start, snippet in snippets[1:]:
        end = start + len(snippet)
        # If overlapping or close together (within 50 chars), merge
        if start <= current_end + 50:
            # Extend current snippet
            if end > current_end:
                # Merge overlapping text
                current_text = current_text + " " + snippet[max(0, current_end - start) :]
                current_end = end
        else:
            # Save current and start new
            merged_snippets.append(current_text)
            current_start, current_text = start, snippet
            current_end = end

    merged_snippets.append(current_text)

    # Join snippets with separator and limit total length
    result = " ... ".join(merged_snippets)
    if len(result) > max_length:
        result = result[:max_length] + "...(truncated)"

    return result


def get_extraction_prompt(page_text: str | None = None) -> str:
    """
    Generate the extraction prompt with optional text context.

    Args:
        page_text: Optional webpage text to include as context

    Returns:
        Formatted prompt string
    """
    if page_text:
        # Apply smart filtering to extract only relevant snippets
        filtered_text = filter_relevant_text(page_text, max_length=1500)
        context_section = f"""**Relevant text from page:**
{filtered_text}"""
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
