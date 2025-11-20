"""
Unit tests for AI schema validation and normalization.
"""

import pytest
from pydantic import ValidationError

from app.ai_schema import AIExtractionMetadata, AIExtractionResponse, get_extraction_prompt, get_repair_prompt


class TestAIExtractionResponse:
    """Test the AI extraction response schema."""

    def test_valid_response(self):
        """Test that valid data passes validation."""
        data = {
            "price": 99.99,
            "currency": "USD",
            "in_stock": True,
            "price_confidence": 0.95,
            "in_stock_confidence": 0.90,
            "source_type": "image",
        }
        response = AIExtractionResponse(**data)
        assert response.price == 99.99
        assert response.in_stock is True
        assert response.price_confidence == 0.95
        assert response.in_stock_confidence == 0.90

    def test_null_price(self):
        """Test that null price is handled correctly."""
        data = {
            "price": None,
            "in_stock": False,
            "price_confidence": 0.2,
            "in_stock_confidence": 0.8,
        }
        response = AIExtractionResponse(**data)
        assert response.price is None
        assert response.in_stock is False

    def test_confidence_clamping_above(self):
        """Test that confidence values above 1.0 are clamped."""
        data = {
            "price": 50.0,
            "in_stock": True,
            "price_confidence": 1.5,  # Should clamp to 1.0
            "in_stock_confidence": 2.0,  # Should clamp to 1.0
        }
        response = AIExtractionResponse(**data)
        assert response.price_confidence == 1.0
        assert response.in_stock_confidence == 1.0

    def test_confidence_clamping_below(self):
        """Test that confidence values below 0.0 are clamped."""
        data = {
            "price": 50.0,
            "in_stock": True,
            "price_confidence": -0.5,  # Should clamp to 0.0
            "in_stock_confidence": -1.0,  # Should clamp to 0.0
        }
        response = AIExtractionResponse(**data)
        assert response.price_confidence == 0.0
        assert response.in_stock_confidence == 0.0

    def test_price_string_normalization(self):
        """Test that price strings are normalized to floats."""
        data = {
            "price": "$99.99",
            "in_stock": True,
            "price_confidence": 0.8,
            "in_stock_confidence": 0.8,
        }
        response = AIExtractionResponse(**data)
        assert response.price == 99.99

    def test_price_string_with_commas(self):
        """Test that prices with commas are handled."""
        data = {
            "price": "$1,234.56",
            "in_stock": True,
            "price_confidence": 0.9,
            "in_stock_confidence": 0.9,
        }
        response = AIExtractionResponse(**data)
        assert response.price == 1234.56

    def test_stock_string_normalization_true(self):
        """Test that stock status strings are normalized to booleans."""
        test_cases = ["true", "True", "yes", "in stock", "available", "1"]
        for value in test_cases:
            data = {
                "price": 10.0,
                "in_stock": value,
                "price_confidence": 0.8,
                "in_stock_confidence": 0.8,
            }
            response = AIExtractionResponse(**data)
            assert response.in_stock is True, f"Failed for value: {value}"

    def test_stock_string_normalization_false(self):
        """Test that out-of-stock strings are normalized to False."""
        test_cases = ["false", "False", "no", "out of stock", "unavailable", "0"]
        for value in test_cases:
            data = {
                "price": 10.0,
                "in_stock": value,
                "price_confidence": 0.8,
                "in_stock_confidence": 0.8,
            }
            response = AIExtractionResponse(**data)
            assert response.in_stock is False, f"Failed for value: {value}"

    def test_stock_ambiguous_string(self):
        """Test that ambiguous stock strings return None."""
        data = {
            "price": 10.0,
            "in_stock": "maybe",
            "price_confidence": 0.8,
            "in_stock_confidence": 0.3,
        }
        response = AIExtractionResponse(**data)
        assert response.in_stock is None

    def test_default_currency(self):
        """Test that default currency is USD."""
        data = {
            "price": 10.0,
            "in_stock": True,
            "price_confidence": 0.8,
            "in_stock_confidence": 0.8,
        }
        response = AIExtractionResponse(**data)
        assert response.currency == "USD"

    def test_default_source_type(self):
        """Test that default source type is 'image'."""
        data = {
            "price": 10.0,
            "in_stock": True,
            "price_confidence": 0.8,
            "in_stock_confidence": 0.8,
        }
        response = AIExtractionResponse(**data)
        assert response.source_type == "image"

    def test_source_type_validation(self):
        """Test that source_type must be one of: image, text, both."""
        with pytest.raises(ValidationError):
            AIExtractionResponse(
                price=10.0,
                in_stock=True,
                price_confidence=0.8,
                in_stock_confidence=0.8,
                source_type="invalid",  # Should fail
            )


class TestAIExtractionMetadata:
    """Test the AI extraction metadata schema."""

    def test_valid_metadata(self):
        """Test that valid metadata passes validation."""
        data = {
            "model_name": "gpt-4o",
            "provider": "openai",
            "prompt_version": "v2.0",
            "repair_used": False,
            "multi_sample": False,
            "sample_count": 1,
        }
        metadata = AIExtractionMetadata(**data)
        assert metadata.model_name == "gpt-4o"
        assert metadata.provider == "openai"
        assert metadata.repair_used is False

    def test_default_values(self):
        """Test that default values are set correctly."""
        data = {
            "model_name": "gemma3:4b",
            "provider": "ollama",
        }
        metadata = AIExtractionMetadata(**data)
        assert metadata.repair_used is False
        assert metadata.multi_sample is False
        assert metadata.sample_count == 1


class TestPromptGeneration:
    """Test prompt generation functions."""

    def test_extraction_prompt_without_text(self):
        """Test extraction prompt without text context."""
        prompt = get_extraction_prompt(None)
        assert "Extract product price" in prompt
        assert "JSON" in prompt
        assert "price_confidence" in prompt
        assert "**Relevant text from page:**" not in prompt

    def test_extraction_prompt_with_text(self):
        """Test extraction prompt with text context."""
        page_text = "Product is in stock for $99.99"
        prompt = get_extraction_prompt(page_text)
        assert "Extract product price" in prompt
        assert "**Relevant text from page:**" in prompt
        assert "$99.99" in prompt

    def test_extraction_prompt_with_long_text(self):
        """Test that long text is truncated."""
        page_text = "A" * 5000
        prompt = get_extraction_prompt(page_text)
        assert "**Relevant text from page:**" in prompt
        assert "truncated" in prompt

    def test_repair_prompt(self):
        """Test repair prompt generation."""
        raw_output = "This is malformed JSON { price: 99.99 }"
        prompt = get_repair_prompt(raw_output)
        assert "Convert the following text" in prompt
        assert raw_output in prompt
        assert "JSON" in prompt
