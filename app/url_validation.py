"""URL validation utilities for security."""

import re
from urllib.parse import urlparse


class URLValidationError(Exception):
    """Raised when URL validation fails."""

    pass


# Blocked schemes that could be used for SSRF
BLOCKED_SCHEMES = {"file", "javascript", "data", "ftp"}

# Private IP ranges (RFC 1918, RFC 4193, loopback)
PRIVATE_IP_PATTERNS = [
    re.compile(r"^127\."),  # Loopback
    re.compile(r"^10\."),  # Private Class A
    re.compile(r"^172\.(1[6-9]|2[0-9]|3[0-1])\."),  # Private Class B
    re.compile(r"^192\.168\."),  # Private Class C
    re.compile(r"^169\.254\."),  # Link-local
    re.compile(r"^::1$"),  # IPv6 loopback
    re.compile(r"^fc00:"),  # IPv6 private
    re.compile(r"^fe80:"),  # IPv6 link-local
    re.compile(r"^localhost$", re.IGNORECASE),
]


def validate_url(url: str, allow_private: bool = False) -> None:
    """
    Validate URL for security (SSRF prevention).

    Args:
        url: URL to validate
        allow_private: Allow private/internal IPs (default: False)

    Raises:
        URLValidationError: If URL is invalid or blocked
    """
    if not url or not isinstance(url, str):
        raise URLValidationError("URL must be a non-empty string")

    try:
        parsed = urlparse(url.strip())
    except Exception as e:
        raise URLValidationError(f"Invalid URL format: {e}") from e

    # Check scheme
    if not parsed.scheme:
        raise URLValidationError("URL must include a scheme (http:// or https://)")

    if parsed.scheme.lower() in BLOCKED_SCHEMES:
        raise URLValidationError(f"Blocked URL scheme: {parsed.scheme}")

    if parsed.scheme.lower() not in {"http", "https"}:
        raise URLValidationError(f"Only HTTP/HTTPS schemes allowed, got: {parsed.scheme}")

    # Check hostname
    if not parsed.hostname:
        raise URLValidationError("URL must include a hostname")

    # Check for private IPs unless explicitly allowed
    if not allow_private:
        hostname = parsed.hostname.lower()
        for pattern in PRIVATE_IP_PATTERNS:
            if pattern.match(hostname):
                raise URLValidationError(f"Private/internal IPs not allowed: {hostname}")
