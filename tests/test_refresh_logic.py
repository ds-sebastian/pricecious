from unittest.mock import patch

import pytest

from app import models


@pytest.mark.asyncio
async def test_refresh_all_sets_status(client, db):
    # Create a profile
    profile = models.NotificationProfile(name="Test Profile", apprise_url="mailto://test@example.com")
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    # Create items
    item1 = models.Item(
        url="https://example.com/1", name="Item 1", notification_profile_id=profile.id, is_refreshing=False
    )
    item2 = models.Item(
        url="https://example.com/2", name="Item 2", notification_profile_id=profile.id, is_refreshing=False
    )
    db.add(item1)
    db.add(item2)
    await db.commit()

    # Mock process_item_check to prevent actual execution
    with patch("app.routers.jobs.process_item_check") as mock_process:
        response = await client.post("/api/jobs/refresh-all")
        assert response.status_code == 200
        assert response.json()["message"] == "Triggered refresh for 2 items"

        # Verify mock was called
        assert mock_process.call_count == 2

    # Verify items are marked as refreshing in DB
    # We need to refresh the objects from the DB
    await db.refresh(item1)
    await db.refresh(item2)

    assert item1.is_refreshing is True
    assert item2.is_refreshing is True
