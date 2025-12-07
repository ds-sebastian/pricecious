from datetime import UTC, datetime, timedelta

import pytest

from app import models, schemas
from app.services.item_service import ItemService


@pytest.mark.asyncio
async def test_history_sync_on_delete_and_update(db):
    # 1. Create Item
    item_create = schemas.ItemCreate(url="http://example.com", name="Sync Test Item", current_price=10.0, in_stock=True)
    item = await ItemService.create_item(db, item_create)
    assert item.current_price == 10.0

    # 2. Manually insert two history records
    # Older record
    h1 = models.PriceHistory(
        item_id=item.id,
        price=10.0,
        in_stock=True,
        timestamp=datetime.now(UTC) - timedelta(hours=1),
    )
    # Newer record
    h2 = models.PriceHistory(
        item_id=item.id,
        price=20.0,  # Price changed
        in_stock=False,  # Stock changed
        timestamp=datetime.now(UTC),
    )
    db.add_all([h1, h2])
    await db.commit()
    await db.refresh(h1)
    await db.refresh(h2)

    # Note: creating history doesn't auto-update item in this test setup unless we call logic,
    # but let's assume the item was updated to the latest "h2" value either by scraper or manual set.
    # For this test, we force the item to match h2 to simulate "latest state"
    item.current_price = 20.0
    item.in_stock = False
    await db.commit()

    # 3. Delete the latest record (h2)
    await ItemService.delete_history(db, h2.id)

    # 4. Verify item reverted to h1's data
    await db.refresh(item)
    assert item.current_price == 10.0
    assert item.in_stock

    # 5. Update the remaining record (h1)
    update = schemas.PriceHistoryUpdate(price=15.0, in_stock=True)
    await ItemService.update_history(db, h1.id, update)

    # 6. Verify item reflects the update
    await db.refresh(item)
    assert item.current_price == 15.0

    # 7. Delete the last record (h1)
    await ItemService.delete_history(db, h1.id)

    # 8. Verify item data is cleared
    await db.refresh(item)
    assert item.current_price is None
    assert item.in_stock is None
