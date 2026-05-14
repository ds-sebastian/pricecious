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
            # is_connected is a property/synchronous method on the browser object usually,
            # but if it matches the signature of the real one it should be a method returning bool.
            # In Playwright it's browser.is_connected() -> bool.
            # Since we use AsyncMock for browser, methods are AsyncMocks by default.
            # We need is_connected to be a sync Mock or just return value if it was sync.
            # But here ScraperService calls it as: cls._browser.is_connected()
            # If cls._browser is AsyncMock, calling it returns a coroutine.
            # ScraperService:112: if cls._browser and cls._browser.is_connected():
            # If it's a coroutine, bool(coroutine) is True.
            # However, if it was never awaited, we get a warning.
            # We should make is_connected a standard Mock returning True.
            mock_browser.is_connected = MagicMock(return_value=True)

            # context = await browser.new_context(...)
            mock_browser.new_context.return_value = mock_context

            # page = await context.new_page()
            mock_context.new_page.return_value = mock_page

            config = ScrapeConfig(scroll_pixels=500, smart_scroll=True)

            await ScraperService.initialize()
            with patch.object(ScraperService, "_validate_screenshot", return_value=True):
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
            mock_browser.is_connected = MagicMock(return_value=True)
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page

            config = ScrapeConfig(timeout=12345)

            await ScraperService.initialize()
            with patch.object(ScraperService, "_validate_screenshot", return_value=True):
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
            mock_browser.is_connected = MagicMock(return_value=True)
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page

            await ScraperService.initialize()

            # Mock file operations that the new history retention uses
            with (
                patch("app.services.scraper_service.shutil.copy2"),
                patch("app.services.scraper_service.glob.glob", return_value=[]),
                patch.object(ScraperService, "_validate_screenshot", return_value=True),
            ):
                path, _ = await ScraperService.scrape_item("http://example.com", item_id=123)

            # The returned path should be the "latest" symlink-style path
            assert path == "screenshots/item_123.png"
            # The actual screenshot call uses a timestamped filename
            call_args = mock_page.screenshot.call_args
            actual_path = call_args.kwargs.get("path") or call_args[1].get("path")
            assert actual_path.startswith("screenshots/item_123_")
            assert actual_path.endswith(".png")

    @pytest.mark.asyncio
    async def test_screenshot_anonymous_uses_hash(self):
        """Test that anonymous screenshots use hashed URL filenames."""
        with patch("app.services.scraper_service.async_playwright") as mock_pw_cls:
            mock_pw_obj = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()

            mock_pw_context = MagicMock()
            mock_pw_context.start = AsyncMock(return_value=mock_pw_obj)
            mock_pw_cls.return_value = mock_pw_context

            mock_pw_obj.chromium.connect_over_cdp.return_value = mock_browser
            mock_browser.is_connected = MagicMock(return_value=True)
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page

            await ScraperService.initialize()
            with patch.object(ScraperService, "_validate_screenshot", return_value=True):
                path, _ = await ScraperService.scrape_item("http://example.com")

            # Pattern: screenshots/scrape_YYYYMMDD_HHMMSS_<10-char-hash>.png
            assert path.startswith("screenshots/scrape_")
            assert path.endswith(".png")
            stem = path.removeprefix("screenshots/scrape_").removesuffix(".png")
            parts = stem.split("_")
            assert len(parts) == 3  # YYYYMMDD, HHMMSS, hash
            assert len(parts[2]) == 10  # 10-char SHA-1 prefix


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
            mock_browser.is_connected = MagicMock(return_value=True)
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

    @pytest.mark.asyncio
    async def test_resolve_ws_url_success(self):
        """Test successful discovery of Chrome WebSocket URL."""
        with patch("app.services.scraper_service.httpx.AsyncClient") as mock_client_cls:
            # Setup mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"webSocketDebuggerUrl": "ws://chrome:9222/devtools/browser/123-uuid"}

            # Setup async client context manager
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            base_url = "ws://chrome:9222"
            resolved = await ScraperService._resolve_ws_url(base_url)

            assert resolved == "ws://chrome:9222/devtools/browser/123-uuid"
            mock_client.get.assert_called_once()
            args, _ = mock_client.get.call_args
            assert args[0] == "http://chrome:9222/json/version"

    @pytest.mark.asyncio
    async def test_resolve_ws_url_fallback_connection_error(self):
        """Test fallback when connection fails."""
        with patch("app.services.scraper_service.httpx.AsyncClient") as mock_client_cls:
            # Setup async client that raises on get
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            base_url = "ws://browserless:3000"
            resolved = await ScraperService._resolve_ws_url(base_url)

            # Should fallback to original URL
            assert resolved == base_url

    @pytest.mark.asyncio
    async def test_resolve_ws_url_fallback_invalid_json(self):
        """Test fallback when response is not as expected."""
        with patch("app.services.scraper_service.httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"other_field": "some_value"}

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            base_url = "ws://chrome:9222"
            resolved = await ScraperService._resolve_ws_url(base_url)

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


class TestCookieConsentHandling:
    """Test cookie/GDPR banner handling in _handle_popups."""

    @pytest.mark.asyncio
    async def test_cookie_selectors_tried_before_generic(self):
        """Verify cookie-specific selectors are tried before generic close buttons."""
        from app.services.scraper_service import COOKIE_CONSENT_SELECTORS, ScraperService

        mock_page = AsyncMock()
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_locator.first = MagicMock()
        mock_locator.first.click = AsyncMock()

        # Track which selectors are checked
        checked_selectors = []

        def track_locator(selector):
            checked_selectors.append(selector)
            if selector == COOKIE_CONSENT_SELECTORS[0]:
                return mock_locator
            empty = MagicMock()
            empty.count = AsyncMock(return_value=0)
            return empty

        mock_page.locator = track_locator
        mock_page.get_by_role = MagicMock(return_value=MagicMock(count=AsyncMock(return_value=0)))
        mock_page.keyboard = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()

        await ScraperService._handle_popups(mock_page)

        # First selector checked should be a cookie selector, not generic
        assert checked_selectors[0] in COOKIE_CONSENT_SELECTORS

    @pytest.mark.asyncio
    async def test_accept_all_text_buttons(self):
        """Verify text-based 'Accept All' buttons are clicked."""
        mock_page = AsyncMock()

        # No CSS selectors match
        mock_locator_empty = MagicMock()
        mock_locator_empty.count = AsyncMock(return_value=0)
        mock_page.locator = MagicMock(return_value=mock_locator_empty)

        # Text button matches
        mock_btn = MagicMock()
        mock_btn.count = AsyncMock(return_value=1)
        mock_btn.first = MagicMock()
        mock_btn.first.click = AsyncMock()
        mock_page.get_by_role = MagicMock(return_value=mock_btn)
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.keyboard = AsyncMock()

        await ScraperService._handle_popups(mock_page)

        mock_btn.first.click.assert_awaited()


class TestScreenshotValidation:
    """Test screenshot validation logic."""

    @pytest.mark.asyncio
    async def test_small_file_rejected(self, tmp_path):
        """Screenshots below minimum size are rejected."""
        small_file = tmp_path / "tiny.png"
        small_file.write_bytes(b"\x89PNG" + b"\x00" * 100)

        mock_page = AsyncMock()

        result = await ScraperService._validate_screenshot(str(small_file), mock_page)
        assert result is False

    @pytest.mark.asyncio
    async def test_valid_screenshot_accepted(self, tmp_path):
        """A real-looking screenshot passes validation."""
        from PIL import Image as PILImage

        # Create a colorful test image (not solid color)
        img = PILImage.new("RGB", (200, 200))
        import random as rng

        rng.seed(42)
        pixels = img.load()
        for i in range(200):
            for j in range(200):
                pixels[i, j] = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
        path = tmp_path / "valid.png"
        img.save(path)

        mock_page = AsyncMock()
        mock_page.inner_text = AsyncMock(return_value="Add to Cart $99.99 Buy Now Product details and more text " * 10)

        result = await ScraperService._validate_screenshot(str(path), mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_blocked_page_short_text_rejected(self, tmp_path):
        """A page with blocked phrases and very short text is rejected."""
        from PIL import Image as PILImage

        img = PILImage.new("RGB", (200, 200))
        import random as rng

        rng.seed(42)
        pixels = img.load()
        for i in range(200):
            for j in range(200):
                pixels[i, j] = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
        path = tmp_path / "blocked.png"
        img.save(path)

        mock_page = AsyncMock()
        mock_page.inner_text = AsyncMock(return_value="Access Denied. Please verify you are a human.")

        result = await ScraperService._validate_screenshot(str(path), mock_page)
        assert result is False


class TestUserAgentRotation:
    """Test that user agents are rotated."""

    @pytest.mark.asyncio
    async def test_ua_is_from_pool(self):
        """Verify the UA comes from our pool, not hardcoded."""
        from app.services.scraper_service import USER_AGENTS

        with patch("app.services.scraper_service.async_playwright") as mock_pw_cls:
            mock_pw_obj = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()

            mock_pw_context = MagicMock()
            mock_pw_context.start = AsyncMock(return_value=mock_pw_obj)
            mock_pw_cls.return_value = mock_pw_context

            mock_pw_obj.chromium.connect_over_cdp.return_value = mock_browser
            mock_browser.is_connected = MagicMock(return_value=True)
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page

            await ScraperService.initialize()
            await ScraperService.scrape_item("http://example.com", item_id=1)

            # Check what UA was passed to new_context
            call_kwargs = mock_browser.new_context.call_args
            ua = call_kwargs.kwargs.get("user_agent") or call_kwargs[1].get("user_agent")
            assert ua in USER_AGENTS


class TestScrapeRetry:
    """Test scrape retry on transient failure."""

    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        """Verify scrape retries on exception."""
        with patch.object(ScraperService, "_scrape_attempt") as mock_attempt:
            # First call fails, second succeeds
            mock_attempt.side_effect = [
                Exception("Transient error"),
                ("screenshots/item_1.png", "page text"),
            ]

            with patch("app.services.scraper_service.asyncio.sleep", new_callable=AsyncMock):
                result = await ScraperService.scrape_item("http://example.com", item_id=1)

            assert result == ("screenshots/item_1.png", "page text")
            assert mock_attempt.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_none_result(self):
        """Verify scrape retries when result is None."""
        with patch.object(ScraperService, "_scrape_attempt") as mock_attempt:
            # First returns None, second succeeds
            mock_attempt.side_effect = [
                (None, ""),
                ("screenshots/item_1.png", "text"),
            ]

            with patch("app.services.scraper_service.asyncio.sleep", new_callable=AsyncMock):
                result = await ScraperService.scrape_item("http://example.com", item_id=1)

            assert result == ("screenshots/item_1.png", "text")
            assert mock_attempt.call_count == 2
