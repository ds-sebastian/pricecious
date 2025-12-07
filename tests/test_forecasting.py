from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.models import PriceHistory
from app.services.forecasting_service import ForecastingService


@pytest.mark.asyncio
async def test_forecasting_service():
    # Mock PriceHistory
    mock_history = [
        MagicMock(timestamp=datetime(2023, 1, 1), price=100.0),
        MagicMock(timestamp=datetime(2023, 1, 2), price=102.0),
        MagicMock(timestamp=datetime(2023, 1, 3), price=101.0),
        MagicMock(timestamp=datetime(2023, 1, 4), price=103.0),
        MagicMock(timestamp=datetime(2023, 1, 5), price=105.0),
    ]

    # Create a dummy result class
    class MockResult:
        def scalars(self):
            return self

        def all(self):
            return mock_history

    mock_result = MockResult()

    # Manual session mock to avoid AsyncMock weirdness
    mock_session = MagicMock()

    async def async_enter(*args, **kwargs):
        return mock_session

    async def async_exit(*args, **kwargs):
        return None

    mock_session.__aenter__.side_effect = async_enter
    mock_session.__aexit__.side_effect = async_exit

    async def async_execute(*args, **kwargs):
        return mock_result

    mock_session.execute.side_effect = async_execute

    async def async_commit(*args, **kwargs):
        return None

    mock_session.commit.side_effect = async_commit

    mock_session.add_all = MagicMock()

    # Mock Prophet
    with patch("app.services.forecasting_service.Prophet") as MockProphet:
        # Mock database session execution result
        history_data = [
            PriceHistory(timestamp=datetime(2023, 1, 1) + timedelta(days=i), price=100.0 + i) for i in range(20)
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = history_data
        mock_session.execute.return_value = mock_result
        mock_model = MockProphet.return_value
        mock_model.make_future_dataframe.return_value = pd.DataFrame(
            {"ds": [datetime(2023, 1, 6), datetime(2023, 1, 7)]}
        )
        mock_model.predict.return_value = pd.DataFrame(
            {
                "ds": [datetime(2023, 1, 6), datetime(2023, 1, 7)],
                "yhat": [106.0, 107.0],
                "yhat_lower": [105.0, 106.0],
                "yhat_upper": [107.0, 108.0],
            }
        )

        # Patch the class itself, and make sure return_value is our mock_session
        # When AsyncSessionLocal() is called, it returns something that has __aenter__
        # Here we make AsyncSessionLocal() return mock_session directly, which has __aenter__
        with patch("app.database.AsyncSessionLocal", return_value=mock_session):
            await ForecastingService.generate_forecast(1)

            # Verify Prophet configuration
            # In this test, history is 20 days (Jan 1 - Jan 20).
            # Duration = 19 days. < 500, so yearly_seasonality=False.
            # Black Friday is Nov. Jan dates do not contain BF. So BF regressor should NOT be added.

            MockProphet.assert_called_with(
                seasonality_mode="multiplicative",
                changepoint_prior_scale=0.01,
                seasonality_prior_scale=1.0,
                daily_seasonality=False,
                weekly_seasonality=True,
                yearly_seasonality=False,
            )
            # Black Friday regressor should NOT be called because dates don't overlap with Nov
            mock_model.add_regressor.assert_not_called()

            mock_model.fit.assert_called()
            mock_model.predict.assert_called()

            # Verify DB operations
            assert mock_session.add_all.called
            assert mock_session.commit.called
