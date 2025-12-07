from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai_schema import AIExtractionMetadata, AIExtractionResponse
from app.services.scheduler_service import UpdateData, _process_single_item_data, _update_item_in_db, process_item_check


@pytest.mark.asyncio
async def test_process_item_check_flow():
    """
    Verify the async flow of process_item_check.
    """
    item_id = 1

    # Mock data
    mock_item_data = {"name": "Test Item", "url": "http://example.com", "selector": None}
    mock_config = {"smart_scroll": False, "smart_scroll_pixels": 350, "text_length": 0, "scraper_timeout": 90000}
    mock_thresholds = {"price": 0.5, "stock": 0.5, "outlier_percent": 500.0}

    mock_extraction = AIExtractionResponse(price=100.0, in_stock=True, price_confidence=0.9, in_stock_confidence=0.9)
    mock_metadata = AIExtractionMetadata(
        model_name="test", provider="test", prompt_version="1", repair_used=False, multi_sample=False, sample_count=1
    )

    # Mock dependencies
    with (
        patch("app.services.scheduler_service.database.AsyncSessionLocal"),
        patch("app.services.scheduler_service.ScraperService.scrape_item", new_callable=AsyncMock) as mock_scrape,
        patch("app.services.scheduler_service.AIService.analyze_image", new_callable=AsyncMock) as mock_analyze,
        patch(
            "app.services.scheduler_service.NotificationService.send_item_notifications", new_callable=AsyncMock
        ) as mock_notify,
        patch("app.services.scheduler_service._process_single_item_data", new_callable=AsyncMock) as mock_process_data,
        patch("app.services.scheduler_service._update_item_in_db", new_callable=AsyncMock) as mock_update_db,
    ):
        # Setup mocks
        mock_process_data.return_value = (mock_item_data, mock_config, mock_thresholds)
        mock_scrape.return_value = ("screenshot.png", "text")
        mock_analyze.return_value = (mock_extraction, mock_metadata)
        mock_update_db.return_value = (90.0, True)

        # Run the function
        await process_item_check(item_id)

        # Verify calls
        # We need to verify called with session, but session is internal to execute_check
        # so we can just check called_once and check that arguments match pattern
        assert mock_process_data.call_count == 1
        # Check first arg is item_id, second is session (AsyncSession/AsyncMock)
        assert mock_process_data.call_args[0][0] == item_id
        assert isinstance(mock_process_data.call_args[0][1], AsyncMock | MagicMock)

        mock_scrape.assert_called_once()
        mock_analyze.assert_called_once()

        assert mock_update_db.call_count == 1
        # Check args: item_id, update_data, session
        assert mock_update_db.call_args[0][0] == item_id
        assert isinstance(mock_update_db.call_args[0][2], AsyncMock | MagicMock)

        mock_notify.assert_called_once()


@pytest.mark.asyncio
async def test_process_single_item_data_uses_provided_session():
    """Verify that _process_single_item_data uses the provided session."""
    item_id = 1
    mock_session = AsyncMock()

    with (
        patch(
            "app.services.scheduler_service.ItemService.get_item_data_for_checking", new_callable=AsyncMock
        ) as mock_get_data,
        patch("app.services.scheduler_service._get_thresholds", new_callable=AsyncMock) as mock_get_thresh,
    ):
        mock_get_data.return_value = ({"name": "Test"}, {})
        mock_get_thresh.return_value = {}

        await _process_single_item_data(item_id, mock_session)

        # Verify get_item_data_for_checking was called with the session
        mock_get_data.assert_called_with(mock_session, item_id)
        # Verify get_thresholds using session
        mock_get_thresh.assert_called_with(mock_session)


@pytest.mark.asyncio
async def test_update_item_in_db_uses_provided_session():
    """Verify that _update_item_in_db uses the provided session."""
    item_id = 1
    update_data = UpdateData(
        extraction=AIExtractionResponse(price=10.0, in_stock=True, price_confidence=1.0, in_stock_confidence=1.0),
        metadata=AIExtractionMetadata(
            model_name="test",
            provider="test",
            prompt_version="1",
            repair_used=False,
            multi_sample=False,
            sample_count=1,
        ),
        thresholds={"price": 0.5, "stock": 0.5, "outlier_percent": 500.0},
        screenshot_path="path",
    )

    mock_session = AsyncMock()

    # Mock db execute result
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = MagicMock(
        current_price=5.0, in_stock=True, id=1, last_error=None
    )
    mock_session.execute.return_value = mock_result

    await _update_item_in_db(item_id, update_data, mock_session)

    # Verify session execute was called
    assert mock_session.execute.call_count >= 1
    # Verify commit
    mock_session.commit.assert_called_once()
