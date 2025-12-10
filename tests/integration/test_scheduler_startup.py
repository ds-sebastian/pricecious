from unittest.mock import AsyncMock, patch

import pytest

from app.main import app, lifespan
from app.services.scheduler_service import scheduler


@pytest.mark.asyncio
async def test_scheduler_startup():
    """Verify that the scheduler starts and jobs are added on app startup."""
    # Ensure scheduler is stopped before test
    if scheduler.running:
        scheduler.shutdown()

    # Mock SettingsService to avoid DB calls
    with patch("app.main.SettingsService") as mock_settings:
        # returns string "24" for forecasting, "60" for refresh
        mock_settings.get_setting_value = AsyncMock(side_effect=["24", "60"])

        async with lifespan(app):
            # 1. Verify Scheduler is running
            assert scheduler.running is True, "Scheduler should be running"

            # 2. Verify Jobs are added
            job_refresh = scheduler.get_job("refresh_job")
            job_forecasting = scheduler.get_job("forecasting_job")

            assert job_refresh is not None, "Refresh job should be scheduled"
            assert job_forecasting is not None, "Forecasting job should be scheduled"

            # 3. Verify Refresh Job Configuration
            # Default is 60 minutes
            assert job_refresh.trigger.interval.total_seconds() == 3600, "Default refresh interval should be 60 minutes"
