"""Tests for URL-based currency inference."""

import pytest

from app.utils.currency import infer_currency_from_url


class TestInferCurrencyFromUrl:
    """Test TLD-to-currency mapping."""

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://www.amazon.com/dp/B0123", "USD"),
            ("https://www.amazon.co.uk/dp/B0123", "GBP"),
            ("https://www.amazon.de/dp/B0123", "EUR"),
            ("https://www.amazon.fr/dp/B0123", "EUR"),
            ("https://www.amazon.es/dp/B0123", "EUR"),
            ("https://www.amazon.it/dp/B0123", "EUR"),
            ("https://www.amazon.co.jp/dp/B0123", "JPY"),
            ("https://www.amazon.ca/dp/B0123", "CAD"),
            ("https://www.amazon.com.au/dp/B0123", "AUD"),
            ("https://www.amazon.com.br/dp/B0123", "BRL"),
            ("https://www.amazon.com.mx/dp/B0123", "MXN"),
            ("https://www.amazon.in/dp/B0123", "INR"),
            ("https://www.amazon.nl/dp/B0123", "EUR"),
            ("https://www.amazon.se/dp/B0123", "SEK"),
            ("https://www.amazon.pl/dp/B0123", "PLN"),
            ("https://www.amazon.sg/dp/B0123", "SGD"),
        ],
    )
    def test_known_tlds(self, url: str, expected: str):
        assert infer_currency_from_url(url) == expected

    def test_defaults_to_usd(self):
        assert infer_currency_from_url("https://www.example.com/product") == "USD"

    def test_multi_part_tld_takes_priority(self):
        """Ensure .co.uk matches GBP, not just .uk."""
        assert infer_currency_from_url("https://shop.co.uk/item") == "GBP"

    def test_invalid_url(self):
        assert infer_currency_from_url("not-a-url") == "USD"

    def test_empty_string(self):
        assert infer_currency_from_url("") == "USD"

    def test_complex_url(self):
        """Currency should be inferred even with complex paths and query params."""
        url = "https://www.shop.de/category/product?id=123&ref=search"
        assert infer_currency_from_url(url) == "EUR"

    def test_subdomain_does_not_confuse(self):
        """Subdomains like 'uk.example.com' use .com TLD."""
        assert infer_currency_from_url("https://uk.example.com/product") == "USD"

    def test_co_nz(self):
        assert infer_currency_from_url("https://shop.co.nz/item") == "NZD"

    def test_co_za(self):
        assert infer_currency_from_url("https://shop.co.za/item") == "ZAR"
