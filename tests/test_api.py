from unittest.mock import AsyncMock, patch

import pytest

from app.main import _cors_origins


@pytest.mark.asyncio
async def test_read_main(client):
    response = await client.get("/api/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Pricecious API"}


@pytest.mark.asyncio
async def test_api_and_health_require_no_auth(client):
    assert (await client.get("/api/")).status_code == 200
    assert (await client.get("/health")).status_code == 200


@pytest.mark.asyncio
async def test_same_origin_and_direct_mutations_are_allowed(client):
    direct = await client.post("/api/settings", json={"key": "direct", "value": "ok"})
    same_origin = await client.post(
        "/api/settings",
        json={"key": "browser", "value": "ok"},
        headers={"Origin": "http://test", "Sec-Fetch-Site": "same-origin"},
    )
    assert direct.status_code == same_origin.status_code == 200


@pytest.mark.asyncio
async def test_forwarded_same_origin_mutation_is_allowed(client):
    response = await client.post(
        "/api/settings",
        json={"key": "proxied", "value": "ok"},
        headers={
            "Host": "pricecious.example",
            "Origin": "https://pricecious.example",
            "Sec-Fetch-Site": "same-origin",
            "X-Forwarded-Proto": "https",
        },
    )
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["post", "put", "delete"])
async def test_cross_origin_mutations_are_rejected(client, method):
    response = await getattr(client, method)(
        "/api/settings", headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cross_site_fetch_metadata_without_origin_is_rejected(client):
    response = await client.post("/api/jobs/refresh-all", headers={"Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_configured_cross_origin_is_allowed(client):
    response = await client.post(
        "/api/settings",
        json={"key": "trusted", "value": "ok"},
        headers={"Origin": "https://trusted.example", "Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://trusted.example"


def test_cors_defaults_to_same_origin(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS")
    assert _cors_origins() == set()


@pytest.mark.asyncio
async def test_create_notification_profile(client):
    response = await client.post(
        "/api/notification-profiles",
        json={
            "name": "Test Profile",
            "apprise_url": "mailto://test@example.com",
            "notify_on_price_drop": True,
            "notify_on_target_price": True,
            "price_drop_threshold_percent": 10.0,
            "notify_on_stock_change": True,
            "check_interval_minutes": 60,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Profile"
    assert "id" in data
    assert data["apprise_url"] == "**********"


@pytest.mark.asyncio
async def test_update_notification_profile(client):
    # Create a profile first
    response = await client.post(
        "/api/notification-profiles",
        json={
            "name": "Update Test Profile",
            "apprise_url": "mailto://test@example.com",
        },
    )
    profile_id = response.json()["id"]

    # Update the profile
    response = await client.put(
        f"/api/notification-profiles/{profile_id}",
        json={
            "name": "Updated Profile Name",
            "apprise_url": "mailto://updated@example.com",
            "notify_on_price_drop": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Profile Name"
    assert data["apprise_url"] == "**********"
    assert data["notify_on_price_drop"] is False
    assert data["id"] == profile_id


@pytest.mark.asyncio
async def test_saved_notification_profile_uses_stored_url(client):
    response = await client.post(
        "/api/notification-profiles",
        json={"name": "Stored URL Profile", "apprise_url": "mailto://stored@example.com"},
    )
    profile_id = response.json()["id"]

    with patch("app.notification_sender.send_notification", new_callable=AsyncMock) as mock_send:
        response = await client.post(f"/api/notification-profiles/{profile_id}/test")

    assert response.status_code == 200
    mock_send.assert_awaited_once_with(
        ["mailto://stored@example.com"],
        "Test Notification",
        "This is a test notification from Pricecious.",
    )


@pytest.mark.asyncio
async def test_create_item(client):
    # First create a profile
    profile_response = await client.post(
        "/api/notification-profiles",
        json={"name": "Test Profile 2", "apprise_url": "mailto://test@example.com"},
    )
    profile_id = profile_response.json()["id"]

    response = await client.post(
        "/api/items",
        json={
            "url": "https://example.com/product",
            "name": "Test Product",
            "target_price": 100.0,
            "notification_profile_id": profile_id,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Product"
    assert data["url"] == "https://example.com/product"
    assert data["notification_profile_id"] == profile_id


@pytest.mark.asyncio
async def test_create_item_uses_async_url_validation(client):
    with patch("app.services.item_service.validate_url_async", new_callable=AsyncMock) as mock_validate:
        response = await client.post(
            "/api/items",
            json={"url": "https://example.com/async-validation", "name": "Async Validation"},
        )

    assert response.status_code == 200
    mock_validate.assert_awaited_once_with("https://example.com/async-validation")


@pytest.mark.asyncio
async def test_get_settings(client):
    response = await client.get("/api/settings")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_update_setting(client):
    response = await client.post("/api/settings", json={"key": "test_key", "value": "test_value"})
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "test_key"
    assert data["value"] == "test_value"


@pytest.mark.asyncio
async def test_secret_settings_are_redacted(client):
    response = await client.post("/api/settings", json={"key": "ai_api_key", "value": "super-secret"})
    assert response.json()["value"] == "**********"
    assert (await client.get("/api/settings")).json()[0]["value"] == "**********"


@pytest.mark.asyncio
async def test_max_tokens_setting_is_not_redacted(client):
    response = await client.post("/api/settings", json={"key": "ai_max_tokens", "value": "500"})
    assert response.json()["value"] == "500"


# Add test for check_item to ensure background task triggering works
# Note: This doesn't verify the background task execution, just the endpoint
@pytest.mark.asyncio
async def test_check_item_trigger(client):
    # Create item first
    response = await client.post(
        "/api/items",
        json={"url": "https://example.com/check", "name": "Check Product", "target_price": 100.0},
    )
    item_id = response.json()["id"]

    response = await client.post(f"/api/items/{item_id}/check")
    assert response.status_code == 200
    assert response.json() == {"message": "Check triggered"}


@pytest.mark.asyncio
async def test_check_item_does_not_enqueue_twice(client):
    response = await client.post(
        "/api/items",
        json={"url": "https://example.com/check-once", "name": "Check Once", "target_price": 100.0},
    )
    item_id = response.json()["id"]

    with patch("app.routers.items.process_item_check") as mock_process:
        first = await client.post(f"/api/items/{item_id}/check")
        second = await client.post(f"/api/items/{item_id}/check")

    assert first.json() == {"message": "Check triggered"}
    assert second.json() == {"message": "Check already in progress"}
    mock_process.assert_called_once_with(item_id)
