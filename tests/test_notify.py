import pytest

from app.models import Item, NotificationProfile
from app.notify import alerts, mask


def item(profile=None, **fields) -> Item:
    profile = profile or NotificationProfile(
        notify_on_price_drop=True,
        notify_on_target_price=True,
        notify_on_stock_change=True,
        notify_on_new_low=True,
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


def test_new_low_replaces_the_price_drop_alert():
    messages = alerts(item(current_price=80.0, currency="EUR"), old_price=100.0, old_stock=None, previous_low=90.0)
    assert messages == [("Lowest price yet: Widget", "Down 20.0% to €80.00 (was €100.00). Previous low €90.00.")]


def test_no_new_low_without_enough_history_or_a_real_record():
    assert titles(alerts(item(current_price=80.0), old_price=100.0, old_stock=None)) == ["Price drop: Widget"]
    assert titles(alerts(item(current_price=95.0), old_price=100.0, old_stock=None, previous_low=90.0)) == []


def test_messages_use_the_item_currency_and_fall_back_to_the_host():
    unnamed = Item(url="https://www.shop.example/x", current_price=5.0, target_price=6.0, currency="CHF")
    unnamed.notification_profile = item().notification_profile
    assert alerts(unnamed, old_price=7.0, old_stock=None)[-1] == (
        "Target price reached: www.shop.example",
        "Now 5.00 CHF (target 6.00 CHF)",
    )


def test_alerts_mention_ranges_and_promotions():
    sale = item(current_price=1799.0, price_high=2048.0, promotion="Limited Time Offer", target_price=1800.0)
    assert alerts(sale, old_price=1999.0, old_stock=None) == [
        ("Price drop: Widget", "Down 10.0% to $1,799.00 for the cheapest option (was $1,999.00) (Limited Time Offer)"),
        (
            "Target price reached: Widget",
            "Now $1,799.00 for the cheapest option (target $1,800.00) (Limited Time Offer)",
        ),
    ]


def test_a_zero_price_is_still_named():
    messages = alerts(item(current_price=0.0, target_price=10.0, currency="USD"), old_price=20.0, old_stock=None)
    assert ("Target price reached: Widget", "Now $0.00 (target $10.00)") in messages
