"""Currency inference from URL TLD."""

from urllib.parse import urlparse

# Maps TLDs and country-code TLDs to ISO 4217 currency codes.
# Multi-part TLDs (e.g. ".co.uk") are checked first.
_MULTI_PART_TLD_MAP: dict[str, str] = {
    ".co.uk": "GBP",
    ".org.uk": "GBP",
    ".co.jp": "JPY",
    ".co.kr": "KRW",
    ".co.in": "INR",
    ".com.au": "AUD",
    ".com.br": "BRL",
    ".com.mx": "MXN",
    ".com.tr": "TRY",
    ".co.nz": "NZD",
    ".co.za": "ZAR",
}

_TLD_MAP: dict[str, str] = {
    ".uk": "GBP",
    ".de": "EUR",
    ".fr": "EUR",
    ".es": "EUR",
    ".it": "EUR",
    ".nl": "EUR",
    ".be": "EUR",
    ".at": "EUR",
    ".pt": "EUR",
    ".ie": "EUR",
    ".fi": "EUR",
    ".gr": "EUR",
    ".eu": "EUR",
    ".jp": "JPY",
    ".cn": "CNY",
    ".kr": "KRW",
    ".in": "INR",
    ".au": "AUD",
    ".ca": "CAD",
    ".br": "BRL",
    ".mx": "MXN",
    ".se": "SEK",
    ".no": "NOK",
    ".dk": "DKK",
    ".ch": "CHF",
    ".pl": "PLN",
    ".cz": "CZK",
    ".ru": "RUB",
    ".tr": "TRY",
    ".nz": "NZD",
    ".za": "ZAR",
    ".sg": "SGD",
    ".hk": "HKD",
    ".tw": "TWD",
    ".th": "THB",
    ".my": "MYR",
    ".il": "ILS",
    ".ae": "AED",
    ".sa": "SAR",
}


def infer_currency_from_url(url: str) -> str:
    """Infer the most likely currency from a URL's TLD.

    Args:
        url: Product URL to analyze.

    Returns:
        ISO 4217 currency code (defaults to ``"USD"``).
    """
    try:
        hostname = urlparse(url).hostname or ""
        hostname = hostname.lower()
    except Exception:
        return "USD"

    # Check multi-part TLDs first (more specific)
    for tld, currency in _MULTI_PART_TLD_MAP.items():
        if hostname.endswith(tld):
            return currency

    # Check single TLDs
    for tld, currency in _TLD_MAP.items():
        if hostname.endswith(tld):
            return currency

    return "USD"
