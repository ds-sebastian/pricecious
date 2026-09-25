import asyncio
import logging
from urllib.parse import urlparse

import apprise

from app.ai import infer_currency
from app.models import Item

logger = logging.getLogger(__name__)


def mask(url: str) -> str:
    """Hide credentials but keep the service name visible, e.g. 'discord://********'."""
    scheme, has_scheme, _ = url.partition("://")
    return f"{scheme}://********" if has_scheme else "********"


def is_valid_url(url: str) -> bool:
    return apprise.Apprise().add(url)


async def send(url: str, title: str, body: str) -> bool:
    def _send() -> bool:
        notifier = apprise.Apprise()
        return notifier.add(url) and bool(notifier.notify(title=title, body=body))

    sent = await asyncio.to_thread(_send)
    if not sent:
        logger.warning(f"Notification failed: {title}")
    return sent


CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "INR": "₹", "KRW": "₩"}


def money(value: float, currency: str) -> str:
    symbol = CURRENCY_SYMBOLS.get(currency)
    return f"{symbol}{value:,.2f}" if symbol else f"{value:,.2f} {currency}"


def display_name(item: Item) -> str:
    return item.name or urlparse(item.url).hostname or item.url


def alerts(
    item: Item, old_price: float | None, old_stock: bool | None, previous_low: float | None = None
) -> list[tuple[str, str]]:
    """Return (title, body) pairs for the changes the item's notification profile wants to hear about.

    previous_low is the lowest price seen before this check, or None when there isn't enough history.
    """
    profile = item.notification_profile
    if profile is None:
        return []
    name, target, price, in_stock = display_name(item), item.target_price, item.current_price, item.in_stock
    currency = item.currency or infer_currency(item.url)
    messages = []
    dropped = price is not None and old_price is not None and price < old_price
    drop = (old_price - price) / old_price * 100 if dropped and old_price else 0.0
    # With a range the tracked price is the cheapest option; say so, and name any store promotion.
    cheapest = " for the cheapest option" if item.price_high else ""
    now = f"{money(price, currency)}{cheapest}" if price is not None else ""
    promo = f" ({item.promotion})" if item.promotion else ""
    change = f"Down {drop:.1f}% to {now} (was {money(old_price, currency)}){promo}" if dropped else ""

    if profile.notify_on_new_low and dropped and previous_low is not None and price < previous_low:
        # Covers the ordinary price-drop alert too, so only one message is sent.
        messages.append((f"Lowest price yet: {name}", f"{change}. Previous low {money(previous_low, currency)}."))
    elif profile.notify_on_price_drop and dropped and drop >= profile.price_drop_threshold_percent:
        messages.append((f"Price drop: {name}", change))
    if (
        profile.notify_on_target_price
        and price is not None
        and target is not None
        and price <= target
        and (old_price is None or old_price > target)
    ):
        messages.append((f"Target price reached: {name}", f"Now {now} (target {money(target, currency)}){promo}"))
    if profile.notify_on_stock_change and None not in (old_stock, in_stock) and old_stock != in_stock:
        messages.append((f"Stock change: {name}", "Back in stock" if in_stock else "Out of stock"))
    return messages
