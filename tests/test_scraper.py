"""
Unit tests for scraper module.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.scraper_service import ScraperService


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
        from app.services.scraper_service import ScrapeConfig

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
            mock_page.locator = AsyncMock(return_value=mock_locator)

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
            config = ScrapeConfig(scroll_pixels=-100)
            await ScraperService.scrape_item("https://example.com", config=config)

            # Check that warning was logged
            assert "Invalid scroll_pixels value" in caplog.text

    @pytest.mark.asyncio
    async def test_invalid_timeout(self, caplog):
        """Test that invalid timeout is corrected."""
        from app.services.scraper_service import ScrapeConfig

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
            await ScraperService.scrape_item("https://example.com", config=config)

            # Check that warning was logged
            assert "Invalid timeout value" in caplog.text


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
            mock_page.locator = AsyncMock(return_value=mock_locator)

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
            mock_page.locator = AsyncMock(return_value=mock_locator)

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
