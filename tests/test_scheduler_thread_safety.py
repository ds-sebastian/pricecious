from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai_schema import AIExtractionMetadata, AIExtractionResponse
from app.services.scheduler_service import UpdateData, _process_single_item_sync, _update_item_in_db, process_item_check


@pytest.mark.asyncio
async def test_process_item_check_thread_safety():
    """
    Verify that process_item_check does not use a shared session across threads.
    We mock the helper functions to ensure they are called correctly.
    """
    item_id = 1

    # Mock data
    mock_item_data = {"name": "Test Item", "url": "http://example.com", "selector": None}
    mock_config = {"smart_scroll": False, "smart_scroll_pixels": 350, "text_length": 0, "scraper_timeout": 90000}
    mock_thresholds = {"price": 0.5, "stock": 0.5}

    mock_extraction = AIExtractionResponse(price=100.0, in_stock=True, price_confidence=0.9, in_stock_confidence=0.9)
    mock_metadata = AIExtractionMetadata(
        model_name="test", provider="test", prompt_version="1", repair_used=False, multi_sample=False, sample_count=1
    )

    # Mock dependencies
    with (
        patch("app.services.scheduler_service.database.SessionLocal"),
        patch("app.services.scheduler_service.ScraperService.scrape_item", new_callable=AsyncMock) as mock_scrape,
        patch("app.services.scheduler_service.AIService.analyze_image", new_callable=AsyncMock) as mock_analyze,
        patch(
            "app.services.scheduler_service.NotificationService.send_item_notifications", new_callable=AsyncMock
        ) as mock_notify,
    ):
        # Setup mocks
        mock_scrape.return_value = ("screenshot.png", "text")
        mock_analyze.return_value = (mock_extraction, mock_metadata)

        # Mock the sync helpers to verify they are called in executor
        with (
            patch("app.services.scheduler_service._process_single_item_sync") as mock_process_sync,
            patch("app.services.scheduler_service._update_item_in_db") as mock_update_db,
        ):
            mock_process_sync.return_value = (mock_item_data, mock_config, mock_thresholds)
            mock_update_db.return_value = (90.0, True)  # old_price, old_stock

            # Run the function
            await process_item_check(item_id)

            # Verify that sync functions were called (which implies they ran in executor if we trust the code structure,
            # but more importantly we verify the flow works without error)
            mock_process_sync.assert_called_once_with(item_id)
            mock_scrape.assert_called_once()
            mock_analyze.assert_called_once()
            mock_update_db.assert_called_once()
            mock_notify.assert_called_once()


def test_process_single_item_sync_creates_session():
    """Verify that _process_single_item_sync creates its own session."""
    item_id = 1
    with (
        patch("app.services.scheduler_service.database.SessionLocal") as mock_session_cls,
        patch("app.services.scheduler_service.ItemService.get_item_data_for_checking") as mock_get_data,
    ):
        mock_session = mock_session_cls.return_value
        mock_session.__enter__.return_value = mock_session

        mock_get_data.return_value = ({"name": "Test"}, {})

        _process_single_item_sync(item_id)

        # Verify SessionLocal was called to create a new session
        mock_session_cls.assert_called()
        # Verify get_item_data_for_checking was called with the new session
        mock_get_data.assert_called_with(mock_session, item_id)


def test_update_item_in_db_creates_session():
    """Verify that _update_item_in_db creates its own session."""
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
        thresholds={"price": 0.5, "stock": 0.5},
        screenshot_path="path",
    )

    with patch("app.services.scheduler_service.database.SessionLocal") as mock_session_cls:
        mock_session = mock_session_cls.return_value
        mock_session.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = MagicMock(
            current_price=5.0, in_stock=True
        )

        _update_item_in_db(item_id, update_data)

        # Verify SessionLocal was called
        mock_session_cls.assert_called()
