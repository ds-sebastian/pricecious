# Since we are using sync TestClient with async endpoints, FastAPI handles the loop.
# However, if we want to test async functions directly, we need pytest-asyncio.
# For API tests, TestClient is fine as it wraps the app.


def test_read_main(client):
    response = client.get("/api/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Pricecious API"}


def test_create_notification_profile(client):
    response = client.post(
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


def test_create_item(client):
    # First create a profile
    profile_response = client.post(
        "/api/notification-profiles",
        json={"name": "Test Profile 2", "apprise_url": "mailto://test@example.com"},
    )
    profile_id = profile_response.json()["id"]

    response = client.post(
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


def test_get_settings(client):
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_update_setting(client):
    response = client.post("/api/settings", json={"key": "test_key", "value": "test_value"})
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "test_key"
    assert data["value"] == "test_value"


# Add test for check_item to ensure background task triggering works
# Note: This doesn't verify the background task execution, just the endpoint
def test_check_item_trigger(client):
    # Create item first
    response = client.post(
        "/api/items",
        json={"url": "https://example.com/check", "name": "Check Product", "target_price": 100.0},
    )
    item_id = response.json()["id"]

    response = client.post(f"/api/items/{item_id}/check")
    assert response.status_code == 200
    assert response.json() == {"message": "Check triggered"}
