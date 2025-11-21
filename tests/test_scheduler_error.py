from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app import models
from app.services.scheduler_service import process_item_check


@pytest.mark.asyncio
async def test_process_item_check_updates_last_checked_on_error(db):
    # Create a profile
    profile = models.NotificationProfile(name="Test Profile", apprise_url="mailto://test@example.com")
    db.add(profile)
    db.commit()
    db.refresh(profile)

    # Create item
    item = models.Item(
        url="https://example.com/error",
        name="Error Item",
        notification_profile_id=profile.id,
        is_refreshing=True,
        selector="body",
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    item_id = item.id
    initial_last_checked = item.last_checked

    # Create a session maker bound to the same engine as the test db
    from sqlalchemy.orm import sessionmaker

    connection = db.get_bind()
    TestSession = sessionmaker(bind=connection)

    # Mock ScraperService.scrape_item to raise an exception
    # And patch SessionLocal to return our test session
    with (
        patch("app.services.scraper_service.ScraperService.scrape_item", side_effect=Exception("Scraper failed")),
        patch("app.database.SessionLocal", side_effect=TestSession),
    ):
        await process_item_check(item_id)

    # Refresh item from DB
    # We need to expire the object to reload from DB because the other session updated it
    db.expire(item)
    db.refresh(item)

    # Assertions
    assert item.is_refreshing is False
    assert item.last_error == "Scraper failed"
    assert item.last_checked is not None
    if initial_last_checked:
        assert item.last_checked > initial_last_checked

    # Ensure last_checked is recent (within last minute)
    assert datetime.now(UTC) - item.last_checked.replace(tzinfo=UTC) < timedelta(minutes=1)
