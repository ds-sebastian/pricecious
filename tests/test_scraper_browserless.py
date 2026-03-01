from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.scraper_service import ScraperService, _build_browserless_url


class TestBuildBrowserlessUrl:
    """Unit tests for _build_browserless_url helper."""

    def test_no_extra_env_vars_returns_base_url(self):
        """When no extra env vars are set, the base URL is returned unchanged."""
        with patch.dict("os.environ", {}, clear=False):
            for key in ("BROWSERLESS_TOKEN", "BROWSERLESS_BLOCK_ADS", "BROWSERLESS_LAUNCH_OPTS_BASE64"):
                patch.dict("os.environ", {key: ""}).start()
            result = _build_browserless_url("ws://browserless:3000")
        assert result == "ws://browserless:3000"

    def test_token_appended(self):
        """BROWSERLESS_TOKEN is appended as a query parameter."""
        with patch.dict("os.environ", {"BROWSERLESS_TOKEN": "mytoken", "BROWSERLESS_BLOCK_ADS": "", "BROWSERLESS_LAUNCH_OPTS_BASE64": ""}):
            result = _build_browserless_url("ws://browserless:3000/chromium")
        assert "token=mytoken" in result

    def test_block_ads_appended(self):
        """BROWSERLESS_BLOCK_ADS=true is appended as blockAds=true."""
        with patch.dict("os.environ", {"BROWSERLESS_BLOCK_ADS": "true", "BROWSERLESS_TOKEN": "", "BROWSERLESS_LAUNCH_OPTS_BASE64": ""}):
            result = _build_browserless_url("ws://browserless:3000/chromium")
        assert "blockAds=true" in result

    def test_block_ads_false_not_appended(self):
        """BROWSERLESS_BLOCK_ADS=false does not append blockAds."""
        with patch.dict("os.environ", {"BROWSERLESS_BLOCK_ADS": "false", "BROWSERLESS_TOKEN": "", "BROWSERLESS_LAUNCH_OPTS_BASE64": ""}):
            result = _build_browserless_url("ws://browserless:3000/chromium")
        assert "blockAds" not in result

    def test_launch_opts_base64_appended(self):
        """Valid BROWSERLESS_LAUNCH_OPTS_BASE64 is decoded and appended as launch param."""
        import base64
        import json
        launch_opts = {"stealth": True, "defaultViewport": {"width": 1920, "height": 1080}}
        b64 = base64.b64encode(json.dumps(launch_opts).encode()).decode()
        with patch.dict("os.environ", {"BROWSERLESS_LAUNCH_OPTS_BASE64": b64, "BROWSERLESS_TOKEN": "", "BROWSERLESS_BLOCK_ADS": ""}):
            result = _build_browserless_url("ws://browserless:3000/chromium")
        assert "launch=" in result

    def test_invalid_launch_opts_base64_ignored(self):
        """Invalid BROWSERLESS_LAUNCH_OPTS_BASE64 is ignored and a warning is logged."""
        with patch.dict("os.environ", {"BROWSERLESS_LAUNCH_OPTS_BASE64": "not-valid-base64!!!", "BROWSERLESS_TOKEN": "", "BROWSERLESS_BLOCK_ADS": ""}):
            result = _build_browserless_url("ws://browserless:3000/chromium")
        assert "launch" not in result

    def test_existing_query_params_preserved(self):
        """Existing query params in the base URL are preserved when new params are added."""
        with patch.dict("os.environ", {"BROWSERLESS_TOKEN": "tok", "BROWSERLESS_BLOCK_ADS": "", "BROWSERLESS_LAUNCH_OPTS_BASE64": ""}):
            result = _build_browserless_url("ws://browserless:3000/chromium?existing=1")
        assert "existing=1" in result
        assert "token=tok" in result

    def test_all_params_combined(self):
        """All three extra env vars are combined into the URL."""
        import base64
        import json
        launch_opts = {"stealth": True}
        b64 = base64.b64encode(json.dumps(launch_opts).encode()).decode()
        with patch.dict("os.environ", {
            "BROWSERLESS_TOKEN": "mytoken",
            "BROWSERLESS_BLOCK_ADS": "true",
            "BROWSERLESS_LAUNCH_OPTS_BASE64": b64,
        }):
            result = _build_browserless_url("ws://browserless:3000/chromium")
        assert "token=mytoken" in result
        assert "blockAds=true" in result
        assert "launch=" in result


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
