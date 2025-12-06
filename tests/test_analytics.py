from datetime import datetime, timedelta

import pytest

from app import models
from app.services.item_service import ItemService


@pytest.fixture(autouse=True)
def clear_cache():
    ItemService.clear_cache()
    yield
    ItemService.clear_cache()


@pytest.mark.asyncio
async def test_get_analytics_data_empty(db):
    # Create item
    item = models.Item(url="http://example.com/1", name="Test Item 1")
    db.add(item)
    await db.commit()
    await db.refresh(item)

    data = await ItemService.get_analytics_data(db, item.id)
    assert data["item_id"] == item.id
    assert data["stats"]["avg_price"] == 0.0
    assert len(data["history"]) == 0


@pytest.mark.asyncio
async def test_get_analytics_data_stats(db):
    # Create item
    item = models.Item(url="http://example.com/2", name="Test Item 2", current_price=100.0)
    db.add(item)
    await db.commit()
    await db.refresh(item)

    # Add history
    prices = [100.0, 102.0, 98.0, 100.0]
    now = datetime.now()
    for i, p in enumerate(prices):
        # timestamps spaced by 1 hour
        ts = now - timedelta(hours=len(prices) - i)
        ph = models.PriceHistory(item_id=item.id, price=p, timestamp=ts)
        db.add(ph)

    await db.commit()

    data = await ItemService.get_analytics_data(db, item.id)
    assert data["stats"]["min_price"] == 98.0
    assert data["stats"]["max_price"] == 102.0
    assert data["stats"]["avg_price"] == 100.0
    assert data["stats"]["latest_price"] == 100.0
    assert len(data["history"]) == 4


@pytest.mark.asyncio
async def test_get_analytics_outlier_filtering(db):
    # Create item
    item = models.Item(url="http://example.com/3", name="Test Item 3")
    db.add(item)
    await db.commit()

    # Create a stable history and one massive outlier
    # Mean approx 100.
    prices = [100.0] * 10
    prices.append(1000.0)  # Massive outlier

    now = datetime.now()
    for i, p in enumerate(prices):
        ts = now - timedelta(hours=len(prices) - i)
        ph = models.PriceHistory(item_id=item.id, price=p, timestamp=ts)
        db.add(ph)

    await db.commit()

    # Without filter
    data = await ItemService.get_analytics_data(db, item.id)
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

    data_filtered = await ItemService.get_analytics_data(db, item.id, std_dev_threshold=2.0)

    # Outlier should be gone
    assert len(data_filtered["history"]) == 10
    for h in data_filtered["history"]:
        assert h.price == 100.0

    # Stats should still reflect the raw data per my implementation choice
    assert data_filtered["stats"]["max_price"] == 1000.0


@pytest.mark.asyncio
async def test_get_analytics_downsampling(db):
    # Create item
    item = models.Item(url="http://example.com/4", name="Test Item 4")
    db.add(item)
    await db.commit()

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

    await db.commit()

    data = await ItemService.get_analytics_data(db, item.id)

    # Check that we downsampled
    history_len = len(data["history"])
    assert history_len <= 150
    assert history_len > 0

    # Stats should be on RAW data
    assert data["stats"]["min_price"] == 0.0
    assert data["stats"]["max_price"] == 299.0

    # Check that aggregation worked somewhat correctly (middle point should be ~150)
    # Since prices are 0..299, avg is ~150.
    # Check that aggregation worked somewhat correctly (middle point should be ~150)
    # Since prices are 0..299, avg is ~150.
    assert 140 < data["stats"]["avg_price"] < 160


@pytest.mark.asyncio
async def test_get_analytics_annotations(db):
    # Create item
    item = models.Item(url="http://example.com/5", name="Test Item 5")
    db.add(item)
    await db.commit()

    # Create history with clear min and max
    # 100, 50 (min), 150 (max), 100
    prices = [100.0, 50.0, 150.0, 100.0]
    now = datetime.now()

    for i, p in enumerate(prices):
        ts = now - timedelta(hours=len(prices) - i)
        ph = models.PriceHistory(item_id=item.id, price=p, timestamp=ts)
        db.add(ph)

    await db.commit()

    data = await ItemService.get_analytics_data(db, item.id)

    annotations = data["annotations"]
    assert len(annotations) == 2

    # Sort by value to easily check min/max
    annotations.sort(key=lambda x: x["value"])

    # Min
    assert annotations[0]["type"] == "min"
    assert annotations[0]["value"] == 50.0
    assert "Lowest" in annotations[0]["label"]

    # Max
    assert annotations[1]["type"] == "max"
    assert "Highest" in annotations[1]["label"]


@pytest.mark.asyncio
async def test_get_analytics_stock_history(db):
    # Create item
    item = models.Item(url="http://example.com/6", name="Test Item 6")
    db.add(item)
    await db.commit()

    # Create mixed stock history
    # 0: In Stock
    # 1: Out of Stock
    # 2: In Stock
    stock_statuses = [True, False, True, True]
    now = datetime.now()

    for i, stock in enumerate(stock_statuses):
        ph = models.PriceHistory(
            item_id=item.id,
            price=100.0,
            timestamp=now - timedelta(hours=len(stock_statuses) - i),
            in_stock=stock,
        )
        db.add(ph)

    await db.commit()

    data = await ItemService.get_analytics_data(db, item.id)

    # Check if history contains correct stock status
    history = data["history"]
    assert len(history) == 4

    # We expect stock status to be preserved in raw history
    # Order is chronological
    assert history[0].in_stock is True
    assert history[1].in_stock is False
    assert history[2].in_stock is True
    assert history[3].in_stock is True


@pytest.mark.asyncio
async def test_get_analytics_stock_history_aggregation(db):
    # Test that aggregation preserves "max" (optimistic) stock status
    item = models.Item(url="http://example.com/7", name="Test Item 7")
    db.add(item)
    await db.commit()

    # Create many points in a short time frame so they get aggregated
    # But since downsampling triggers at > 150 points, we need > 150 points.
    points = 200
    now = datetime.now()
    step = timedelta(minutes=1)

    # All prices uniform, but stock toggles
    # If using MAX, a bucket with Mixed stock should result in True
    for i in range(points):
        # Every 10th item is in stock, others out
        in_stock = (i % 10) == 0
        ph = models.PriceHistory(
            item_id=item.id, price=10.0, timestamp=now - (step * points) + (step * i), in_stock=in_stock
        )
        db.add(ph)

    await db.commit()

    data = await ItemService.get_analytics_data(db, item.id)
    history = data["history"]

    # Should be downsampled
    assert len(history) <= 155

    # Check that we have True values (since MAX(true, false) = true)
    # Since we have Trues regularly distributed, most buckets should have at least one True.
    # Actually, with 200 points to 150 buckets, bucket size is small (~1.3 items/bucket).
    # Some buckets might only have 'False' items.

    has_true = any(h.in_stock for h in history)
    assert has_true
