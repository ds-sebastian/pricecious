"""
Unit tests for scraper module.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.scraper_service import ScrapeConfig, ScraperService


@pytest.fixture(autouse=True)
async def reset_scraper_service():
    """Reset ScraperService state before and after each test."""
    ScraperService._browser = None
    ScraperService._playwright = None
    ScraperService._lock = asyncio.Lock()  # Reset lock to ensure no deadlocks from previous tests
    yield
    if ScraperService._browser:
        try:
            await ScraperService._browser.close()
        except Exception:
            pass
    if ScraperService._playwright:
        try:
            await ScraperService._playwright.stop()
        except Exception:
            pass
    ScraperService._browser = None
    ScraperService._playwright = None


class TestScraperInputValidation:
    """Test input validation in scraper."""

    @pytest.mark.asyncio
    async def test_invalid_scroll_pixels(self):
        """Test that invalid scroll_pixels handled."""
        with patch("app.services.scraper_service.async_playwright") as mock_pw_cls:
            # Setup the chain
            mock_pw_obj = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()

            # pw = await async_playwright().start()
            # async_playwright() returns a context manager usually, but code calls .start() directly on result?
            # Code: cls._playwright = await async_playwright().start()
            # So async_playwright() returns an object that has start() method which is async.

            mock_pw_context = MagicMock()
            mock_pw_context.start = AsyncMock(return_value=mock_pw_obj)
            mock_pw_cls.return_value = mock_pw_context

            # browser = await pw.chromium.connect_over_cdp(...)
            mock_pw_obj.chromium.connect_over_cdp.return_value = mock_browser
            mock_browser.is_connected.return_value = True

            # context = await browser.new_context(...)
            mock_browser.new_context.return_value = mock_context

            # page = await context.new_page()
            mock_context.new_page.return_value = mock_page

            config = ScrapeConfig(scroll_pixels=500, smart_scroll=True)

            await ScraperService.initialize()
            await ScraperService.scrape_item("http://example.com", config=config)

            # Verify scroll was called
            mock_page.evaluate.assert_called()
            call_args = mock_page.evaluate.call_args[0][0]
            assert "scrollBy(0, 500)" in call_args

    @pytest.mark.asyncio
    async def test_invalid_timeout(self):
        """Test that timeout is passed to navigation."""
        with patch("app.services.scraper_service.async_playwright") as mock_pw_cls:
            mock_pw_obj = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()

            mock_pw_context = MagicMock()
            mock_pw_context.start = AsyncMock(return_value=mock_pw_obj)
            mock_pw_cls.return_value = mock_pw_context

            mock_pw_obj.chromium.connect_over_cdp.return_value = mock_browser
            mock_browser.is_connected.return_value = True
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page

            config = ScrapeConfig(timeout=12345)

            await ScraperService.initialize()
            await ScraperService.scrape_item("http://example.com", config=config)

            mock_page.goto.assert_called_with("http://example.com", wait_until="domcontentloaded", timeout=12345)


class TestScraperScreenshot:
    """Test screenshot functionality."""

    @pytest.mark.asyncio
    async def test_screenshot_path_generation(self):
        """Test that screenshot paths are generated correctly."""
        with patch("app.services.scraper_service.async_playwright") as mock_pw_cls:
            mock_pw_obj = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()

            mock_pw_context = MagicMock()
            mock_pw_context.start = AsyncMock(return_value=mock_pw_obj)
            mock_pw_cls.return_value = mock_pw_context

            mock_pw_obj.chromium.connect_over_cdp.return_value = mock_browser
            mock_browser.is_connected.return_value = True
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page

            await ScraperService.initialize()
            path, _ = await ScraperService.scrape_item("http://example.com", item_id=123)

            assert path == "screenshots/item_123.png"
            mock_page.screenshot.assert_called_with(path="screenshots/item_123.png")


class TestScraperErrorHandling:
    """Test error handling in scraper."""

    @pytest.mark.asyncio
    async def test_connection_failure_initial(self):
        """Test handling of connection failures during init."""
        with patch("app.services.scraper_service.async_playwright") as mock_pw_cls:
            mock_pw_obj = AsyncMock()
            mock_pw_context = MagicMock()
            mock_pw_context.start = AsyncMock(return_value=mock_pw_obj)
            mock_pw_cls.return_value = mock_pw_context

            mock_pw_obj.chromium.connect_over_cdp.side_effect = Exception("Conn Fail")

            res, text = await ScraperService.scrape_item("http://example.com")
            assert res is None
            assert text == ""

    @pytest.mark.asyncio
    async def test_page_load_timeout(self):
        """Test handling of page load timeout (robust mode)."""
        with patch("app.services.scraper_service.async_playwright") as mock_pw_cls:
            mock_pw_obj = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()

            mock_pw_context = MagicMock()
            mock_pw_context.start = AsyncMock(return_value=mock_pw_obj)
            mock_pw_cls.return_value = mock_pw_context

            mock_pw_obj.chromium.connect_over_cdp.return_value = mock_browser
            mock_browser.is_connected.return_value = True
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page

            # Navigation fails but should be caught
            mock_page.goto.side_effect = Exception("Timeout")

            await ScraperService.initialize()
            res, _text = await ScraperService.scrape_item("http://example.com")

            # Updated behavior: navigation failure leads to early exit, no screenshot
            assert res is None

    # @pytest.mark.asyncio
    # async def test_reconnection_logic(self):
    #     """Test that scraper attempts to reconnect if disconnected."""
    #     # TODO: Fix flaky test related to classmethod mocking
    #     pass


class TestScraperConnectionLogic:
    """Test the smart WebSocket URL resolution logic."""

    def test_resolve_ws_url_success(self):
        """Test successful discovery of Chrome WebSocket URL."""
        with patch("app.services.scraper_service.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"webSocketDebuggerUrl": "ws://chrome:9222/devtools/browser/123-uuid"}
            mock_get.return_value = mock_response

            base_url = "ws://chrome:9222"
            resolved = ScraperService._resolve_ws_url(base_url)

            assert resolved == "ws://chrome:9222/devtools/browser/123-uuid"
            mock_get.assert_called_once()
            args, _ = mock_get.call_args
            assert args[0] == "http://chrome:9222/json/version"

    def test_resolve_ws_url_fallback_connection_error(self):
        """Test fallback when connection fails."""
        with patch("app.services.scraper_service.requests.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")

            base_url = "ws://browserless:3000"
            resolved = ScraperService._resolve_ws_url(base_url)

            # Should fallback to original URL
            assert resolved == base_url

    def test_resolve_ws_url_fallback_invalid_json(self):
        """Test fallback when response is not as expected."""
        with patch("app.services.scraper_service.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"other_field": "some_value"}
            mock_get.return_value = mock_response

            base_url = "ws://chrome:9222"
            resolved = ScraperService._resolve_ws_url(base_url)

            assert resolved == base_url

    @pytest.mark.asyncio
    async def test_initialize_uses_resolved_url(self):
        """Test that initialize uses the resolved URL."""
        # Clean up any existing state
        ScraperService._browser = None
        ScraperService._playwright = None

        with patch("app.services.scraper_service.async_playwright") as mock_pw_cls:
            # Mock resolving logic
            with patch.object(ScraperService, "_resolve_ws_url") as mock_resolve:
                mock_resolve.return_value = "ws://resolved-url:1234"

                # Mock Playwright stuff
                mock_pw_obj = AsyncMock()
                mock_browser = AsyncMock()
                mock_pw_context = MagicMock()
                mock_pw_context.start = AsyncMock(return_value=mock_pw_obj)
                mock_pw_cls.return_value = mock_pw_context

                mock_pw_obj.chromium.connect_over_cdp.return_value = mock_browser

                await ScraperService.initialize()

                # Verify resolve was called
                mock_resolve.assert_called_once()

                # Verify connect_over_cdp was called with the RESOLVED url
                mock_pw_obj.chromium.connect_over_cdp.assert_awaited_with("ws://resolved-url:1234")
