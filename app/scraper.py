import asyncio
import logging
import os

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

BROWSERLESS_URL = os.getenv("BROWSERLESS_URL", "ws://browserless:3000")

logger = logging.getLogger(__name__)


async def scrape_item(  # noqa: PLR0913, PLR0912, PLR0915
    url: str,
    selector: str | None = None,
    item_id: int | None = None,
    smart_scroll: bool = False,
    scroll_pixels: int = 350,
    text_length: int = 0,
    timeout: int = 90000,
) -> tuple[str | None, str]:
    """
    Scrapes the given URL using Browserless and Playwright.
    Returns a tuple: (screenshot_path, page_text)

    Args:
        url: Target URL to scrape
        selector: Optional CSS selector to focus on
        item_id: Optional item ID for screenshot naming
        smart_scroll: Enable scrolling to load lazy content
        scroll_pixels: Number of pixels to scroll (must be positive)
        text_length: Number of characters to extract (0 = disabled)
        timeout: Page load timeout in milliseconds
    """
    # Input validation
    if scroll_pixels <= 0:
        logger.warning(f"Invalid scroll_pixels value: {scroll_pixels}, using default 350")
        scroll_pixels = 350

    if timeout <= 0:
        logger.warning(f"Invalid timeout value: {timeout}, using default 90000")
        timeout = 90000
    async with async_playwright() as p:
        browser = None
        try:
            logger.info(f"Connecting to Browserless at {BROWSERLESS_URL}")
            browser = await p.chromium.connect_over_cdp(BROWSERLESS_URL)
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

            page = await context.new_page()

            logger.info(f"Navigating to {url} (Timeout: {timeout}ms)")
            try:
                # First wait for domcontentloaded - this is the minimum we need
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                logger.info(f"Page loaded (domcontentloaded): {url}")

                # Then try to wait for networkidle, but don't fail if it times out
                # This helps with heavy pages that never fully settle
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                    logger.info("Network idle reached")
                except PlaywrightTimeoutError:
                    logger.info("Network idle timed out (non-critical), proceeding...")

            except Exception as e:
                logger.error(f"Error navigating to {url}: {e}")
                # Try to take screenshot anyway if page partially loaded
                pass

            # Wait a bit for dynamic content if needed
            await page.wait_for_timeout(2000)

            # Try to close common popups
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
                        # Try to click it. If it fails, catch and continue
                        await page.locator(popup_selector).first.click(timeout=2000)
                        await page.wait_for_timeout(1000)  # Wait for animation
                except Exception as e:
                    logger.debug(f"Could not close popup with selector {popup_selector}: {e}")

            # Also try pressing Escape
            try:
                await page.keyboard.press("Escape")
            except Exception as e:
                logger.debug(f"Could not press Escape key: {e}")

            if selector:
                try:
                    logger.info(f"Waiting for selector: {selector}")
                    await page.wait_for_selector(selector, timeout=5000)
                    # Scroll to element
                    element = page.locator(selector).first
                    await element.scroll_into_view_if_needed()
                    logger.info(f"Scrolled to selector: {selector}")
                except Exception as e:
                    logger.warning(f"Selector {selector} not found or timed out: {e}")
            else:
                # Auto-detect price if no selector
                logger.info("No selector provided. Attempting to find price element...")
                try:
                    # Look for common price patterns
                    price_locator = page.locator("text=/$[0-9,]+(\\.[0-9]{2})?/")
                    if await price_locator.count() > 0:
                        # Pick the first one that looks visible and reasonable size
                        # This is heuristic
                        await price_locator.first.scroll_into_view_if_needed()
                        logger.info("Scrolled to potential price element")
                except Exception as e:
                    logger.warning(f"Auto-price detection failed: {e}")

            # Smart Scroll
            if smart_scroll:
                logger.info(f"Performing smart scroll ({scroll_pixels}px)...")
                try:
                    await page.evaluate(f"window.scrollBy(0, {scroll_pixels})")
                    await page.wait_for_timeout(1000)
                except Exception as e:
                    logger.warning(f"Smart scroll failed: {e}")

            # Text Extraction
            page_text = ""
            if text_length > 0:
                try:
                    logger.info(f"Extracting text (limit: {text_length} chars)...")
                    # Get text from body
                    raw_text = await page.inner_text("body")
                    # Simple truncation
                    page_text = raw_text[:text_length]
                    logger.info(f"Extracted {len(page_text)} characters")
                except Exception as e:
                    logger.error(f"Text extraction failed: {e}")

            # Take screenshot
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

            return filename, page_text

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None, ""

        finally:
            if browser:
                await browser.close()
