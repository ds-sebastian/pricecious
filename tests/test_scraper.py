import io
import json
import logging
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
from PIL import Image

from app import scraper
from app.scraper import Capture, ScrapeError, browserless_url, content_problem
from app.urls import UnsafeURLError

BROWSERLESS_ENV = [
    "BROWSERLESS_TOKEN",
    "BROWSERLESS_BLOCK_ADS",
    "BROWSERLESS_STEALTH",
    "BROWSERLESS_HEADLESS",
    "BROWSERLESS_VIEWPORT_WIDTH",
    "BROWSERLESS_VIEWPORT_HEIGHT",
]


@pytest.fixture
def env(monkeypatch):
    for name in BROWSERLESS_ENV:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch.setenv


def query(url):
    return {key: values[0] for key, values in parse_qs(urlparse(url).query).items()}


def test_browserless_url_without_options_is_unchanged(env):
    assert browserless_url("ws://browserless:3000") == "ws://browserless:3000"


def test_browserless_url_combines_options(env):
    env("BROWSERLESS_TOKEN", "secret")
    env("BROWSERLESS_BLOCK_ADS", "true")
    env("BROWSERLESS_STEALTH", "1")
    env("BROWSERLESS_HEADLESS", "new")
    env("BROWSERLESS_VIEWPORT_WIDTH", "1920")
    env("BROWSERLESS_VIEWPORT_HEIGHT", "1080")

    params = query(browserless_url("ws://host:3000/chromium?timeout=60000"))

    assert params["timeout"] == "60000"
    assert params["token"] == "secret"
    assert params["blockAds"] == "true"
    assert json.loads(params["launch"]) == {
        "stealth": True,
        "headless": "new",
        "defaultViewport": {"width": 1920, "height": 1080},
    }


def test_browserless_url_parses_headless_booleans_and_ignores_bad_viewport(env):
    env("BROWSERLESS_HEADLESS", "TRUE")
    env("BROWSERLESS_VIEWPORT_WIDTH", "wide")
    env("BROWSERLESS_BLOCK_ADS", "false")

    params = query(browserless_url("ws://host"))

    assert json.loads(params["launch"]) == {"headless": True}
    assert "blockAds" not in params


@pytest.mark.parametrize("path", ["/chromium", "/chrome", "/devtools/browser/abc"])
async def test_known_endpoints_skip_discovery(monkeypatch, path):
    client = MagicMock()
    monkeypatch.setattr(scraper.httpx, "AsyncClient", client)
    assert await scraper._resolve_ws_url(f"ws://host:3000{path}") == f"ws://host:3000{path}"
    client.assert_not_called()


async def test_plain_chrome_discovers_websocket_url(monkeypatch):
    response = MagicMock()
    response.json.return_value = {"webSocketDebuggerUrl": "ws://host:9222/devtools/browser/123"}
    http = AsyncMock()
    http.get.return_value = response
    client = MagicMock()
    client.return_value.__aenter__.return_value = http
    monkeypatch.setattr(scraper.httpx, "AsyncClient", client)

    assert await scraper._resolve_ws_url("ws://host:9222") == "ws://host:9222/devtools/browser/123"
    http.get.assert_awaited_once_with("http://host:9222/json/version")


async def test_discovery_failure_falls_back_to_base_url(monkeypatch):
    client = MagicMock()
    client.return_value.__aenter__.side_effect = ConnectionError
    monkeypatch.setattr(scraper.httpx, "AsyncClient", client)
    assert await scraper._resolve_ws_url("wss://host") == "wss://host"


async def test_connection_error_does_not_leak_the_token(env, monkeypatch):
    env("BROWSERLESS_TOKEN", "super-secret")
    playwright = MagicMock()
    playwright.chromium.connect_over_cdp = AsyncMock(side_effect=Exception("401 Unauthorized token=super-secret"))
    playwright.stop = AsyncMock()
    monkeypatch.setattr(scraper, "async_playwright", lambda: MagicMock(start=AsyncMock(return_value=playwright)))
    monkeypatch.setattr(scraper, "BROWSERLESS_URL", "ws://browserless:3000/chromium")

    with pytest.raises(ScrapeError) as error:
        await scraper.start()

    assert "super-secret" not in str(error.value)
    assert "authentication was rejected" in str(error.value)
    assert scraper._conn.browser is None


def image_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_content_checks(png):
    assert content_problem(png, "Widget $19.99 Add to cart") is None
    assert content_problem(b"tiny", "") == "Page looks blank"
    blank = image_bytes(Image.new("RGB", (4000, 3000), "white"))
    assert content_problem(blank + b"\0" * 10_000, "") == "Page looks blank"
    assert "bot check" in content_problem(png, "Please complete the captcha to continue")
    # Long real pages mentioning a phrase are fine.
    assert content_problem(png, "captcha " + "word " * 200) is None


async def test_capture_rejects_unsafe_urls():
    with pytest.raises(ScrapeError, match="Blocked URL"):
        await scraper.capture("http://127.0.0.1:8000/admin")


async def test_capture_retries_once(monkeypatch, png):
    attempt = AsyncMock(side_effect=[ScrapeError("Page failed to load: timeout"), Capture(png, "ok")])
    monkeypatch.setattr(scraper, "_capture_once", attempt)
    monkeypatch.setattr(scraper, "RETRY_DELAY_SECONDS", 0)

    assert (await scraper.capture("https://example.com")).text == "ok"
    assert attempt.await_count == 2


async def test_capture_gives_up_after_last_attempt(monkeypatch):
    monkeypatch.setattr(scraper, "_capture_once", AsyncMock(side_effect=ScrapeError("still broken")))
    monkeypatch.setattr(scraper, "RETRY_DELAY_SECONDS", 0)
    with pytest.raises(ScrapeError, match="still broken"):
        await scraper.capture("https://example.com")


async def test_network_guard_blocks_private_requests_and_logs_each_origin_once(monkeypatch, caplog):
    context = AsyncMock()
    await scraper._guard_network(context)
    guard_request = context.route.await_args.args[1]
    validate = AsyncMock(side_effect=UnsafeURLError("Hostname could not be resolved: tracking.example"))
    monkeypatch.setattr(scraper, "validate_url_async", validate)
    monkeypatch.setattr(scraper.asyncio, "sleep", AsyncMock())

    with caplog.at_level(logging.WARNING, logger="app.scraper"):
        for secret in ("one", "two"):
            route = AsyncMock()
            route.request.url = f"https://tracking.example/event?secret={secret}"
            await guard_request(route)
            route.abort.assert_awaited_once_with("blockedbyclient")

    assert validate.await_count == 4  # one DNS retry per request
    assert [r.message for r in caplog.records] == [
        "Blocked browser request to https://tracking.example: Hostname could not be resolved: tracking.example"
    ]


async def test_network_guard_allows_public_requests(monkeypatch):
    context = AsyncMock()
    await scraper._guard_network(context)
    guard_request = context.route.await_args.args[1]
    route = AsyncMock()
    route.request.url = "https://cdn.example.com/app.js"

    await guard_request(route)

    route.continue_.assert_awaited_once()


@pytest.mark.parametrize(
    ("title", "name"),
    [
        ("Acme K65 Keyboard | Acme Store", "Acme K65 Keyboard"),
        ("Amazon.com: SoundHall NC700 Wireless Headphones : Electronics", "SoundHall NC700 Wireless Headphones"),
        ('Lumen 27" 4K Monitor \u2013 Lumen Displays', 'Lumen 27" 4K Monitor'),
        ("  Plain   title ", "Plain title"),
        ("", None),
    ],
)
def test_product_name_from_page_title(title, name):
    assert scraper.product_name(title) == name
