import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.scraper_service import ScraperService, _build_browserless_url, _safe_url_for_log
from app.url_validation import URLValidationError


class TestBuildBrowserlessUrl:
    """Unit tests for _build_browserless_url helper."""

    def test_no_extra_env_vars_returns_base_url(self):
        """When no extra env vars are set, the base URL is returned unchanged."""
        env = {
            "BROWSERLESS_TOKEN": "",
            "BROWSERLESS_BLOCK_ADS": "",
            "BROWSERLESS_STEALTH": "",
            "BROWSERLESS_HEADLESS": "",
            "BROWSERLESS_VIEWPORT_WIDTH": "",
            "BROWSERLESS_VIEWPORT_HEIGHT": "",
        }
        with patch.dict("os.environ", env):
            result = _build_browserless_url("ws://browserless:3000")
        assert result == "ws://browserless:3000"

    def test_token_appended(self):
        """BROWSERLESS_TOKEN is appended as a query parameter."""
        with patch.dict("os.environ", {"BROWSERLESS_TOKEN": "mytoken"}):
            result = _build_browserless_url("ws://browserless:3000/chromium")
        assert "token=mytoken" in result

    def test_block_ads_appended(self):
        """BROWSERLESS_BLOCK_ADS=true is appended as blockAds=true."""
        with patch.dict("os.environ", {"BROWSERLESS_BLOCK_ADS": "true"}):
            result = _build_browserless_url("ws://browserless:3000/chromium")
        assert "blockAds=true" in result

    def test_block_ads_false_not_appended(self):
        """BROWSERLESS_BLOCK_ADS=false does not append blockAds."""
        with patch.dict("os.environ", {"BROWSERLESS_BLOCK_ADS": "false"}):
            result = _build_browserless_url("ws://browserless:3000/chromium")
        assert "blockAds" not in result

    def test_stealth_appended(self):
        """BROWSERLESS_STEALTH=true results in launch JSON containing stealth:true."""
        with patch.dict("os.environ", {"BROWSERLESS_STEALTH": "true"}):
            result = _build_browserless_url("ws://browserless:3000/chromium")
        assert "launch=" in result
        assert "stealth" in result

    def test_headless_appended(self):
        """BROWSERLESS_HEADLESS is included in the launch JSON."""
        with patch.dict("os.environ", {"BROWSERLESS_HEADLESS": "new"}):
            result = _build_browserless_url("ws://browserless:3000/chromium")
        assert "launch=" in result
        assert "headless" in result

    def test_viewport_appended(self):
        """BROWSERLESS_VIEWPORT_WIDTH/HEIGHT are included in the launch JSON."""
        with patch.dict("os.environ", {"BROWSERLESS_VIEWPORT_WIDTH": "1920", "BROWSERLESS_VIEWPORT_HEIGHT": "1080"}):
            result = _build_browserless_url("ws://browserless:3000/chromium")
        assert "launch=" in result
        assert "defaultViewport" in result

    def test_log_url_redacts_token_and_credentials(self):
        result = _safe_url_for_log("wss://user:password@browserless:3000/chromium?token=secret&launch=private")

        assert result == "wss://browserless:3000/chromium"
        assert "secret" not in result
        assert "password" not in result

    def test_invalid_viewport_ignored(self):
        """Non-integer BROWSERLESS_VIEWPORT_WIDTH/HEIGHT are ignored with a warning."""
        with patch.dict("os.environ", {"BROWSERLESS_VIEWPORT_WIDTH": "not-a-number"}):
            result = _build_browserless_url("ws://browserless:3000/chromium")
        assert "defaultViewport" not in result

    def test_headless_bool_true_converted(self):
        """BROWSERLESS_HEADLESS=true is stored as boolean true in the launch JSON."""
        with patch.dict("os.environ", {"BROWSERLESS_HEADLESS": "true"}):
            result = _build_browserless_url("ws://browserless:3000/chromium")
        assert "true" in result  # JSON-serialised boolean, not the string "true"

    def test_headless_new_kept_as_string(self):
        """BROWSERLESS_HEADLESS=new is kept as a string in the launch JSON."""
        with patch.dict("os.environ", {"BROWSERLESS_HEADLESS": "new"}):
            result = _build_browserless_url("ws://browserless:3000/chromium")
        assert "new" in result

    def test_existing_query_params_preserved(self):
        """Existing query params in the base URL are preserved when new params are added."""
        with patch.dict("os.environ", {"BROWSERLESS_TOKEN": "tok"}):
            result = _build_browserless_url("ws://browserless:3000/chromium?existing=1")
        assert "existing=1" in result
        assert "token=tok" in result

    def test_all_params_combined(self):
        """All extra env vars are combined into the URL."""
        env = {
            "BROWSERLESS_TOKEN": "mytoken",
            "BROWSERLESS_BLOCK_ADS": "true",
            "BROWSERLESS_STEALTH": "true",
            "BROWSERLESS_HEADLESS": "new",
            "BROWSERLESS_VIEWPORT_WIDTH": "1920",
            "BROWSERLESS_VIEWPORT_HEIGHT": "1080",
        }
        with patch.dict("os.environ", env):
            result = _build_browserless_url("ws://browserless:3000/chromium")
        assert "token=mytoken" in result
        assert "blockAds=true" in result
        assert "launch=" in result
        assert "stealth" in result
        assert "headless" in result
        assert "defaultViewport" in result


class TestScraperBrowserless:
    """Test Browserless-specific URL resolution logic."""

    @pytest.mark.asyncio
    async def test_connection_error_does_not_expose_token(self):
        playwright = AsyncMock()
        playwright.chromium.connect_over_cdp.side_effect = Exception("connection refused; token=secret")
        starter = MagicMock()
        starter.start = AsyncMock(return_value=playwright)
        ScraperService._browser = None
        ScraperService._playwright = None
        ScraperService._lock = asyncio.Lock()

        with (
            patch("app.services.scraper_service.async_playwright", return_value=starter),
            patch("app.services.scraper_service.BROWSERLESS_URL", "ws://browserless:3000/chromium"),
            patch.dict("os.environ", {"BROWSERLESS_TOKEN": "secret"}),
            pytest.raises(RuntimeError) as exc_info,
        ):
            await ScraperService.initialize()

        assert "secret" not in str(exc_info.value)
        assert "connection was refused" in str(exc_info.value)

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

    @pytest.mark.asyncio
    async def test_request_guard_retries_and_logs_once_per_host(self, caplog):
        context = AsyncMock()
        context.new_page.return_value = AsyncMock()
        browser = AsyncMock()
        browser.new_context.return_value = context
        ScraperService._browser = browser
        ScraperService._dns_semaphore = asyncio.Semaphore(8)
        route = AsyncMock()
        route.request.url = "https://tracking.example/event?secret=one"
        error = URLValidationError("Hostname could not be resolved: tracking.example")

        with (
            patch(
                "app.services.scraper_service.validate_url_async", new_callable=AsyncMock, side_effect=error
            ) as validate,
            caplog.at_level("WARNING", logger="app.services.scraper_service"),
        ):
            async with ScraperService._scoped_context():
                guard = context.route.call_args.args[1]
                await guard(route)
                route.request.url = "https://tracking.example/other?secret=two"
                await guard(route)

        warnings = [record.message for record in caplog.records if "Blocked unsafe browser" in record.message]
        assert validate.await_count == 4
        assert len(warnings) == 1
        assert warnings[0].startswith("Blocked unsafe browser request to https://tracking.example")
        assert "secret" not in warnings[0]
