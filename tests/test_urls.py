import socket

import pytest

from app.urls import UnsafeURLError, redact, validate_url


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/product",
        "http://example.com/product?id=1&ref=abc#reviews",
        "https://example.com:8443/product",
        "https://例え.jp/product",
        "http://8.8.8.8/",
    ],
)
def test_public_urls_are_allowed(url):
    validate_url(url)


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("", "non-empty"),
        (None, "non-empty"),
        ("example.com/product", "Only http"),
        ("file:///etc/passwd", "Only http"),
        ("javascript:alert(1)", "Only http"),
        ("ftp://example.com/file", "Only http"),
        ("http:///path", "hostname"),
        ("http://user:pass@example.com/", "credentials"),
        ("http://example.com:99999/", "Invalid URL"),
    ],
)
def test_malformed_urls_are_rejected(url, message):
    with pytest.raises(UnsafeURLError, match=message):
        validate_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/",
        "http://127.0.0.1/",
        "http://127.1/",
        "http://0.0.0.0/",
        "http://10.1.2.3/",
        "http://172.16.0.1/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]:8000/",
    ],
)
def test_private_addresses_are_rejected(url):
    with pytest.raises(UnsafeURLError, match="Private/internal"):
        validate_url(url)


def test_hostname_resolving_to_private_address_is_rejected(monkeypatch):
    monkeypatch.setattr(
        "app.urls.socket.getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
            (0, 0, 0, "", ("10.0.0.5", 80)),
        ],
    )
    with pytest.raises(UnsafeURLError, match="Private/internal"):
        validate_url("http://rebinding.example/")


def test_allow_private_skips_resolution():
    validate_url("http://192.168.1.1/", allow_private=True)


def test_redact_strips_credentials_query_and_fragment():
    assert redact("wss://user:secret@host:3000/chromium?token=abc#x") == "wss://host:3000/chromium"
    assert redact("http://[::1]:9222/json") == "http://[::1]:9222/json"
