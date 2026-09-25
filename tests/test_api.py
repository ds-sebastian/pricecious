from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from app import checks
from app.database import utcnow
from app.models import Item, PriceHistory
from app.scraper import Capture

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


async def test_unnamed_item_gets_currency_from_its_domain(client):
    created = await create_item(client, url="https://shop.example.de/grinder", name="  ")
    assert created["name"] is None
    assert created["currency"] == "EUR"

    updated = await client.put(f"/api/items/{created['id']}", json=ITEM | {"currency": "chf"})
    assert updated.json()["currency"] == "CHF"


async def test_items_report_deals(client, db):
    item = await create_item(client)
    now = utcnow()
    db.add_all(
        PriceHistory(item_id=item["id"], price=price, timestamp=now - timedelta(days=days))
        for days, price in [(30, 120.0), (10, 110.0), (0, 99.0)]
    )
    await db.execute(Item.__table__.update().values(current_price=99.0))
    await db.commit()

    assert (await client.get("/api/items")).json()[0]["deal"] == "lowest_seen"


@pytest.mark.parametrize(
    ("fields", "status"),
    [
        ({"url": "http://192.168.1.10/admin"}, 422),
        ({"url": "file:///etc/passwd"}, 422),
        ({"currency": "dollars"}, 422),
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

    assert response.json() == {"queued": 1, "recently_checked": 0}
    assert enqueued == [running["id"], idle["id"]]


async def test_check_all_skips_recently_checked_items(client, db, enqueued):
    fresh = await create_item(client, name="Fresh")
    stale = await create_item(client, name="Stale")
    new = await create_item(client, name="New")
    now = utcnow()
    await db.execute(Item.__table__.update().where(Item.id == fresh["id"]).values(last_checked=now))
    await db.execute(
        Item.__table__.update().where(Item.id == stale["id"]).values(last_checked=now - timedelta(minutes=10))
    )
    await db.commit()

    first = (await client.post("/api/items/check-all")).json()
    assert first == {"queued": 2, "recently_checked": 1}
    assert sorted(enqueued) == sorted([stale["id"], new["id"]])

    # A single item can still be checked on demand.
    assert (await client.post(f"/api/items/{fresh['id']}/check")).json() == {"queued": True}


# History


async def test_history_is_paginated_newest_first(client, db):
    item = await create_item(client)
    now = utcnow()
    db.add_all(PriceHistory(item_id=item["id"], price=p, timestamp=now - timedelta(days=p)) for p in range(1, 6))
    await db.commit()

    page = (await client.get(f"/api/items/{item['id']}/history?page=2&size=2")).json()

    assert page["total"] == 5
    assert [record["price"] for record in page["items"]] == [3, 4]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", [10, 20, 30, 40]),
        ("min_price=15&max_price=35", [20, 30]),
        ("stock=in", [10]),
        ("stock=out", [20]),
        ("stock=unknown", [30, 40]),
        ("min_confidence=0.8", [10, 30]),
        ("confidence_below=0.5", [20]),
    ],
)
async def test_history_filters(client, db, query, expected):
    item = await create_item(client)
    now = utcnow()
    readings = [(10, True, 0.9), (20, False, 0.3), (30, None, 0.8), (40, None, None)]
    db.add_all(
        PriceHistory(item_id=item["id"], price=p, in_stock=s, price_confidence=c, timestamp=now - timedelta(hours=p))
        for p, s, c in readings
    )
    await db.commit()

    page = (await client.get(f"/api/items/{item['id']}/history?{query}")).json()

    assert sorted(record["price"] for record in page["items"]) == expected
    assert page["total"] == len(expected)


async def test_invalid_history_filters_are_rejected(client):
    item = await create_item(client)
    for query in ("stock=maybe", "min_confidence=2", "min_price=-1", "sort=asc"):
        assert (await client.get(f"/api/items/{item['id']}/history?{query}")).status_code == 422


async def test_editing_or_deleting_history_updates_current_price(client, db):
    item = await create_item(client)
    now = utcnow()
    older = PriceHistory(item_id=item["id"], price=50, in_stock=True, timestamp=now - timedelta(hours=2))
    latest = PriceHistory(item_id=item["id"], price=5000, in_stock=True, timestamp=now, promotion="Flash sale")
    db.add_all([older, latest])
    await db.commit()

    await client.put(f"/api/history/{latest.id}", json={"price": 55, "in_stock": False})
    current = (await client.get("/api/items")).json()[0]
    assert (current["current_price"], current["in_stock"], current["promotion"]) == (55, False, "Flash sale")

    await client.delete(f"/api/history/{latest.id}")
    current = (await client.get("/api/items")).json()[0]
    assert (current["current_price"], current["promotion"]) == (50, None)

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


# AI settings test


@pytest.fixture
async def item_with_screenshot(client, png):
    item = await create_item(client)
    path = checks.screenshot_file(item["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    return item


async def test_ai_test_uses_unsaved_settings_and_saved_screenshot(client, item_with_screenshot, png, monkeypatch):
    ask = AsyncMock(return_value='{"price": 12.5, "currency": "usd", "price_confidence": 0.9}')
    monkeypatch.setattr("app.ai.ask", ask)

    response = await client.post(
        "/api/settings/test-ai", json={"item_id": item_with_screenshot["id"], "settings": {"ai_model": "llava"}}
    )

    result = response.json()
    assert result["extraction"]["price"] == 12.5
    assert result["extraction"]["currency"] == "USD"
    assert result["error"] is None
    screenshot, settings = ask.await_args.args
    assert screenshot == png
    assert settings.ai_model == "llava"
    assert (await client.get("/api/settings")).json()["ai_model"] == "gemma3:4b"  # nothing was saved


async def test_ai_test_reports_unparseable_replies_and_failures(client, item_with_screenshot, monkeypatch):
    monkeypatch.setattr("app.ai.ask", AsyncMock(return_value="I think it costs about twelve dollars"))
    result = (await client.post("/api/settings/test-ai", json={"item_id": item_with_screenshot["id"]})).json()
    assert result["extraction"] is None
    assert result["reply"] == "I think it costs about twelve dollars"
    assert "did not return JSON" in result["error"]

    monkeypatch.setattr("app.ai.ask", AsyncMock(side_effect=RuntimeError("model 'llava' not found")))
    failed = await client.post("/api/settings/test-ai", json={"item_id": item_with_screenshot["id"]})
    assert failed.status_code == 502
    assert failed.json()["detail"] == "The model call failed: model 'llava' not found"


async def test_ai_test_validates_settings(client, item_with_screenshot):
    response = await client.post(
        "/api/settings/test-ai", json={"item_id": item_with_screenshot["id"], "settings": {"ai_temperature": 9}}
    )
    assert response.status_code == 422


async def test_ai_test_captures_the_page_when_page_text_is_wanted(client, item_with_screenshot, png, monkeypatch):
    capture = AsyncMock(return_value=Capture(png, "Price: $12.50 " * 10))
    monkeypatch.setattr("app.scraper.capture", capture)
    ask = AsyncMock(return_value='{"price": 12.5}')
    monkeypatch.setattr("app.ai.ask", ask)

    await client.post(
        "/api/settings/test-ai",
        json={
            "item_id": item_with_screenshot["id"],
            "settings": {"text_context_enabled": True, "text_context_length": 20},
        },
    )

    capture.assert_awaited_once()
    assert ask.await_args.kwargs["page_text"] == "Price: $12.50 Price:"
