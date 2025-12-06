from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app import models
from app.services.scheduler_service import process_item_check


@pytest.mark.asyncio
async def test_process_item_check_updates_last_checked_on_error(db):
    # Create a profile
    profile = models.NotificationProfile(name="Test Profile", apprise_url="mailto://test@example.com")
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    # Create item
    item = models.Item(
        url="https://example.com/error",
        name="Error Item",
        notification_profile_id=profile.id,
        is_refreshing=True,
        selector="body",
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    item_id = item.id
    initial_last_checked = item.last_checked

    # Mock ScraperService.scrape_item to raise an exception
    # And patch AsyncSessionLocal to return a context manager yielding our test session

    class MockSessionContext:
        def __init__(self, session):
            self.session = session

        async def __aenter__(self):
            return self.session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with (
        patch("app.services.scraper_service.ScraperService.scrape_item", side_effect=Exception("Scraper failed")),
        patch("app.database.AsyncSessionLocal", side_effect=lambda: MockSessionContext(db)),
    ):
        await process_item_check(item_id)

    # Refresh item from DB
    # We need to expire the object to reload from DB because the other session updated it
    # Since we are sharing the session 'db', it should be up to date after commit?
    # But usually explicit refresh is safer.
    db.expire(item)
    await db.refresh(item)

    # Assertions
    assert item.is_refreshing is False
    assert item.last_error == "Scraper failed"
    assert item.last_checked is not None
    if initial_last_checked:
        assert item.last_checked > initial_last_checked

    # Ensure last_checked is recent (within last minute)
    assert datetime.now() - item.last_checked < timedelta(minutes=1)
