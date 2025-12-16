from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.scraper_service import ScraperService


class TestScraperBrowserless:
    """Test Browserless-specific URL resolution logic."""

    @pytest.mark.asyncio
    async def test_resolve_ws_url_skips_discovery_for_chromium(self):
        """Test that /chromium URLs skip the discovery process."""
        with patch("app.services.scraper_service.httpx.AsyncClient") as mock_client:
            base_url = "ws://browserless:3000/chromium?token=123"
            resolved = await ScraperService._resolve_ws_url(base_url)

            # Should be exactly the same
            assert resolved == base_url

            # httpx should NOT have been called
            mock_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolve_ws_url_skips_discovery_for_chrome(self):
        """Test that /chrome URLs skip the discovery process."""
        with patch("app.services.scraper_service.httpx.AsyncClient") as mock_client:
            base_url = "ws://browserless:3000/chrome"
            resolved = await ScraperService._resolve_ws_url(base_url)

            assert resolved == base_url
            mock_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolve_ws_url_generic_still_discovers(self):
        """Test that generic URLs still attempt discovery."""
        with patch("app.services.scraper_service.httpx.AsyncClient") as mock_client_cls:
            # Setup mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"webSocketDebuggerUrl": "ws://host/devtools/123"}

            # Setup async client context manager
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            base_url = "ws://generic-chrome:9222"
            resolved = await ScraperService._resolve_ws_url(base_url)

            assert resolved == "ws://host/devtools/123"
            mock_client.get.assert_called_once()
