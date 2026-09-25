"""Page capture through a shared Browserless/Chrome connection."""

import asyncio
import io
import json
import logging
import os
import random
import re
from contextlib import suppress
from dataclasses import dataclass
from urllib.parse import urlencode, urlparse, urlunparse

import httpx
from PIL import Image, ImageStat
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.urls import UnresolvableHostError, UnsafeURLError, redact, validate_url_async

logger = logging.getLogger(__name__)

BROWSERLESS_URL = os.getenv("BROWSERLESS_URL", "ws://browserless:3000")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]
COOKIE_ACCEPT_SELECTORS = [
    "#onetrust-accept-btn-handler",
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    ".cc-accept",
    "[data-testid*='cookie-accept']",
    "button[id*='cookie' i][class*='accept' i]",
    "button[id*='consent' i]",
    "button[class*='cookie' i][class*='accept' i]",
]
COOKIE_ACCEPT_LABELS = ["Accept All", "Accept Cookies", "I Agree", "Agree", "Allow All"]
POPUP_CLOSE_SELECTORS = [
    "button[aria-label='Close']",
    ".close-button",
    ".modal-close",
    "div[role='dialog'] button",
    "svg[data-name='Close']",
]
PRICE_LOCATOR = "text=/(\\$|€|£)\\s*[0-9,]+\\.?[0-9]{0,2}/i"
BLOCKED_PAGE_PHRASES = [
    "access denied",
    "please verify you are a human",
    "are you a robot",
    "captcha",
    "blocked",
    "unusual traffic",
    "enable javascript",
    "please enable cookies",
]

MIN_SCREENSHOT_BYTES = 5_000
MIN_IMAGE_VARIANCE = 50.0
MIN_CONTENT_WORDS = 100
ATTEMPTS = 2
RETRY_DELAY_SECONDS = 3
DNS_ATTEMPTS = 2
_dns_limit = asyncio.Semaphore(8)


class _Connection:
    playwright: Playwright | None = None
    browser: Browser | None = None
    lock = asyncio.Lock()


_conn = _Connection()


@dataclass
class Capture:
    screenshot: bytes
    text: str
    title: str = ""
    selector_text: str = ""  # text of the item's CSS selector match, when it has one


class ScrapeError(Exception):
    def __init__(self, message: str, capture: Capture | None = None):
        super().__init__(message)
        self.capture = capture  # what the browser saw, when a page loaded but was rejected


def browserless_url(base_url: str) -> str:
    """Append Browserless options from BROWSERLESS_* env vars as query parameters."""
    params: dict[str, str] = {}
    if token := os.getenv("BROWSERLESS_TOKEN"):
        params["token"] = token
    if _env_flag("BROWSERLESS_BLOCK_ADS"):
        params["blockAds"] = "true"

    launch: dict = {}
    if _env_flag("BROWSERLESS_STEALTH"):
        launch["stealth"] = True
    if headless := os.getenv("BROWSERLESS_HEADLESS"):
        launch["headless"] = {"true": True, "false": False}.get(headless.lower(), headless)
    try:
        viewport = {
            dim: int(value)
            for dim in ("width", "height")
            if (value := os.getenv(f"BROWSERLESS_VIEWPORT_{dim.upper()}"))
        }
    except ValueError:
        logger.warning("BROWSERLESS_VIEWPORT_WIDTH/HEIGHT must be integers; ignoring them")
        viewport = {}
    if viewport:
        launch["defaultViewport"] = viewport
    if launch:
        params["launch"] = json.dumps(launch, separators=(",", ":"))

    if not params:
        return base_url
    parsed = urlparse(base_url)
    query = "&".join(filter(None, [parsed.query, urlencode(params)]))
    return urlunparse(parsed._replace(query=query))


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").lower() in {"true", "1", "yes"}


async def _resolve_ws_url(base_url: str) -> str:
    """Plain headless Chrome needs its per-session WebSocket URL from /json/version; Browserless doesn't."""
    parsed = urlparse(base_url)
    if parsed.path in {"/chromium", "/chrome", "/webdriver"} or parsed.path.startswith("/devtools/browser/"):
        return base_url
    scheme = "https" if parsed.scheme == "wss" else "http"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{scheme}://{parsed.netloc}/json/version")
        return response.json()["webSocketDebuggerUrl"]
    except Exception:
        return base_url


def _connection_failure(exc: Exception) -> str:
    """Summarize a connection error without echoing text that may contain the token."""
    message = str(exc).lower()
    for needles, reason in [
        (("500 internal server error",), "server returned HTTP 500 (check BROWSERLESS_* launch options)"),
        (("401", "403", "unauthorized", "authentication"), "authentication was rejected"),
        (("timed out", "timeout"), "connection timed out"),
        (("connection refused", "econnrefused"), "connection was refused"),
        (("name or service not known", "could not resolve", "dns"), "DNS resolution failed"),
    ]:
        if any(needle in message for needle in needles):
            return reason
    return type(exc).__name__


async def start() -> Browser:
    async with _conn.lock:
        if _conn.browser and _conn.browser.is_connected():
            return _conn.browser
        await _close()
        ws_url = await _resolve_ws_url(browserless_url(BROWSERLESS_URL))
        logger.info(f"Connecting to browser at {redact(ws_url)}")
        _conn.playwright = await async_playwright().start()
        try:
            _conn.browser = await _conn.playwright.chromium.connect_over_cdp(ws_url)
        except Exception as exc:
            await _close()
            raise ScrapeError(f"Could not connect to browser at {redact(ws_url)}: {_connection_failure(exc)}") from None
        return _conn.browser


async def stop() -> None:
    async with _conn.lock:
        await _close()


async def _close() -> None:
    if _conn.browser:
        with suppress(Exception):
            await _conn.browser.close()
    if _conn.playwright:
        with suppress(Exception):
            await _conn.playwright.stop()
    _conn.playwright = _conn.browser = None


async def capture(
    url: str, *, selector: str | None = None, scroll_pixels: int = 0, timeout_ms: int = 90_000
) -> Capture:
    """Load a page and return its screenshot and visible text, retrying once on failure."""
    try:
        await validate_url_async(url)
    except UnsafeURLError as exc:
        raise ScrapeError(f"Blocked URL: {exc}") from None

    for attempt in range(1, ATTEMPTS):
        try:
            return await _capture_once(url, selector, scroll_pixels, timeout_ms)
        except ScrapeError as exc:
            logger.info(f"Capture attempt {attempt} failed for {redact(url)}: {exc}; retrying")
            await asyncio.sleep(RETRY_DELAY_SECONDS)
    return await _capture_once(url, selector, scroll_pixels, timeout_ms)


async def _capture_once(url: str, selector: str | None, scroll_pixels: int, timeout_ms: int) -> Capture:
    browser = await start()
    context = None
    try:
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=random.choice(USER_AGENTS),
            service_workers="block",
        )
        await _guard_network(context)
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        await page.set_extra_http_headers({"Referer": "https://www.google.com/"})
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except PlaywrightError as exc:
            raise ScrapeError(f"Page failed to load: {_first_line(exc)}") from None
        with suppress(PlaywrightTimeoutError):
            await page.wait_for_load_state("networkidle", timeout=5000)
        await page.wait_for_timeout(2000)

        await _dismiss_popups(page)
        await _scroll_to_price(page, selector)
        if scroll_pixels:
            await page.evaluate("px => window.scrollBy(0, px)", scroll_pixels)
            await page.wait_for_timeout(1000)

        text = title = selector_text = ""
        with suppress(PlaywrightError):
            text = " ".join((await page.inner_text("body")).split())
            title = await page.title()
        if selector:
            with suppress(PlaywrightError):
                selector_text = " ".join((await page.locator(selector).first.inner_text(timeout=1000)).split())
        screenshot = await page.screenshot()
    except PlaywrightError as exc:  # usually a lost browser connection; start() reconnects next time
        raise ScrapeError(f"Browser error: {_first_line(exc)}") from None
    finally:
        if context:
            with suppress(Exception):
                await context.close()

    capture = Capture(screenshot, text, title, selector_text)
    if problem := await asyncio.to_thread(content_problem, screenshot, text):
        raise ScrapeError(problem, capture)
    return capture


def _first_line(exc: PlaywrightError) -> str:
    return exc.message.splitlines()[0].removeprefix("Page.goto: ")


def product_name(title: str) -> str | None:
    """Guess a product name from a page title such as 'Acme K65 Keyboard | Acme Store'.

    Titles join the product with the store and category using separators; the product is usually the longest part.
    """
    parts = re.split(r"\s+[|\-\u2013\u2014:\u00b7]\s+|:\s+", " ".join(title.split()))  # pipes, dashes, colons, middots
    return max(parts, key=len)[:200] or None


def content_problem(screenshot: bytes, text: str) -> str | None:
    """Detect blank, error, and bot-check pages."""
    if len(screenshot) < MIN_SCREENSHOT_BYTES:
        return "Page looks blank"
    with Image.open(io.BytesIO(screenshot)) as image:
        if ImageStat.Stat(image.convert("L")).var[0] < MIN_IMAGE_VARIANCE:
            return "Page looks blank"
    lowered = text.lower()
    if len(text.split()) < MIN_CONTENT_WORDS:
        for phrase in BLOCKED_PAGE_PHRASES:
            if phrase in lowered:
                return f"Page looks blocked by a bot check ('{phrase}')"
    return None


async def _guard_network(context: BrowserContext) -> None:
    """Abort every request and WebSocket whose destination is not a public address."""
    reported: set[str] = set()

    async def check(url: str) -> bool:
        async with _dns_limit:
            for attempt in range(DNS_ATTEMPTS):
                try:
                    await validate_url_async(url)
                    return True
                except UnresolvableHostError as exc:
                    if attempt + 1 < DNS_ATTEMPTS:
                        await asyncio.sleep(0.1)
                        continue
                    # Often a tracker stopped by a DNS blocklist; the browser couldn't load it either.
                    logger.debug(f"Skipped browser request to {_origin(url)}: {exc}")
                    return False
                except UnsafeURLError as exc:
                    origin = _origin(url)
                    level = logging.DEBUG if origin in reported else logging.WARNING
                    reported.add(origin)
                    logger.log(level, f"Blocked browser request to {origin}: {exc}")
                    return False
        return False

    async def guard_request(route):
        if await check(route.request.url):
            await route.continue_()
        else:
            await route.abort("blockedbyclient")

    async def guard_websocket(ws):
        if await check(ws.url.replace("wss://", "https://", 1).replace("ws://", "http://", 1)):
            ws.connect_to_server()
        else:
            await ws.close(code=1008, reason="Unsafe destination")

    await context.route("**/*", guard_request)
    await context.route_web_socket("**/*", guard_websocket)


def _origin(url: str) -> str:
    parsed = urlparse(redact(url))
    return f"{parsed.scheme}://{parsed.netloc}"


async def _click_first(page: Page, selectors: list[str], *, stop_after_first: bool) -> None:
    for selector in selectors:
        with suppress(PlaywrightError):
            locator = page.locator(selector)
            if await locator.count():
                await locator.first.click(timeout=1000)
                if stop_after_first:
                    await page.wait_for_timeout(500)
                    return


async def _dismiss_popups(page: Page) -> None:
    await _click_first(page, COOKIE_ACCEPT_SELECTORS, stop_after_first=True)
    for label in COOKIE_ACCEPT_LABELS:
        with suppress(PlaywrightError):
            button = page.get_by_role("button", name=label, exact=False)
            if await button.count():
                await button.first.click(timeout=1000)
                await page.wait_for_timeout(500)
                break
    await _click_first(page, POPUP_CLOSE_SELECTORS, stop_after_first=False)
    with suppress(PlaywrightError):
        await page.keyboard.press("Escape")


async def _scroll_to_price(page: Page, selector: str | None) -> None:
    with suppress(PlaywrightError):
        if selector:
            await page.wait_for_selector(selector, timeout=5000)
            await page.locator(selector).first.scroll_into_view_if_needed()
            return
        locator = page.locator(PRICE_LOCATOR)
        if await locator.count():
            await locator.first.scroll_into_view_if_needed()
