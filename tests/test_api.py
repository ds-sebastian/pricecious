from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from app import checks
from app.database import utcnow
from app.models import Item, PriceHistory

ITEM = {"url": "https://example.com/product", "name": "Widget", "target_price": 100}


@pytest.fixture
def enqueued(monkeypatch):
    ids = []
    monkeypatch.setattr(checks, "enqueue", lambda item_ids, **_: ids.extend(item_ids))
    return ids


async def create_item(client, **fields):
    response = await client.post("/api/items", json=ITEM | fields)
    assert response.status_code == 201, response.text
    return response.json()


# Items


async def test_create_and_list_items(client):
    created = await create_item(client, tags=" gpu,  ssd ,gpu, ", selector="  ")

    assert created["tags"] == "gpu, ssd"
    assert created["selector"] is None
    assert created["interval"] == 60
    assert created["next_check"] is None
    listed = (await client.get("/api/items")).json()
    assert [item["name"] for item in listed] == ["Widget"]


async def test_next_check_is_utc(client, db):
    item = await create_item(client, check_interval_minutes=30)
    await db.execute(Item.__table__.update().values(last_checked=utcnow()))
    await db.commit()

    listed = (await client.get("/api/items")).json()[0]
    assert listed["id"] == item["id"]
    assert listed["last_checked"].endswith("Z") or listed["last_checked"].endswith("+00:00")
    assert listed["interval"] == 30


@pytest.mark.parametrize(
    ("fields", "status"),
    [
        ({"url": "http://192.168.1.10/admin"}, 422),
        ({"url": "file:///etc/passwd"}, 422),
        ({"name": "   "}, 422),
        ({"target_price": -1}, 422),
        ({"check_interval_minutes": 1}, 422),
        ({"notification_profile_id": 999}, 404),
    ],
)
async def test_invalid_items_are_rejected(client, fields, status):
    assert (await client.post("/api/items", json=ITEM | fields)).status_code == status


async def test_resuming_a_paused_item_resets_failures(client, db):
    item = await create_item(client)
    await db.execute(
        Item.__table__.update().values(
            is_active=False, consecutive_failures=20, error_type="auto_deactivated", last_error="Paused"
        )
    )
    await db.commit()

    updated = (await client.put(f"/api/items/{item['id']}", json=ITEM | {"is_active": True})).json()

    assert updated["is_active"] is True
    assert updated["consecutive_failures"] == 0
    assert updated["last_error"] is None


async def test_delete_item_removes_history_and_screenshot(client, db):
    item = await create_item(client)
    db.add(PriceHistory(item_id=item["id"], price=10))
    await db.commit()
    screenshot = checks.screenshot_file(item["id"])
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    screenshot.write_bytes(b"png")

    assert (await client.delete(f"/api/items/{item['id']}")).status_code == 204

    assert (await client.get("/api/items")).json() == []
    assert (await db.scalars(PriceHistory.__table__.select())).all() == []
    assert not screenshot.exists()
    assert (await client.delete(f"/api/items/{item['id']}")).status_code == 404


async def test_check_is_queued_once(client, enqueued):
    item = await create_item(client)

    first = await client.post(f"/api/items/{item['id']}/check")
    second = await client.post(f"/api/items/{item['id']}/check")

    assert (first.json(), second.json()) == ({"queued": True}, {"queued": False})
    assert enqueued == [item["id"]]
    assert (await client.get("/api/items")).json()[0]["is_refreshing"] is True


async def test_check_all_skips_running_and_paused_items(client, enqueued):
    idle = await create_item(client, name="Idle")
    running = await create_item(client, name="Running")
    await create_item(client, name="Paused", is_active=False)
    await client.post(f"/api/items/{running['id']}/check")

    response = await client.post("/api/items/check-all")

    assert response.json() == {"queued": 1}
    assert enqueued == [running["id"], idle["id"]]


# History


async def test_history_is_paginated_newest_first(client, db):
    item = await create_item(client)
    now = utcnow()
    db.add_all(PriceHistory(item_id=item["id"], price=p, timestamp=now - timedelta(days=p)) for p in range(1, 6))
    await db.commit()

    page = (await client.get(f"/api/items/{item['id']}/history?page=2&size=2")).json()

    assert page["total"] == 5
    assert [record["price"] for record in page["items"]] == [3, 4]


async def test_editing_or_deleting_history_updates_current_price(client, db):
    item = await create_item(client)
    now = utcnow()
    older = PriceHistory(item_id=item["id"], price=50, in_stock=True, timestamp=now - timedelta(hours=2))
    latest = PriceHistory(item_id=item["id"], price=5000, in_stock=True, timestamp=now)
    db.add_all([older, latest])
    await db.commit()

    await client.put(f"/api/history/{latest.id}", json={"price": 55, "in_stock": False})
    current = (await client.get("/api/items")).json()[0]
    assert (current["current_price"], current["in_stock"]) == (55, False)

    await client.delete(f"/api/history/{latest.id}")
    assert (await client.get("/api/items")).json()[0]["current_price"] == 50

    await client.delete(f"/api/history/{older.id}")
    assert (await client.get("/api/items")).json()[0]["current_price"] is None


async def test_analytics_endpoint(client, db):
    item = await create_item(client)
    db.add_all(PriceHistory(item_id=item["id"], price=p, timestamp=utcnow() - timedelta(hours=p)) for p in (1, 2))
    await db.commit()

    data = (await client.get(f"/api/items/{item['id']}/analytics?days=7&std_dev_threshold=2")).json()

    assert data["stats"]["min"] == 1
    assert len(data["history"]) == 2
    assert (await client.get("/api/items/999/analytics")).status_code == 404


# Settings


async def test_settings_have_defaults_and_validate(client):
    settings = (await client.get("/api/settings")).json()
    assert settings["ai_model"] == "gemma3:4b"
    assert settings["smart_scroll_enabled"] is False

    saved = (await client.put("/api/settings", json={"ai_temperature": 0.4, "smart_scroll_enabled": True})).json()
    assert (saved["ai_temperature"], saved["smart_scroll_enabled"]) == (0.4, True)

    assert (await client.put("/api/settings", json={"ai_temperature": 5})).status_code == 422
    assert (await client.put("/api/settings", json={"unknown": 1})).status_code == 422
    assert (await client.put("/api/settings", json={"refresh_interval_minutes": 0})).status_code == 422


async def test_api_key_is_never_returned(client):
    saved = (await client.put("/api/settings", json={"ai_api_key": "sk-secret"})).json()
    assert saved["ai_api_key"] == "********"

    # Sending the mask back (an untouched form field) keeps the stored key.
    await client.put("/api/settings", json={"ai_api_key": "********", "ai_model": "gpt-5-mini"})
    assert (await client.get("/api/settings")).json()["ai_api_key"] == "********"

    await client.put("/api/settings", json={"ai_api_key": ""})
    assert (await client.get("/api/settings")).json()["ai_api_key"] == ""


async def test_forecast_refresh_starts_once(client, monkeypatch):
    spawned = []
    monkeypatch.setattr(checks, "spawn", lambda coro: spawned.append(coro.close()))
    monkeypatch.setattr("app.forecast.is_running", lambda: False)
    assert (await client.post("/api/forecasts/refresh")).json() == {"started": True}
    monkeypatch.setattr("app.forecast.is_running", lambda: True)
    assert (await client.post("/api/forecasts/refresh")).json() == {"started": False}
    assert len(spawned) == 1


# Notification profiles

PROFILE = {"name": "Discord", "apprise_url": "discord://webhook_id/webhook_token"}


async def test_profile_url_is_masked_and_kept_when_unchanged(client, monkeypatch):
    created = (await client.post("/api/notification-profiles", json=PROFILE)).json()
    assert created["apprise_url"] == "discord://********"

    renamed = PROFILE | {"name": "Renamed", "apprise_url": created["apprise_url"]}
    assert (await client.put(f"/api/notification-profiles/{created['id']}", json=renamed)).status_code == 200

    send = AsyncMock(return_value=True)
    monkeypatch.setattr("app.notify.send", send)
    assert (await client.post(f"/api/notification-profiles/{created['id']}/test")).status_code == 204
    assert send.await_args.args[0] == PROFILE["apprise_url"]


async def test_profile_validation(client):
    await client.post("/api/notification-profiles", json=PROFILE)
    duplicate = await client.post("/api/notification-profiles", json=PROFILE)
    invalid = await client.post("/api/notification-profiles", json=PROFILE | {"name": "x", "apprise_url": "nope"})
    assert (duplicate.status_code, invalid.status_code) == (409, 422)


async def test_deleting_profile_unlinks_items(client):
    profile = (await client.post("/api/notification-profiles", json=PROFILE)).json()
    await create_item(client, notification_profile_id=profile["id"])

    assert (await client.delete(f"/api/notification-profiles/{profile['id']}")).status_code == 204
    assert (await client.get("/api/items")).json()[0]["notification_profile_id"] is None


async def test_failed_test_notification_is_reported(client, monkeypatch):
    monkeypatch.setattr("app.notify.send", AsyncMock(return_value=False))
    response = await client.post("/api/notification-profiles/test", json={"apprise_url": "json://example.com"})
    assert response.status_code == 502


# App shell and security


async def test_health_and_unknown_api_paths(client):
    assert (await client.get("/health")).json() == {"status": "ok"}
    assert (await client.get("/api/nope")).status_code == 404


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "http://test", "Sec-Fetch-Site": "same-origin"},
        {"Origin": "https://trusted.example", "Sec-Fetch-Site": "cross-site"},
        {"Host": "prices.lan", "Origin": "https://prices.lan", "X-Forwarded-Proto": "https"},
    ],
)
async def test_same_origin_and_trusted_writes_are_allowed(client, headers):
    response = await client.put("/api/settings", json={"ai_model": "x"}, headers=headers)
    assert response.status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
async def test_cross_origin_writes_are_rejected(client, headers):
    assert (await client.post("/api/items/check-all", headers=headers)).status_code == 403


async def test_trusted_origin_gets_cors_headers(client):
    response = await client.get("/api/settings", headers={"Origin": "https://trusted.example"})
    assert response.headers["access-control-allow-origin"] == "https://trusted.example"
