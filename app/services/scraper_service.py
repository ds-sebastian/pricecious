import asyncio
import logging
import os
from dataclasses import dataclass

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

BROWSERLESS_URL = os.getenv("BROWSERLESS_URL", "ws://browserless:3000")


@dataclass
class ScrapeConfig:
    """Configuration for scraping parameters."""

    smart_scroll: bool = False
    scroll_pixels: int = 350
    text_length: int = 0
    timeout: int = 90000


class ScraperService:
    _playwright = None
    _browser: Browser | None = None
    _lock = asyncio.Lock()

    @classmethod
    async def initialize(cls):
        """Initialize the shared browser instance."""
        async with cls._lock:
            if cls._browser is None:
                logger.info("Initializing ScraperService shared browser...")
                cls._playwright = await async_playwright().start()
                cls._browser = await cls._connect_browser(cls._playwright)
                logger.info("ScraperService initialized.")

    @classmethod
    async def shutdown(cls):
        """Shutdown the shared browser instance."""
        async with cls._lock:
            if cls._browser:
                logger.info("Shutting down ScraperService shared browser...")
                await cls._browser.close()
                cls._browser = None
            if cls._playwright:
                await cls._playwright.stop()
                cls._playwright = None
            logger.info("ScraperService shutdown complete.")

    @staticmethod
    async def scrape_item(
        url: str,
        selector: str | None = None,
        item_id: int | None = None,
        config: ScrapeConfig | None = None,
    ) -> tuple[str | None, str]:
        """
        Scrapes the given URL using Browserless and Playwright.
        Returns a tuple: (screenshot_path, page_text)
        """
        if config is None:
            config = ScrapeConfig()

        # Input validation
        scroll_pixels = config.scroll_pixels
        timeout = config.timeout

        if scroll_pixels <= 0:
            logger.warning(f"Invalid scroll_pixels value: {scroll_pixels}, using default 350")
            scroll_pixels = 350

        if timeout <= 0:
            logger.warning(f"Invalid timeout value: {timeout}, using default 90000")
            timeout = 90000

        # Ensure minimums even if positive (optional, but good practice)
        scroll_pixels = max(350, scroll_pixels)
        timeout = max(30000, timeout)

        # Ensure browser is initialized
        if ScraperService._browser is None:
            logger.warning("ScraperService not initialized, attempting lazy initialization...")
            try:
                await ScraperService.initialize()
            except Exception as e:
                logger.error(f"Lazy initialization failed: {e}")
                return None, ""

        if ScraperService._browser is None:
            logger.error("Failed to initialize browser for scraping.")
            return None, ""

        try:
            context = await ScraperService._create_context(ScraperService._browser)
            page = await context.new_page()

            try:
                await ScraperService._navigate_and_wait(page, url, timeout)
                await ScraperService._handle_popups(page)

                if selector:
                    await ScraperService._wait_for_selector(page, selector)
                else:
                    await ScraperService._auto_detect_price(page)

                if config.smart_scroll:
                    await ScraperService._smart_scroll(page, scroll_pixels)

                page_text = await ScraperService._extract_text(page, config.text_length)
                screenshot_path = await ScraperService._take_screenshot(page, url, item_id)

                return screenshot_path, page_text

            finally:
                await context.close()

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None, ""

    @staticmethod
    async def _connect_browser(p) -> Browser:
        logger.info(f"Connecting to Browserless at {BROWSERLESS_URL}")
        return await p.chromium.connect_over_cdp(BROWSERLESS_URL)

    @staticmethod
    async def _create_context(browser: Browser) -> BrowserContext:
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        # Stealth mode / Ad blocking attempts
        await context.route("**/*", lambda route: route.continue_())
        return context

    @staticmethod
    async def _navigate_and_wait(page: Page, url: str, timeout: int):
        logger.info(f"Navigating to {url} (Timeout: {timeout}ms)")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            logger.info(f"Page loaded (domcontentloaded): {url}")

            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
                logger.info("Network idle reached")
            except PlaywrightTimeoutError:
                logger.info("Network idle timed out (non-critical), proceeding...")

        except Exception as e:
            logger.warning(f"Navigation warning for {url}: {e}")
            # Continue even if navigation isn't perfect, as we might still get content

        # Wait a bit for dynamic content
        await page.wait_for_timeout(2000)

    @staticmethod
    async def _handle_popups(page: Page):
        logger.info("Attempting to close popups...")
        popup_selectors = [
            "button[aria-label='Close']",
            "button[aria-label='close']",
            ".close-button",
            ".modal-close",
            "svg[data-name='Close']",
            "[class*='popup'] button",
            "[class*='modal'] button",
            "button:has-text('No, thanks')",
            "button:has-text('No thanks')",
            "a:has-text('No, thanks')",
            "div[role='dialog'] button[aria-label='Close']",
        ]

        for popup_selector in popup_selectors:
            try:
                if await page.locator(popup_selector).count() > 0:
                    logger.info(f"Found popup close button: {popup_selector}")
                    await page.locator(popup_selector).first.click(timeout=2000)
                    await page.wait_for_timeout(1000)
            except Exception:
                # Ignore errors when trying to close popups
                pass

        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass

    @staticmethod
    async def _wait_for_selector(page: Page, selector: str):
        try:
            logger.info(f"Waiting for selector: {selector}")
            await page.wait_for_selector(selector, timeout=5000)
            element = page.locator(selector).first
            await element.scroll_into_view_if_needed()
            logger.info(f"Scrolled to selector: {selector}")
        except Exception as e:
            logger.warning(f"Selector {selector} not found or timed out: {e}")

    @staticmethod
    async def _auto_detect_price(page: Page):
        logger.info("No selector provided. Attempting to find price element...")
        try:
            price_locator = page.locator("text=/$[0-9,]+(\\.[0-9]{2})?/")
            if await price_locator.count() > 0:
                await price_locator.first.scroll_into_view_if_needed()
                logger.info("Scrolled to potential price element")
        except Exception as e:
            logger.warning(f"Auto-price detection failed: {e}")

    @staticmethod
    async def _smart_scroll(page: Page, scroll_pixels: int):
        logger.info(f"Performing smart scroll ({scroll_pixels}px)...")
        try:
            await page.evaluate(f"window.scrollBy(0, {scroll_pixels})")
            await page.wait_for_timeout(1000)
        except Exception as e:
            logger.warning(f"Smart scroll failed: {e}")

    @staticmethod
    async def _extract_text(page: Page, text_length: int) -> str:
        if text_length <= 0:
            return ""

        try:
            logger.info(f"Extracting text (limit: {text_length} chars)...")
            raw_text = await page.inner_text("body")
            page_text = raw_text[:text_length]
            logger.info(f"Extracted {len(page_text)} characters")
            return page_text
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return ""

    @staticmethod
    async def _take_screenshot(page: Page, url: str, item_id: int | None) -> str:
        screenshot_dir = "screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)

        if item_id:
            filename = f"{screenshot_dir}/item_{item_id}.png"
        else:
            url_part = url.split("//")[-1].replace("/", "_")
            timestamp = asyncio.get_event_loop().time()
            filename = f"{screenshot_dir}/{url_part}_{timestamp}.png"

        await page.screenshot(path=filename, full_page=False)
        logger.info(f"Screenshot saved to {filename}")
        return filename
