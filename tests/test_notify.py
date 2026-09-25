import pytest

from app.models import Item, NotificationProfile
from app.notify import alerts, mask


def item(profile=None, **fields) -> Item:
    profile = profile or NotificationProfile(
        notify_on_price_drop=True,
        notify_on_target_price=True,
        notify_on_stock_change=True,
        price_drop_threshold_percent=10.0,
    )
    return Item(name="Widget", notification_profile=profile, **fields)


def titles(messages):
    return [title for title, _ in messages]


def test_no_profile_means_no_alerts():
    assert alerts(Item(name="Widget", current_price=1.0), old_price=100.0, old_stock=None) == []


@pytest.mark.parametrize(("old", "new", "expected"), [(100.0, 89.0, True), (100.0, 95.0, False), (None, 50.0, False)])
def test_price_drop_needs_threshold(old, new, expected):
    messages = alerts(item(current_price=new), old_price=old, old_stock=None)
    assert ("Price drop: Widget" in titles(messages)) is expected


def test_target_price_alerts_only_when_crossed():
    assert "Target price reached: Widget" in titles(
        alerts(item(current_price=99.0, target_price=100.0), old_price=105.0, old_stock=None)
    )
    # Already below target on the previous check: don't repeat the alert every time.
    assert alerts(item(current_price=98.0, target_price=100.0), old_price=99.0, old_stock=None) == []


def test_stock_change_alerts_both_ways():
    back = alerts(item(in_stock=True), old_price=None, old_stock=False)
    gone = alerts(item(in_stock=False), old_price=None, old_stock=True)
    assert back == [("Stock change: Widget", "Back in stock")]
    assert gone == [("Stock change: Widget", "Out of stock")]
    assert alerts(item(in_stock=True), old_price=None, old_stock=None) == []


def test_disabled_alerts_stay_quiet():
    profile = NotificationProfile(
        notify_on_price_drop=False, notify_on_target_price=False, notify_on_stock_change=False
    )
    assert alerts(item(profile, current_price=1.0, target_price=5.0, in_stock=True), 100.0, False) == []


def test_mask_keeps_only_the_service():
    assert mask("tgram://bot_token/chat_id") == "tgram://********"
    assert mask("garbage") == "********"
