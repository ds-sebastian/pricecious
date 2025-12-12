import asyncio
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from urllib.parse import urlparse

import requests
from playwright.async_api import Browser, Page, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)
BROWSERLESS_URL = os.getenv("BROWSERLESS_URL", "ws://browserless:3000")


@dataclass
class ScrapeConfig:
    smart_scroll: bool = False
    scroll_pixels: int = 350
    text_length: int = 0
    timeout: int = 90000


class ScraperService:
    _playwright = None
    _browser: Browser | None = None
    _lock = asyncio.Lock()  # Keep lock to prevent race conditions during init

    @classmethod
    async def initialize(cls):
        """Initialize the shared browser instance."""
        async with cls._lock:
            if not cls._browser:
                logger.info("Initializing ScraperService shared browser...")
                cls._playwright = await async_playwright().start()

                # Resolve the correct WebSocket URL (handles generic Chrome vs Browserless)
                ws_url = cls._resolve_ws_url(BROWSERLESS_URL)
                logger.info(f"Connecting to Chrome at: {ws_url}")

                try:
                    cls._browser = await cls._playwright.chromium.connect_over_cdp(ws_url)
                except Exception as e:
                    if "500 Internal Server Error" in str(e):
                        logger.critical(
                            "Failed to connect to Browserless (500 Error). "
                            "This usually indicates invalid 'launch' arguments. "
                            "Check if 'headless: \"new\"' is supported or try removing 'launch' args."
                        )
                    raise

    @staticmethod
    def _resolve_ws_url(base_url: str) -> str:
        """
        Attempt to resolve the full WebSocket URL from a Chrome instance.

        Generic headless Chrome requires connecting to a specific WebSocket ID
        (e.g., ws://host:port/devtools/browser/<uuid>), which can be discovered
        via http://host:port/json/version.

        Browserless and some other providers accept connection directly at the base URL.
        If the URL already points to a specific endpoint (e.g. /chromium), skip discovery.
        """
        try:
            parsed = urlparse(base_url)

            # If path indicates a specific endpoint (Browserless, or specific session), use it directly.
            # Browserless v2 uses /chromium or /chrome.
            if parsed.path in ["/chromium", "/chrome", "/webdriver"] or parsed.path.startswith("/devtools/browser/"):
                logger.debug(f"Targeting specific endpoint {parsed.path}, skipping discovery.")
                return base_url

            # Construct HTTP URL for the version endpoint
            # Assume http unless scheme is clearly wss -> https (which implies secure)
            scheme = "https" if parsed.scheme == "wss" else "http"
            # Use the netloc (host:port) from the WS URL
            version_url = f"{scheme}://{parsed.netloc}/json/version"

            logger.debug(f"Attempting to discover Chrome WebSocket URL from: {version_url}")
            resp = requests.get(version_url, timeout=2.0)

            if resp.status_code == HTTPStatus.OK:
                data = resp.json()
                if "webSocketDebuggerUrl" in data:
                    resolved = data["webSocketDebuggerUrl"]
                    logger.info("Discovered dynamic Chrome WebSocket URL")
                    return resolved
        except Exception as e:
            # If discovery fails (timeout, connection refused, not a JSON response),
            # it might be Browserless or just not ready. Fallback to original.
            logger.debug(f"Chrome URL discovery failed ({e}), falling back to direct connection.")

        return base_url

    @classmethod
    async def shutdown(cls):
        """Shutdown the shared browser instance."""
        async with cls._lock:
            if cls._browser:
                await cls._browser.close()
                cls._browser = None
            if cls._playwright:
                await cls._playwright.stop()
                cls._playwright = None
            logger.info("ScraperService shutdown complete.")

    @classmethod
    async def _ensure_connection(cls) -> bool:
        """Check connection and reconnect if necessary."""
        if cls._browser and cls._browser.is_connected():
            return True
        logger.warning("Browser disconnected, reconnecting...")
        await cls.shutdown()
        try:
            await cls.initialize()
            return True
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            return False

    @staticmethod
    async def scrape_item(
        url: str,
        selector: str | None = None,
        item_id: int | None = None,
        config: ScrapeConfig | None = None,
    ) -> tuple[str | None, str]:
        """Scrape URL using shared browser."""
        config = config or ScrapeConfig()

        if not await ScraperService._ensure_connection():
            return None, ""

        try:
            # Use a fresh context for each scrape to ensure isolation
            async with ScraperService._scoped_context() as page:
                if not await ScraperService._navigate(page, url, config.timeout):
                    return None, ""

                await ScraperService._handle_popups(page)

                if selector:
                    await ScraperService._wait_for_selector(page, selector)
                else:
                    await ScraperService._auto_detect_price(page)

                if config.smart_scroll:
                    await page.evaluate(f"window.scrollBy(0, {config.scroll_pixels})")
                    await page.wait_for_timeout(1000)

                text = await ScraperService._extract_text(page, config.text_length)
                screenshot = await ScraperService._take_screenshot(page, url, item_id)

                return screenshot, text

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None, ""

    @staticmethod
    @asynccontextmanager
    async def _scoped_context():
        """Provide a scoped page instance with proper cleanup."""
        context = await ScraperService._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        await context.route("**/*", lambda route: route.continue_())
        page = await context.new_page()
        try:
            yield page
        finally:
            await context.close()

    @staticmethod
    async def _navigate(page: Page, url: str, timeout: int) -> bool:
        logger.info(f"Navigating to {url}")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except PlaywrightTimeoutError:
                pass  # Non-critical

            await page.wait_for_timeout(2000)
            return True
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"Navigation issue: {error_msg}")
            if "Target page, context or browser has been closed" in error_msg:
                # Critical error, force a reset for next time
                logger.error("Browser usage error detected, forcing shutdown to reset state.")
                await ScraperService.shutdown()
            return False

    @staticmethod
    async def _handle_popups(page: Page):
        """Attempt to close common popups."""
        common_selectors = [
            "button[aria-label='Close']",
            ".close-button",
            ".modal-close",
            "div[role='dialog'] button",
            "svg[data-name='Close']",
        ]
        # Quick race to close popups if they exist
        for selector in common_selectors:
            try:
                if await page.locator(selector).count() > 0:
                    await page.locator(selector).first.click(timeout=1000)
            except Exception:
                pass

        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass

    @staticmethod
    async def _wait_for_selector(page: Page, selector: str):
        try:
            await page.wait_for_selector(selector, timeout=5000)
            await page.locator(selector).first.scroll_into_view_if_needed()
        except Exception:
            logger.warning(f"Selector {selector} not found")

    @staticmethod
    async def _auto_detect_price(page: Page):
        try:
            # Simple heuristic: look for currency symbol
            locator = page.locator("text=/$[0-9,]+(\\.[0-9]{2})?/")
            if await locator.count() > 0:
                await locator.first.scroll_into_view_if_needed()
        except Exception:
            pass

    @staticmethod
    async def _extract_text(page: Page, limit: int) -> str:
        if limit <= 0:
            return ""
        try:
            text = await page.inner_text("body")
            return text[:limit]
        except Exception:
            return ""

    @staticmethod
    async def _take_screenshot(page: Page, url: str, item_id: int | None) -> str:
        path = "screenshots"
        os.makedirs(path, exist_ok=True)
        filename = f"{path}/item_{item_id}.png" if item_id else f"{path}/scrape_{datetime.now().timestamp()}.png"
        await page.screenshot(path=filename)
        return filename
