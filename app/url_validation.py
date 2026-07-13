"""URL validation utilities for SSRF prevention."""

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse


class URLValidationError(Exception):
    """Raised when URL validation fails."""


def validate_url(url: str, allow_private: bool = False) -> None:
    """Allow only HTTP(S) URLs whose hostname resolves exclusively to public IPs."""
    if not url or not isinstance(url, str):
        raise URLValidationError("URL must be a non-empty string")

    try:
        parsed = urlparse(url.strip())
        port = parsed.port  # Force validation of malformed ports.
    except (TypeError, ValueError) as exc:
        raise URLValidationError(f"Invalid URL format: {exc}") from exc

    if not parsed.scheme:
        raise URLValidationError("URL must include a scheme (http:// or https://)")
    if parsed.scheme.lower() not in {"http", "https"}:
        raise URLValidationError(f"Blocked URL scheme: {parsed.scheme}; only HTTP/HTTPS are allowed")
    if not parsed.hostname:
        raise URLValidationError("URL must include a hostname")
    if parsed.username or parsed.password:
        raise URLValidationError("URLs containing credentials are not allowed")
    if allow_private:
        return

    hostname = parsed.hostname
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise URLValidationError(f"Hostname could not be resolved: {hostname}") from exc

    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise URLValidationError(f"Private/internal IPs not allowed: {hostname}")


async def validate_url_async(url: str, allow_private: bool = False) -> None:
    """Resolve without blocking the event loop."""
    await asyncio.to_thread(validate_url, url, allow_private)
