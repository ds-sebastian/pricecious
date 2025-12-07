from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import models
from app.services.scheduler_service import UpdateData, _update_item_in_db


@pytest.fixture
def mock_session():
    session = AsyncMock()
    # Mock execute result
    mock_result = MagicMock()
    mock_result.scalars().first.return_value = None
    session.execute.return_value = mock_result
    return session


@pytest.fixture
def mock_item():
    item = models.Item(
        id=1,
        url="http://example.com",
        name="Test Item",
        current_price=100.0,
        in_stock=True,
        current_price_confidence=0.9,
        in_stock_confidence=0.9,
        last_checked=datetime.now(UTC).replace(tzinfo=None),
    )
    return item


@pytest.fixture
def update_data():
    extraction = MagicMock()
    extraction.price = 200.0
    extraction.in_stock = True
    extraction.price_confidence = 0.9
    extraction.in_stock_confidence = 0.9

    metadata = MagicMock()
    metadata.model_name = "test-model"
    metadata.provider = "test-provider"
    metadata.prompt_version = "v1"
    metadata.repair_used = False

    thresholds = {"price": 0.5, "stock": 0.5, "outlier_percent": 50.0, "outlier_enabled": True}

    return UpdateData(extraction=extraction, metadata=metadata, thresholds=thresholds, screenshot_path="test.png")


@pytest.mark.asyncio
async def test_outlier_rejection_enabled(mock_session, mock_item, update_data):
    # Setup
    mock_session.execute.return_value.scalars().first.return_value = mock_item

    # Run
    _old_price, _old_stock = await _update_item_in_db(1, update_data, mock_session)

    # Verify rejection
    # Price increased by 100% (100 -> 200), threshold is 50%
    # Should reject update
    assert mock_item.current_price == 100.0
    assert mock_item.last_error is not None
    assert "Price rejected" in mock_item.last_error


@pytest.mark.asyncio
async def test_outlier_rejection_disabled(mock_session, mock_item, update_data):
    # Setup
    mock_session.execute.return_value.scalars().first.return_value = mock_item
    update_data.thresholds["outlier_enabled"] = False

    # Run
    _old_price, _old_stock = await _update_item_in_db(1, update_data, mock_session)

    # Verify update accepted
    assert mock_item.current_price == 200.0
    assert mock_item.last_error is None


@pytest.mark.asyncio
async def test_outlier_acceptance_within_threshold(mock_session, mock_item, update_data):
    # Setup
    mock_session.execute.return_value.scalars().first.return_value = mock_item
    update_data.extraction.price = 140.0  # 40% increase

    # Run
    _old_price, _old_stock = await _update_item_in_db(1, update_data, mock_session)

    # Verify update accepted
    assert mock_item.current_price == 140.0
    assert mock_item.last_error is None
