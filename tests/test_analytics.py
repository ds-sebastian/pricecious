from datetime import datetime, timedelta

import pytest

from app import models
from app.services.item_service import ItemService


@pytest.fixture(autouse=True)
def clear_cache():
    ItemService.clear_cache()
    yield
    ItemService.clear_cache()


def test_get_analytics_data_empty(db):
    # Create item
    item = models.Item(url="http://example.com/1", name="Test Item 1")
    db.add(item)
    db.commit()
    db.refresh(item)

    data = ItemService.get_analytics_data(db, item.id)
    assert data["item_id"] == item.id
    assert data["stats"]["avg_price"] == 0.0
    assert len(data["history"]) == 0


def test_get_analytics_data_stats(db):
    # Create item
    item = models.Item(url="http://example.com/2", name="Test Item 2", current_price=100.0)
    db.add(item)
    db.commit()
    db.refresh(item)

    # Add history
    prices = [100.0, 102.0, 98.0, 100.0]
    now = datetime.now()
    for i, p in enumerate(prices):
        # timestamps spaced by 1 hour
        ts = now - timedelta(hours=len(prices) - i)
        ph = models.PriceHistory(item_id=item.id, price=p, timestamp=ts)
        db.add(ph)

    db.commit()

    data = ItemService.get_analytics_data(db, item.id)
    assert data["stats"]["min_price"] == 98.0
    assert data["stats"]["max_price"] == 102.0
    assert data["stats"]["avg_price"] == 100.0
    assert data["stats"]["latest_price"] == 100.0
    assert len(data["history"]) == 4


def test_get_analytics_outlier_filtering(db):
    # Create item
    item = models.Item(url="http://example.com/3", name="Test Item 3")
    db.add(item)
    db.commit()

    # Create a stable history and one massive outlier
    # Mean approx 100.
    prices = [100.0] * 10
    prices.append(1000.0)  # Massive outlier

    now = datetime.now()
    for i, p in enumerate(prices):
        ts = now - timedelta(hours=len(prices) - i)
        ph = models.PriceHistory(item_id=item.id, price=p, timestamp=ts)
        db.add(ph)

    db.commit()

    # Without filter
    data = ItemService.get_analytics_data(db, item.id)
    assert len(data["history"]) == 11
    assert data["stats"]["max_price"] == 1000.0

    # With filter (e.g. 2 std dev)
    # Mean of [100*10, 1000] = 181.8
    # Std Dev is huge.
    # Let's use a simpler case. [100, 100, 100, 200]
    # Mean = 125, StdDev = 50.
    # 200 is 1.5 sigma from mean.
    # If threshold is 1.0, 200 should be removed.
    # Range: 125 +/- 50 = [75, 175]. 200 is outside.

    # Using the massive outlier:
    # Mean ~181. Stdev ~271.
    # Range 2 sigma: 181 +/- 542 = [-361, 723].
    # 1000 is outside 723. It should be filtered.

    data_filtered = ItemService.get_analytics_data(db, item.id, std_dev_threshold=2.0)

    # Outlier should be gone
    assert len(data_filtered["history"]) == 10
    for h in data_filtered["history"]:
        assert h.price == 100.0

    # Stats should still reflect the raw data per my implementation choice
    assert data_filtered["stats"]["max_price"] == 1000.0


def test_get_analytics_downsampling(db):
    # Create item
    item = models.Item(url="http://example.com/4", name="Test Item 4")
    db.add(item)
    db.commit()

    # Create 300 history points (linear increase)
    # 0 to 299
    points = 300
    now = datetime.now()
    start_time = now - timedelta(days=10)
    # Time step = 10 days / 300 = 48 minutes roughly
    step = timedelta(minutes=48)

    for i in range(points):
        ph = models.PriceHistory(item_id=item.id, price=float(i), timestamp=start_time + (step * i))
        db.add(ph)

    db.commit()

    data = ItemService.get_analytics_data(db, item.id)

    # Check that we downsampled
    history_len = len(data["history"])
    assert history_len <= 150
    assert history_len > 0

    # Stats should be on RAW data
    assert data["stats"]["min_price"] == 0.0
    assert data["stats"]["max_price"] == 299.0

    # Check that aggregation worked somewhat correctly (middle point should be ~150)
    # Since prices are 0..299, avg is ~150.
    assert 140 < data["stats"]["avg_price"] < 160
