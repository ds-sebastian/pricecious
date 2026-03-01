import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import cachetools
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models

logger = logging.getLogger(__name__)


class AnalyticsService:
    _analytics_cache: cachetools.TTLCache = cachetools.TTLCache(maxsize=256, ttl=300)

    @staticmethod
    async def get_analytics_data(
        db: AsyncSession, item_id: int, std_dev_threshold: float | None = None, days_back: int | None = None
    ) -> dict[str, Any]:
        """Get analytics data with caching."""
        cache_key = (item_id, std_dev_threshold, days_back)
        if cache_key in AnalyticsService._analytics_cache:
            return AnalyticsService._analytics_cache[cache_key]

        item = await db.get(models.Item, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        # Build query filters
        filters = [models.PriceHistory.item_id == item_id]
        if days_back:
            start_date = (datetime.now(UTC) - timedelta(days=days_back)).replace(tzinfo=None)
            filters.append(models.PriceHistory.timestamp >= start_date)

        # Execute analytics
        stats = await AnalyticsService._calculate_stats(db, item, filters)
        if not stats:
            return AnalyticsService._empty_analytics(item)

        history = await AnalyticsService._fetch_history(db, item_id, filters, stats, std_dev_threshold)
        annotations = await AnalyticsService._get_annotations(db, stats, filters)

        # Fetch forecasts
        forecast_result = await db.execute(
            select(models.PriceForecast)
            .where(models.PriceForecast.item_id == item_id)
            .order_by(models.PriceForecast.forecast_date)
        )
        forecasts = forecast_result.scalars().all()

        result = {
            "item_id": item.id,
            "item_name": item.name,
            "stats": stats,
            "history": history,
            "annotations": annotations,
            "forecast": forecasts,
        }

        AnalyticsService._analytics_cache[cache_key] = result
        return result

    @staticmethod
    def clear_cache():
        AnalyticsService._analytics_cache.clear()

    @staticmethod
    async def _calculate_stats(db: AsyncSession, item: models.Item, filters: list) -> dict | None:
        """Calculate basic price statistics."""
        stmt = select(
            func.count(models.PriceHistory.id).label("count"),
            func.min(models.PriceHistory.price).label("min"),
            func.max(models.PriceHistory.price).label("max"),
            func.avg(models.PriceHistory.price).label("avg"),
            func.min(models.PriceHistory.timestamp).label("start"),
            func.max(models.PriceHistory.timestamp).label("end"),
        ).filter(*filters)

        res = (await db.execute(stmt)).one_or_none()
        if not res or not res.count:
            return None

        sum_sq_stmt = select(func.sum(models.PriceHistory.price * models.PriceHistory.price)).filter(*filters)
        sum_sq = (await db.execute(sum_sq_stmt)).scalar() or 0

        avg = float(res.avg or 0)
        count = res.count
        variance = (sum_sq / count) - (avg**2)
        std_dev = variance**0.5 if variance > 0 else 0

        # Latest price
        latest = (
            await db.execute(
                select(models.PriceHistory.price)
                .filter(models.PriceHistory.item_id == item.id)
                .order_by(models.PriceHistory.timestamp.desc())
                .limit(1)
            )
        ).scalar() or 0.0

        # 24h change
        yesterday_price = (
            await db.execute(
                select(models.PriceHistory.price)
                .filter(
                    models.PriceHistory.item_id == item.id,
                    models.PriceHistory.timestamp <= (datetime.now(UTC) - timedelta(days=1)).replace(tzinfo=None),
                )
                .order_by(models.PriceHistory.timestamp.desc())
                .limit(1)
            )
        ).scalar()

        change = ((latest - yesterday_price) / yesterday_price * 100) if yesterday_price else 0.0

        return {
            "min_price": float(res.min),
            "max_price": float(res.max),
            "avg_price": round(avg, 2),
            "std_dev": round(std_dev, 2),
            "_std_dev_raw": std_dev,
            "latest_price": latest,
            "price_change_24h": round(change, 2),
            "_start_time": res.start,
            "_end_time": res.end,
        }

    @staticmethod
    async def _fetch_history(
        db: AsyncSession, item_id: int, filters: list, stats: dict, std_dev_threshold: float | None
    ) -> list[models.PriceHistory]:
        """Fetch aggregated price history for charting."""
        # Add sigma clipping filter if requested
        query_filters = list(filters)
        if std_dev_threshold and stats["_std_dev_raw"] > 0:
            avg = stats["avg_price"]
            delta = std_dev_threshold * stats["_std_dev_raw"]
            query_filters.append(models.PriceHistory.price.between(avg - delta, avg + delta))

        # We want ~150 points.
        start, end = stats["_start_time"], stats["_end_time"]
        if not start or not end:
            return []

        duration = (end - start).total_seconds()
        step = max(duration / 150, 60)  # Min 1 minute step

        is_sqlite = db.bind.dialect.name == "sqlite"
        ts_col = models.PriceHistory.timestamp

        if is_sqlite:
            epoch = func.cast(func.strftime("%s", ts_col), models.Item.id.type)  # Use integer cast
        else:
            epoch = func.extract("epoch", ts_col)

        bucket = func.cast((epoch - start.timestamp()) / step, models.Item.id.type)

        rows = (
            await db.execute(
                select(
                    func.avg(models.PriceHistory.price).label("price"),
                    func.min(ts_col).label("ts"),
                    func.max(func.cast(models.PriceHistory.in_stock, models.Item.id.type)).label("stock"),
                )
                .filter(*query_filters)
                .group_by(bucket)
                .order_by(func.min(ts_col))
            )
        ).all()

        return [
            models.PriceHistory(
                id=0,  # Dummy ID
                item_id=item_id,
                price=r.price,
                timestamp=r.ts,
                in_stock=bool(r.stock) if r.stock is not None else None,
            )
            for r in rows
        ]

    @staticmethod
    async def _get_annotations(db: AsyncSession, stats: dict, filters: list) -> list[dict]:
        """Generate high/low and stock change annotations."""
        if stats["min_price"] == 0 and stats["max_price"] == 0:
            return []

        annotations = []

        # Min/Max queries
        for type_, val, label in [("min", stats["min_price"], "Lowest"), ("max", stats["max_price"], "Highest")]:
            if val <= 0:
                continue
            if type_ == "max" and val == stats["min_price"]:
                continue

            rec = (
                await db.execute(
                    select(models.PriceHistory)
                    .filter(*filters, models.PriceHistory.price == val)
                    .order_by(models.PriceHistory.timestamp.asc())
                    .limit(1)
                )
            ).scalar()

            if rec:
                annotations.append(
                    {
                        "type": type_,
                        "value": rec.price,
                        "timestamp": rec.timestamp,
                        "label": f"{label}: ${rec.price:.2f}",
                    }
                )

        # Stock changes
        rows = (
            await db.execute(
                select(models.PriceHistory.timestamp, models.PriceHistory.in_stock, models.PriceHistory.price)
                .filter(*filters)
                .order_by(models.PriceHistory.timestamp.asc())
            )
        ).all()

        last_stock = None
        for r in rows:
            if r.in_stock is None:
                continue
            if last_stock is not None and r.in_stock != last_stock:
                annotations.append(
                    {
                        "type": "stock_depleted" if not r.in_stock else "stock_restocked",
                        "value": r.price,
                        "timestamp": r.timestamp,
                        "label": "Stock Depleted" if not r.in_stock else "Back in Stock",
                    }
                )
            last_stock = r.in_stock

        return annotations

    @staticmethod
    def _empty_analytics(item: models.Item) -> dict:
        return {
            "item_id": item.id,
            "item_name": item.name,
            "stats": {
                "min_price": 0.0,
                "max_price": 0.0,
                "avg_price": 0.0,
                "std_dev": 0.0,
                "latest_price": item.current_price or 0.0,
                "price_change_24h": 0.0,
            },
            "history": [],
            "annotations": [],
        }
