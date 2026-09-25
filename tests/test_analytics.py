from datetime import timedelta

import pytest

from app.analytics import CHART_POINTS, deals, item_analytics, previous_low
from app.database import utcnow
from app.models import Item, PriceForecast, PriceHistory


@pytest.fixture
async def item(db):
    item = Item(url="https://example.com", name="Widget")
    db.add(item)
    await db.commit()
    return item


def add_history(db, item, *points):
    """points: (hours_ago, price, in_stock)"""
    now = utcnow()
    db.add_all(
        PriceHistory(item_id=item.id, timestamp=now - timedelta(hours=h), price=p, in_stock=s) for h, p, s in points
    )


async def test_empty_history(db, item):
    data = await item_analytics(db, item, days=30, sigma=None)
    assert data == {"stats": None, "history": [], "annotations": [], "forecast": []}


async def test_stats_and_24h_change(db, item):
    add_history(db, item, (48, 100.0, True), (30, 120.0, True), (1, 90.0, True))
    await db.commit()

    stats = (await item_analytics(db, item, days=None, sigma=None))["stats"]

    assert (stats["latest"], stats["min"], stats["max"]) == (90.0, 90.0, 120.0)
    assert stats["avg"] == pytest.approx(103.33, abs=0.01)
    assert stats["change_24h"] == pytest.approx(-25.0)


async def test_days_window_and_unknown_24h_change(db, item):
    add_history(db, item, (24 * 40, 500.0, None), (2, 100.0, None))
    await db.commit()

    data = await item_analytics(db, item, days=30, sigma=None)

    assert [p["price"] for p in data["history"]] == [100.0]
    assert data["stats"]["change_24h"] is None


async def test_outliers_are_filtered_from_chart_but_not_stats(db, item):
    add_history(db, item, *[(h, 100.0, True) for h in range(10, 20)], (5, 1000.0, True))
    await db.commit()

    data = await item_analytics(db, item, days=None, sigma=2)

    assert data["stats"]["max"] == 1000.0
    assert max(p["price"] for p in data["history"]) == 100.0


async def test_history_is_downsampled_to_real_readings(db, item):
    prices = [100.0 + h % 7 for h in range(2000)]
    prices[1234] = 500.0  # a one-off spike must survive thinning
    add_history(db, item, *[(h / 4, prices[h], None) for h in range(2000)])
    await db.commit()

    history = (await item_analytics(db, item, days=None, sigma=None))["history"]

    assert len(history) <= 4 * (CHART_POINTS + 1)
    assert history == sorted(history, key=lambda p: p["timestamp"])
    assert {p["price"] for p in history} <= set(prices)  # nothing averaged into a price never seen
    assert max(p["price"] for p in history) == 500.0


async def test_annotations_mark_extremes_and_stock_changes(db, item):
    add_history(db, item, (5, 100.0, True), (4, 80.0, False), (3, 120.0, None), (2, 110.0, True))
    await db.commit()

    notes = (await item_analytics(db, item, days=None, sigma=None))["annotations"]

    assert [(n["type"], n["price"]) for n in notes] == [
        ("min", 80.0),
        ("max", 120.0),
        ("out_of_stock", 80.0),
        ("restocked", 110.0),
    ]


async def test_forecast_is_included(db, item):
    db.add(PriceForecast(item_id=item.id, forecast_date=utcnow(), predicted_price=9, yhat_lower=8, yhat_upper=10))
    await db.commit()

    forecast = (await item_analytics(db, item, days=None, sigma=None))["forecast"]

    assert [(f["price"], f["lower"], f["upper"]) for f in forecast] == [(9, 8, 10)]


async def deal_for(db, item, current, points):
    """points: (days_ago, price, confidence)"""
    now = utcnow()
    db.add_all(
        PriceHistory(item_id=item.id, timestamp=now - timedelta(days=d), price=p, price_confidence=c)
        for d, p, c in points
    )
    item.current_price = current
    await db.commit()
    return (await deals(db, [item], threshold=0.5)).get(item.id)


async def test_lowest_price_seen(db, item):
    assert await deal_for(db, item, 90.0, [(30, 120.0, 0.9), (1, 90.0, 0.9)]) == "lowest_seen"


async def test_lowest_in_90_days_needs_90_days_of_history(db, item):
    points = [(200, 50.0, 0.9), (60, 120.0, 0.9), (1, 90.0, 0.9)]
    assert await deal_for(db, item, 90.0, points) == "lowest_90d"


@pytest.mark.parametrize(
    "points",
    [
        [(60, 90.0, 0.9), (1, 90.0, 0.9)],  # never higher: not a deal
        [(5, 120.0, 0.9), (1, 90.0, 0.9)],  # too little history to call it a record
        [(30, 120.0, 0.9), (20, 10.0, 0.2), (1, 90.0, 0.9)],  # a misread doesn't count, so this is a record
    ],
)
async def test_deal_edge_cases(db, item, points):
    expected = "lowest_seen" if points[1][2] == 0.2 else None
    assert await deal_for(db, item, 90.0, points) == expected


async def test_previous_low_ignores_misreads_and_short_histories(db, item):
    now = utcnow()
    db.add_all(
        [
            PriceHistory(item_id=item.id, timestamp=now - timedelta(days=3), price=100.0, price_confidence=0.9),
            PriceHistory(item_id=item.id, timestamp=now - timedelta(days=2), price=5.0, price_confidence=0.1),
        ]
    )
    await db.commit()
    assert await previous_low(db, item.id, 0.5) is None  # only 3 days tracked

    db.add(PriceHistory(item_id=item.id, timestamp=now - timedelta(days=20), price=110.0, price_confidence=0.9))
    await db.commit()
    assert await previous_low(db, item.id, 0.5) == 100.0
