import logging

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, schemas
from app.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)


class HistoryService:
    @staticmethod
    async def get_history_raw(
        db: AsyncSession, item_id: int, filters: schemas.HistoryFilter
    ) -> tuple[list[models.PriceHistory], int]:
        """Fetch raw history with filters."""
        offset = (filters.page - 1) * filters.size

        # Build base query
        base_filters = [models.PriceHistory.item_id == item_id]

        if filters.min_price is not None:
            base_filters.append(models.PriceHistory.price >= filters.min_price)
        if filters.max_price is not None:
            base_filters.append(models.PriceHistory.price <= filters.max_price)
        if filters.in_stock is not None:
            base_filters.append(models.PriceHistory.in_stock == filters.in_stock)
        if filters.min_confidence is not None:
            # Check both price and stock confidence
            base_filters.append(
                (models.PriceHistory.price_confidence >= filters.min_confidence)
                | (models.PriceHistory.price_confidence.is_(None))
            )

        # Count total
        count_stmt = select(func.count(models.PriceHistory.id)).filter(*base_filters)
        total = (await db.execute(count_stmt)).scalar() or 0

        # Fetch page
        order = models.PriceHistory.timestamp.asc() if filters.sort == "asc" else models.PriceHistory.timestamp.desc()
        stmt = select(models.PriceHistory).filter(*base_filters).order_by(order).offset(offset).limit(filters.size)
        items = (await db.execute(stmt)).scalars().all()

        return list(items), total

    @staticmethod
    async def update_history(
        db: AsyncSession, history_id: int, update: schemas.PriceHistoryUpdate
    ) -> models.PriceHistory:
        record = await db.get(models.PriceHistory, history_id)
        if not record:
            raise HTTPException(status_code=404, detail="History record not found")

        if update.price is not None:
            record.price = update.price
            record.repair_used = True  # Mark as manually repaired/modified

        if update.in_stock is not None:
            record.in_stock = update.in_stock
            record.repair_used = True

        await db.commit()
        await db.refresh(record)

        # Invalidate analytics cache
        AnalyticsService.clear_cache()

        # Sync latest data to item table
        await HistoryService._sync_item_latest_data(db, record.item_id)

        return record

    @staticmethod
    async def delete_history(db: AsyncSession, history_id: int) -> dict:
        record = await db.get(models.PriceHistory, history_id)
        if not record:
            raise HTTPException(status_code=404, detail="History record not found")

        item_id = record.item_id
        await db.delete(record)
        await db.commit()

        AnalyticsService.clear_cache()

        # Sync latest data to item table
        await HistoryService._sync_item_latest_data(db, item_id)

        return {"ok": True}

    @staticmethod
    async def _sync_item_latest_data(db: AsyncSession, item_id: int):
        """Sync the Item table's current_price and in_stock with the latest history record."""
        latest_history = (
            await db.execute(
                select(models.PriceHistory)
                .filter(models.PriceHistory.item_id == item_id)
                .order_by(models.PriceHistory.timestamp.desc())
                .limit(1)
            )
        ).scalar()

        item = await db.get(models.Item, item_id)
        if not item:
            return

        if latest_history:
            item.current_price = latest_history.price
            item.in_stock = latest_history.in_stock
            item.last_checked = latest_history.timestamp
        else:
            # No history left, reset fields
            item.current_price = None
            item.in_stock = None

        await db.commit()
        await db.refresh(item)
