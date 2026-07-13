import asyncio
from datetime import timedelta
from unittest.mock import patch

import pytest

from app import models
from app.services.item_service import REFRESH_CLAIM_TIMEOUT, ItemService
from app.services.scheduler_service import process_item_check
from app.utils.datetime_utils import utc_now_naive


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


@pytest.mark.asyncio
async def test_refresh_all_skips_already_running_items(client, db):
    running = models.Item(
        url="https://example.com/running",
        name="Running",
        is_refreshing=True,
        refresh_started_at=utc_now_naive(),
    )
    idle = models.Item(url="https://example.com/idle", name="Idle", is_refreshing=False)
    db.add_all([running, idle])
    await db.commit()

    with patch("app.routers.jobs.process_item_check") as mock_process:
        response = await client.post("/api/jobs/refresh-all")

    assert response.json()["message"] == "Triggered refresh for 1 items"
    mock_process.assert_called_once_with(idle.id)


@pytest.mark.asyncio
async def test_due_items_are_claimed_before_checks_start(db):
    item = models.Item(url="https://example.com/due", name="Due", is_refreshing=False, is_active=True)
    db.add(item)
    await db.commit()

    class SessionContext:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *_args):
            return None

    with patch("app.services.item_service.database.AsyncSessionLocal", return_value=SessionContext()):
        due = await ItemService.get_due_items()
        due_again = await ItemService.get_due_items()

    assert [entry[0] for entry in due] == [item.id]
    assert due_again == []
    await db.refresh(item)
    assert item.is_refreshing is True
    assert item.refresh_started_at is not None


@pytest.mark.asyncio
async def test_stale_refresh_claim_can_be_reclaimed(db):
    item = models.Item(
        url="https://example.com/stale",
        name="Stale",
        is_refreshing=True,
        is_active=True,
        refresh_started_at=utc_now_naive() - REFRESH_CLAIM_TIMEOUT - timedelta(minutes=1),
    )
    db.add(item)
    await db.commit()
    previous_claim = item.refresh_started_at

    claimed = await ItemService.claim_items_for_refresh(db, [item.id])

    assert claimed == [item.id]
    await db.refresh(item)
    assert item.is_refreshing is True
    assert item.refresh_started_at > previous_claim


@pytest.mark.asyncio
async def test_cancelling_queued_check_releases_claim(db):
    item = models.Item(url="https://example.com/cancelled", name="Cancelled", is_active=True)
    db.add(item)
    await db.commit()
    assert await ItemService.claim_items_for_refresh(db, [item.id]) == [item.id]

    class SessionContext:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *_args):
            return None

    semaphore = asyncio.Semaphore(0)
    with patch("app.services.scheduler_service.database.AsyncSessionLocal", return_value=SessionContext()):
        task = asyncio.create_task(process_item_check(item.id, semaphore))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    await db.refresh(item)
    assert item.is_refreshing is False
    assert item.refresh_started_at is None
