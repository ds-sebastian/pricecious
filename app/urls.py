"""URL checks that keep the scraper away from private networks (SSRF)."""

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse, urlunparse


class UnsafeURLError(ValueError):
    pass


class UnresolvableHostError(UnsafeURLError):
    """DNS has no answer for the host, so the request would fail anyway."""


def validate_url(url: str, allow_private: bool = False) -> None:
    """Allow only credential-free HTTP(S) URLs whose host resolves exclusively to public IPs."""
    if not url or not isinstance(url, str):
        raise UnsafeURLError("URL must be a non-empty string")
    try:
        parsed = urlparse(url.strip())
        port = parsed.port  # raises on malformed ports
    except ValueError as exc:
        raise UnsafeURLError(f"Invalid URL: {exc}") from exc

    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeURLError("Only http:// and https:// URLs are allowed")
    if not parsed.hostname:
        raise UnsafeURLError("URL must include a hostname")
    if parsed.username or parsed.password:
        raise UnsafeURLError("URLs containing credentials are not allowed")
    if allow_private:
        return

    try:
        infos = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnresolvableHostError(f"Hostname could not be resolved: {parsed.hostname}") from exc
    addresses = {info[4][0] for info in infos}
    if not addresses or not all(ipaddress.ip_address(a).is_global for a in addresses):
        raise UnsafeURLError(f"Private/internal addresses are not allowed: {parsed.hostname}")


async def validate_url_async(url: str) -> None:
    await asyncio.to_thread(validate_url, url)


def redact(url: str) -> str:
    """Drop credentials, query and fragment so a URL is safe to log."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if ":" in host:
            host = f"[{host}]"
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return urlunparse(parsed._replace(netloc=host, query="", fragment=""))
    except ValueError:
        return "<invalid URL>"
