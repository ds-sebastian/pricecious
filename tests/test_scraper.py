"""
Unit tests for scraper module.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.scraper_service import ScrapeConfig, ScraperService


@pytest.fixture(autouse=True)
async def reset_scraper_service():
    """Reset ScraperService state before and after each test."""
    # Reset state
    ScraperService._browser = None
    ScraperService._playwright = None
    # We don't reset the lock as it's a new object per process usually, but for tests it's fine.
    # Actually, we should probably ensure it's clean.

    yield

    # Cleanup after test
    if ScraperService._browser:
        await ScraperService._browser.close()
    if ScraperService._playwright:
        await ScraperService._playwright.stop()

    ScraperService._browser = None
    ScraperService._playwright = None


class TestScraperInputValidation:
    """Test input validation in scraper."""

    @pytest.mark.asyncio
    async def test_invalid_scroll_pixels(self, caplog):
        """Test that invalid scroll_pixels is corrected."""

        with patch("app.services.scraper_service.async_playwright") as mock_playwright:
            # Mock the playwright start return value
            mock_pw = AsyncMock()
            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw)

            # Mock browser and context
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock()
            mock_page.screenshot = AsyncMock()
            mock_page.inner_text = AsyncMock(return_value="")

            # Mock locator properly
            mock_locator = AsyncMock()
            mock_locator.count = AsyncMock(return_value=0)
            mock_locator.first = AsyncMock()
            mock_locator.first.click = AsyncMock()
            mock_locator.first.scroll_into_view_if_needed = AsyncMock()
            mock_page.locator = MagicMock(return_value=mock_locator)

            # Mock keyboard
            mock_keyboard = AsyncMock()
            mock_keyboard.press = AsyncMock()
            mock_page.keyboard = mock_keyboard

            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_browser.close = AsyncMock()

            # Connect over CDP returns the browser
            mock_pw.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)

            # Test with negative scroll_pixels
            config = ScrapeConfig(scroll_pixels=-100, smart_scroll=True)

            # We need to mock _smart_scroll to verify it's called with corrected value
            with patch(
                "app.services.scraper_service.ScraperService._smart_scroll", new_callable=AsyncMock
            ) as mock_scroll:
                await ScraperService.scrape_item("https://example.com", config=config)

                # Verify it was called with default 350
                mock_scroll.assert_called_once()
                args, _ = mock_scroll.call_args
                assert args[1] == 350

    @pytest.mark.asyncio
    async def test_invalid_timeout(self, caplog):
        """Test that invalid timeout is corrected."""

        with patch("app.services.scraper_service.async_playwright") as mock_playwright:
            mock_pw = AsyncMock()
            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw)

            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock()
            mock_page.screenshot = AsyncMock()
            mock_page.inner_text = AsyncMock(return_value="")

            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_browser.close = AsyncMock()

            mock_pw.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)

            # Test with zero timeout
            config = ScrapeConfig(timeout=0)

            # Mock _navigate_and_wait to verify timeout
            with patch(
                "app.services.scraper_service.ScraperService._navigate_and_wait", new_callable=AsyncMock
            ) as mock_nav:
                await ScraperService.scrape_item("https://example.com", config=config)

                # Verify it was called with default 90000 (default when <= 0)
                mock_nav.assert_called_once()
                args, _ = mock_nav.call_args
                assert args[2] == 90000


class TestScraperScreenshot:
    """Test screenshot functionality."""

    @pytest.mark.asyncio
    async def test_screenshot_path_generation(self):
        """Test that screenshot paths are generated correctly."""
        with patch("app.services.scraper_service.async_playwright") as mock_playwright:
            mock_pw = AsyncMock()
            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw)

            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock()
            mock_page.screenshot = AsyncMock()
            mock_page.inner_text = AsyncMock(return_value="test text")

            # Mock locator
            mock_locator = AsyncMock()
            mock_locator.count = AsyncMock(return_value=0)
            mock_locator.first = AsyncMock()
            mock_locator.first.click = AsyncMock()
            mock_locator.first.scroll_into_view_if_needed = AsyncMock()
            mock_page.locator = MagicMock(return_value=mock_locator)

            # Mock keyboard
            mock_keyboard = AsyncMock()
            mock_keyboard.press = AsyncMock()
            mock_page.keyboard = mock_keyboard

            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_browser.close = AsyncMock()

            mock_pw.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)

            # Test with item_id
            path, _ = await ScraperService.scrape_item("https://example.com", item_id=123)

            assert path == "screenshots/item_123.png"
            mock_page.screenshot.assert_called_once_with(path="screenshots/item_123.png", full_page=False)


class TestScraperErrorHandling:
    """Test error handling in scraper."""

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        """Test handling of connection failures."""
        with patch("app.services.scraper_service.async_playwright") as mock_playwright:
            # Mock start to return a mock that fails on connect
            mock_pw = AsyncMock()
            mock_pw.chromium.connect_over_cdp = AsyncMock(side_effect=Exception("Connection failed"))
            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw)

            # Should return None on error
            result, text = await ScraperService.scrape_item("https://example.com")

            assert result is None
            assert text == ""

    @pytest.mark.asyncio
    async def test_page_load_timeout(self):
        """Test handling of page load timeout."""
        with patch("app.services.scraper_service.async_playwright") as mock_playwright:
            mock_pw = AsyncMock()
            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw)

            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock(side_effect=Exception("Timeout"))
            mock_page.screenshot = AsyncMock()  # Should still try to screenshot
            mock_page.inner_text = AsyncMock(return_value="")

            # Mock locator
            mock_locator = AsyncMock()
            mock_locator.count = AsyncMock(return_value=0)
            mock_page.locator = MagicMock(return_value=mock_locator)

            # Mock keyboard
            mock_keyboard = AsyncMock()
            mock_keyboard.press = AsyncMock()
            mock_page.keyboard = mock_keyboard

            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_browser.close = AsyncMock()

            mock_pw.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)

            # Should continue and try to screenshot
            await ScraperService.scrape_item("https://example.com", item_id=1)

            # Even with timeout, should attempt screenshot
            mock_page.screenshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconnection_deadlock(self):
        """Test that reconnection doesn't deadlock."""
        with patch("app.services.scraper_service.async_playwright") as mock_playwright:
            mock_pw = AsyncMock()
            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw)

            mock_browser = AsyncMock()

            # First context creation fails (simulating connection loss)
            mock_browser.new_context = AsyncMock(side_effect=Exception("Connection lost"))
            mock_browser.close = AsyncMock()

            # Initialize first
            # We need to mock connect_over_cdp to return our mock browser
            # First call returns "broken" browser, second call returns "working" browser
            working_browser = AsyncMock()
            working_context = AsyncMock()
            working_browser.new_context = AsyncMock(return_value=working_context)
            working_context.close = AsyncMock()

            mock_pw.chromium.connect_over_cdp = AsyncMock(side_effect=[mock_browser, working_browser])

            await ScraperService.initialize()

            # This should trigger reconnection logic
            # If deadlock exists, this will hang (timeout in test)
            try:
                result = await ScraperService._ensure_browser_connected()
                assert result is True

            except TimeoutError:
                pytest.fail("Deadlock detected during reconnection")
