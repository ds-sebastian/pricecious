import asyncio
import logging

import apprise

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


def alerts(item: Item, old_price: float | None, old_stock: bool | None) -> list[tuple[str, str]]:
    """Return (title, body) pairs for the changes the item's notification profile wants to hear about."""
    profile = item.notification_profile
    if profile is None:
        return []
    name, target_price, price, in_stock = item.name, item.target_price, item.current_price, item.in_stock
    messages = []
    if profile.notify_on_price_drop and price is not None and old_price and price < old_price:
        drop = (old_price - price) / old_price * 100
        if drop >= profile.price_drop_threshold_percent:
            messages.append((f"Price drop: {name}", f"Down {drop:.1f}% to ${price:.2f} (was ${old_price:.2f})"))
    if (
        profile.notify_on_target_price
        and price is not None
        and target_price is not None
        and price <= target_price
        and (old_price is None or old_price > target_price)
    ):
        messages.append((f"Target price reached: {name}", f"Now ${price:.2f} (target ${target_price:.2f})"))
    if profile.notify_on_stock_change and None not in (old_stock, in_stock) and old_stock != in_stock:
        messages.append((f"Stock change: {name}", "Back in stock" if in_stock else "Out of stock"))
    return messages
