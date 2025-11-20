"""
Unit tests for scraper module.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.scraper import scrape_item


class TestScraperInputValidation:
    """Test input validation in scraper."""

    @pytest.mark.asyncio
    async def test_invalid_scroll_pixels(self, caplog):
        """Test that invalid scroll_pixels is corrected."""
        with patch("app.scraper.async_playwright") as mock_playwright:
            # Mock the playwright context
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock()
            mock_page.screenshot = AsyncMock()
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_browser.close = AsyncMock()

            mock_pw = AsyncMock()
            mock_pw.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)
            mock_playwright.return_value.__aenter__.return_value = mock_pw

            # Test with negative scroll_pixels
            await scrape_item("https://example.com", scroll_pixels=-100)

            # Check that warning was logged
            assert "Invalid scroll_pixels value" in caplog.text

    @pytest.mark.asyncio
    async def test_invalid_timeout(self, caplog):
        """Test that invalid timeout is corrected."""
        with patch("app.scraper.async_playwright") as mock_playwright:
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock()
            mock_page.screenshot = AsyncMock()
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_browser.close = AsyncMock()

            mock_pw = AsyncMock()
            mock_pw.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)
            mock_playwright.return_value.__aenter__.return_value = mock_pw

            # Test with zero timeout
            await scrape_item("https://example.com", timeout=0)

            # Check that warning was logged
            assert "Invalid timeout value" in caplog.text


class TestScraperScreenshot:
    """Test screenshot functionality."""

    @pytest.mark.asyncio
    async def test_screenshot_path_generation(self):
        """Test that screenshot paths are generated correctly."""
        with patch("app.scraper.async_playwright") as mock_playwright:
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock()
            mock_page.screenshot = AsyncMock()
            mock_page.inner_text = AsyncMock(return_value="test text")
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_browser.close = AsyncMock()

            mock_pw = AsyncMock()
            mock_pw.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)
            mock_playwright.return_value.__aenter__.return_value = mock_pw

            # Test with item_id
            path, text = await scrape_item("https://example.com", item_id=123)

            assert path == "screenshots/item_123.png"
            mock_page.screenshot.assert_called_once_with(path="screenshots/item_123.png", full_page=False)


class TestScraperErrorHandling:
    """Test error handling in scraper."""

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        """Test handling of connection failures."""
        with patch("app.scraper.async_playwright") as mock_playwright:
            mock_pw = AsyncMock()
            mock_pw.chromium.connect_over_cdp = AsyncMock(side_effect=Exception("Connection failed"))
            mock_playwright.return_value.__aenter__.return_value = mock_pw

            # Should return None on error
            result, text = await scrape_item("https://example.com")

            assert result is None
            assert text == ""

    @pytest.mark.asyncio
    async def test_page_load_timeout(self):
        """Test handling of page load timeout."""
        with patch("app.scraper.async_playwright") as mock_playwright:
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock(side_effect=Exception("Timeout"))
            mock_page.screenshot = AsyncMock()  # Should still try to screenshot
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_browser.close = AsyncMock()

            mock_pw = AsyncMock()
            mock_pw.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)
            mock_playwright.return_value.__aenter__.return_value = mock_pw

            # Should continue and try to screenshot
            result, text = await scrape_item("https://example.com", item_id=1)

            # Even with timeout, should attempt screenshot
            mock_page.screenshot.assert_called_once()
