from unittest.mock import MagicMock, patch

import pytest

from app.services.ai_service import DEFAULT_CONFIG, AIService


@pytest.mark.asyncio
async def test_call_llm_retry_on_empty_content():
    """
    Test that call_llm retires without response_format if the first call returns empty content.
    """
    mock_response_empty = MagicMock()
    mock_response_empty.choices = [MagicMock(message=MagicMock(content=""))]

    mock_response_valid = MagicMock()
    mock_response_valid.choices = [MagicMock(message=MagicMock(content='{"valid": "json"}'))]

    # Mock acompletion to fail first, then succeed
    with patch(
        "app.services.ai_service.acompletion", side_effect=[mock_response_empty, mock_response_valid]
    ) as mock_acompletion:
        config = DEFAULT_CONFIG.copy()
        # Ensure provider is NOT openai so we hit the generic json_object path or ollama path
        config["provider"] = "other"

        result = await AIService.call_llm(messages=[], config=config)

        assert result == '{"valid": "json"}'
        assert mock_acompletion.call_count == 2

        # Verify first call had response_format
        call_args_1 = mock_acompletion.call_args_list[0]
        assert "response_format" in call_args_1.kwargs

        # Verify second call dropped response_format
        call_args_2 = mock_acompletion.call_args_list[1]
        assert "response_format" not in call_args_2.kwargs


@pytest.mark.asyncio
async def test_call_llm_fails_if_retry_empty():
    """
    Test that call_llm raises ValueError if even the retry returns empty content.
    """
    mock_response_empty = MagicMock()
    mock_response_empty.choices = [MagicMock(message=MagicMock(content=""))]

    with patch("app.services.ai_service.acompletion", return_value=mock_response_empty) as mock_acompletion:
        config = DEFAULT_CONFIG.copy()

        with pytest.raises(ValueError, match="LLM returned empty content"):
            await AIService.call_llm(messages=[], config=config)

        assert mock_acompletion.call_count == 2
