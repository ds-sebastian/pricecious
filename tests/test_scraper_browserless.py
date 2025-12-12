from unittest.mock import MagicMock, patch

from app.services.scraper_service import ScraperService


class TestScraperBrowserless:
    """Test Browserless-specific URL resolution logic."""

    def test_resolve_ws_url_skips_discovery_for_chromium(self):
        """Test that /chromium URLs skip the discovery process."""
        with patch("app.services.scraper_service.requests.get") as mock_get:
            base_url = "ws://browserless:3000/chromium?token=123"
            resolved = ScraperService._resolve_ws_url(base_url)

            # Should be exactly the same
            assert resolved == base_url

            # requests.get should NOT have been called
            mock_get.assert_not_called()

    def test_resolve_ws_url_skips_discovery_for_chrome(self):
        """Test that /chrome URLs skip the discovery process."""
        with patch("app.services.scraper_service.requests.get") as mock_get:
            base_url = "ws://browserless:3000/chrome"
            resolved = ScraperService._resolve_ws_url(base_url)

            assert resolved == base_url
            mock_get.assert_not_called()

    def test_resolve_ws_url_generic_still_discovers(self):
        """Test that generic URLs still attempt discovery."""
        with patch("app.services.scraper_service.requests.get") as mock_get:
            # Setup mock to return a dynamic URL
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"webSocketDebuggerUrl": "ws://host/devtools/123"}
            mock_get.return_value = mock_response

            base_url = "ws://generic-chrome:9222"
            resolved = ScraperService._resolve_ws_url(base_url)

            assert resolved == "ws://host/devtools/123"
            mock_get.assert_called_once()
