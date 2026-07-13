from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import models
from app.services.scheduler_service import UpdateData, _handle_error, _update_item_in_db


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

    thresholds = {
        "price": 0.5,
        "stock": 0.5,
        "outlier_percent": 50.0,
        "outlier_enabled": True,
        "price_min_floor": 0.01,
        "price_max_ceiling": 100_000.0,
        "max_consecutive_failures": 20,
    }

    return UpdateData(extraction=extraction, metadata=metadata, thresholds=thresholds, screenshot_path="test.png")


@pytest.mark.asyncio
async def test_outlier_rejection_enabled(mock_session, mock_item, update_data):
    # Setup
    mock_session.execute.return_value.scalars().first.return_value = mock_item

    # Run
    result = await _update_item_in_db(1, update_data, mock_session)

    # Verify rejection
    # Price increased by 100% (100 -> 200), threshold is 50%
    # Should reject update
    assert mock_item.current_price == 100.0
    assert mock_item.last_error is not None
    assert "Price rejected" in mock_item.last_error
    assert result.price is None
    assert result.in_stock is None


@pytest.mark.asyncio
async def test_outlier_rejection_disabled(mock_session, mock_item, update_data):
    # Setup
    mock_session.execute.return_value.scalars().first.return_value = mock_item
    update_data.thresholds["outlier_enabled"] = False

    # Run
    result = await _update_item_in_db(1, update_data, mock_session)

    # Verify update accepted
    assert mock_item.current_price == 200.0
    assert mock_item.last_error is None
    assert result.price == 200.0


@pytest.mark.asyncio
async def test_low_confidence_sets_last_error(mock_session, mock_item, update_data):
    """Price found but confidence below threshold should set last_error."""
    mock_session.execute.return_value.scalars().first.return_value = mock_item
    update_data.extraction.price = 120.0
    update_data.extraction.price_confidence = 0.3  # Below 0.5 threshold
    update_data.thresholds["outlier_enabled"] = False  # Disable outlier check

    result = await _update_item_in_db(1, update_data, mock_session)

    # Price should NOT be updated
    assert mock_item.current_price == 100.0
    # last_error should explain the low confidence
    assert mock_item.last_error is not None
    assert "Low confidence" in mock_item.last_error
    assert "120.00" in mock_item.last_error
    assert "0.30" in mock_item.last_error
    assert result.price is None


@pytest.mark.asyncio
async def test_low_confidence_stock_is_not_accepted(mock_session, mock_item, update_data):
    mock_session.execute.return_value.scalars().first.return_value = mock_item
    update_data.extraction.price = None
    update_data.extraction.in_stock = False
    update_data.extraction.in_stock_confidence = 0.2

    result = await _update_item_in_db(1, update_data, mock_session)

    assert mock_item.in_stock is True
    assert result.in_stock is None


@pytest.mark.asyncio
async def test_sufficient_confidence_clears_low_confidence_error(mock_session, mock_item, update_data):
    """A successful high-confidence update should clear a previous low-confidence error."""
    mock_session.execute.return_value.scalars().first.return_value = mock_item
    mock_item.last_error = "Low confidence: price found (99.00) but confidence (0.20) is below threshold (0.50)"
    mock_item.current_price = 100.0
    update_data.extraction.price = 110.0
    update_data.extraction.price_confidence = 0.9  # High confidence
    update_data.thresholds["outlier_enabled"] = False

    _old_price, _old_stock = await _update_item_in_db(1, update_data, mock_session)

    # Price should be updated
    assert mock_item.current_price == 110.0
    # last_error should be cleared
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


# --- New tests for bidirectional outlier detection ---


@pytest.mark.asyncio
async def test_outlier_rejection_downward(mock_session, mock_item, update_data):
    """A suspicious price drop should be rejected too (bidirectional check)."""
    mock_session.execute.return_value.scalars().first.return_value = mock_item
    update_data.extraction.price = 5.0  # 95% decrease from $100

    _old_price, _old_stock = await _update_item_in_db(1, update_data, mock_session)

    # Price should NOT be updated
    assert mock_item.current_price == 100.0
    assert mock_item.last_error is not None
    assert "decrease" in mock_item.last_error
    assert "Price rejected" in mock_item.last_error


@pytest.mark.asyncio
async def test_outlier_downward_within_threshold_accepted(mock_session, mock_item, update_data):
    """A reasonable price drop within threshold should be accepted."""
    mock_session.execute.return_value.scalars().first.return_value = mock_item
    update_data.extraction.price = 70.0  # 30% decrease — within 50% threshold

    _old_price, _old_stock = await _update_item_in_db(1, update_data, mock_session)

    assert mock_item.current_price == 70.0
    assert mock_item.last_error is None


# --- New tests for price sanity bounds ---


@pytest.mark.asyncio
async def test_price_below_floor_rejected(mock_session, mock_item, update_data):
    """A price below the absolute floor should be rejected."""
    mock_session.execute.return_value.scalars().first.return_value = mock_item
    update_data.extraction.price = 0.001  # Below default floor of 0.01
    update_data.thresholds["outlier_enabled"] = False  # Disable outlier check

    _old_price, _old_stock = await _update_item_in_db(1, update_data, mock_session)

    assert mock_item.current_price == 100.0
    assert mock_item.last_error is not None
    assert "outside sanity bounds" in mock_item.last_error


@pytest.mark.asyncio
async def test_price_above_ceiling_rejected(mock_session, mock_item, update_data):
    """A price above the absolute ceiling should be rejected."""
    mock_session.execute.return_value.scalars().first.return_value = mock_item
    update_data.extraction.price = 200_000.0  # Above default ceiling of 100,000
    update_data.thresholds["outlier_enabled"] = False

    _old_price, _old_stock = await _update_item_in_db(1, update_data, mock_session)

    assert mock_item.current_price == 100.0
    assert mock_item.last_error is not None
    assert "outside sanity bounds" in mock_item.last_error


# --- New tests for consecutive failure tracking ---


@pytest.mark.asyncio
async def test_success_resets_consecutive_failures(mock_session, mock_item, update_data):
    """A successful update should reset consecutive_failures to 0."""
    mock_session.execute.return_value.scalars().first.return_value = mock_item
    mock_item.consecutive_failures = 5
    update_data.extraction.price = 110.0
    update_data.thresholds["outlier_enabled"] = False

    await _update_item_in_db(1, update_data, mock_session)

    assert mock_item.consecutive_failures == 0


@pytest.mark.asyncio
async def test_handle_error_increments_failures():
    """_handle_error should increment consecutive_failures."""
    mock_item = models.Item(
        id=1,
        url="http://example.com",
        name="Test Item",
        consecutive_failures=3,
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars().first.return_value = mock_item
    mock_session.execute.return_value = mock_result

    with patch("app.services.scheduler_service.database.AsyncSessionLocal") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

        # Mock _get_thresholds
        with patch("app.services.scheduler_service._get_thresholds") as mock_thresh:
            mock_thresh.return_value = {"max_consecutive_failures": 20}
            await _handle_error(1, "Test error")

    assert mock_item.consecutive_failures == 4
    assert mock_item.is_active is not False  # Should not deactivate at 4


@pytest.mark.asyncio
async def test_handle_error_auto_deactivates_after_max_failures():
    """Item should be auto-deactivated after max consecutive failures."""
    mock_item = models.Item(
        id=1,
        url="http://example.com",
        name="Test Item",
        consecutive_failures=19,  # Will become 20 — at the limit
        is_active=True,
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars().first.return_value = mock_item
    mock_session.execute.return_value = mock_result

    with patch("app.services.scheduler_service.database.AsyncSessionLocal") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch("app.services.scheduler_service._get_thresholds") as mock_thresh:
            mock_thresh.return_value = {"max_consecutive_failures": 20}
            await _handle_error(1, "Persistent failure")

    assert mock_item.consecutive_failures == 20
    assert mock_item.is_active is False
    assert "Auto-deactivated" in mock_item.last_error
