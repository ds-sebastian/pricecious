from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_test_notification_endpoint(client):
    with patch("app.services.notification_service.notification_sender.send_notification") as mock_send:
        response = await client.post(
            "/api/notification-profiles/test", json={"apprise_url": "mailto://test@example.com"}
        )

        assert response.status_code == 200
        assert response.json() == {"ok": True}

        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        # send_notification(urls: list, title: str, body: str)
        assert args[0] == ["mailto://test@example.com"]
        assert args[1] == "Test Notification"
