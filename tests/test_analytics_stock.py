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
async def test_get_analytics_stock_annotations(db):
    # Create item
    item = models.Item(url="http://example.com/8", name="Test Item 8")
    db.add(item)
    await db.commit()

    # Create history: In Stock -> Out -> In
    # timestamps: NOW-2h, NOW-1h, NOW
    now = datetime.now()

    # 1. In Stock (2 hours ago)
    ph1 = models.PriceHistory(item_id=item.id, price=100.0, timestamp=now - timedelta(hours=2), in_stock=True)
    db.add(ph1)

    # 2. Out of Stock (1 hour ago) -> Should trigger "Stock Depleted"
    ph2 = models.PriceHistory(item_id=item.id, price=100.0, timestamp=now - timedelta(hours=1), in_stock=False)
    db.add(ph2)

    # 3. In Stock (Now) -> Should trigger "Back in Stock"
    ph3 = models.PriceHistory(item_id=item.id, price=100.0, timestamp=now, in_stock=True)
    db.add(ph3)

    await db.commit()

    data = await ItemService.get_analytics_data(db, item.id)
    annotations = data["annotations"]

    stock_notes = [a for a in annotations if "stock" in a["type"]]
    assert len(stock_notes) == 2

    # Sort chronologically
    stock_notes.sort(key=lambda x: x["timestamp"])

    assert stock_notes[0]["type"] == "stock_depleted"
    assert stock_notes[0]["label"] == "Stock Depleted"

    assert stock_notes[1]["type"] == "stock_restocked"
    assert stock_notes[1]["label"] == "Back in Stock"
