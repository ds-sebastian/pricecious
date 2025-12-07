import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import database, models, schemas
from app.services.settings_service import SettingsService
from app.url_validation import URLValidationError, validate_url

logger = logging.getLogger(__name__)


class ItemService:
    _analytics_cache: ClassVar[dict[tuple, tuple[dict[str, Any], datetime]]] = {}
    CACHE_TTL_SECONDS = 300

    @staticmethod
    async def get_items(db: AsyncSession) -> list[dict]:
        """Fetch all items with computed next_check times."""
        result = await db.execute(select(models.Item).options(selectinload(models.Item.notification_profile)))
        items = result.scalars().all()

        global_interval = int(await SettingsService.get_setting_value(db, "refresh_interval_minutes", "60"))

        return [ItemService._enrich_item(item, global_interval) for item in items]

    @staticmethod
    def _enrich_item(item: models.Item, global_interval: int) -> dict:
        """Add computed fields to item dictionary."""
        profile_int = item.notification_profile.check_interval_minutes if item.notification_profile else None
        interval = ItemService._get_effective_interval(item.check_interval_minutes, profile_int, global_interval)

        next_check = None
        if item.last_checked:
            last_checked = item.last_checked.replace(tzinfo=UTC) if not item.last_checked.tzinfo else item.last_checked
            next_check = last_checked + timedelta(minutes=interval)

        # Efficient dict creation skipping sqlalchemy internal state
        data = {k: v for k, v in item.__dict__.items() if not k.startswith("_")}
        data.update(
            {
                "screenshot_url": f"/screenshots/item_{item.id}.png",
                "next_check": next_check,
                "interval": interval,
                # Ensure notification_profile is included if loaded, otherwise handle gracefully
                "notification_profile": item.notification_profile,
            }
        )
        return data

    @staticmethod
    async def create_item(db: AsyncSession, item: schemas.ItemCreate) -> models.Item:
        logger.info(f"Creating item: {item.name} - {item.url}")
        try:
            validate_url(item.url)
        except URLValidationError as e:
            raise HTTPException(status_code=400, detail=f"Invalid URL: {e}") from e

        db_item = models.Item(**item.model_dump())
        db.add(db_item)
        await db.commit()
        await db.refresh(db_item)
        return db_item

    @staticmethod
    async def update_item(db: AsyncSession, item_id: int, item_update: schemas.ItemCreate) -> models.Item:
        db_item = await db.get(models.Item, item_id)
        if not db_item:
            raise HTTPException(status_code=404, detail="Item not found")

        for key, value in item_update.model_dump().items():
            setattr(db_item, key, value)

        await db.commit()
        await db.refresh(db_item)
        return db_item

    @staticmethod
    async def delete_item(db: AsyncSession, item_id: int) -> dict[str, bool]:
        item = await db.get(models.Item, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        # Best effort screenshot cleanup
        try:
            path = f"screenshots/item_{item_id}.png"
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

        await db.delete(item)
        await db.commit()
        return {"ok": True}

    @staticmethod
    async def get_item(db: AsyncSession, item_id: int) -> models.Item | None:
        return await db.get(models.Item, item_id)

    @staticmethod
    async def get_item_data_for_checking(db: AsyncSession, item_id: int) -> tuple[dict | None, dict | None]:
        result = await db.execute(
            select(models.Item).options(selectinload(models.Item.notification_profile)).where(models.Item.id == item_id)
        )
        item = result.scalars().first()
        if not item:
            return None, None

        settings = await SettingsService.get_all_settings(db)

        # Parse settings
        smart_scroll = settings.get("smart_scroll_enabled", "false").lower() == "true"
        text_context = settings.get("text_context_enabled", "false").lower() == "true"

        config = {
            "smart_scroll": smart_scroll,
            "smart_scroll_pixels": int(settings.get("smart_scroll_pixels", "350")),
            "text_length": int(settings.get("text_context_length", "5000")) if text_context else 0,
            "scraper_timeout": int(settings.get("scraper_timeout", "90000")),
        }

        # Construct item dict manually to ensure flat structure/expected keys
        profile = item.notification_profile
        item_data = {
            "id": item.id,
            "url": item.url,
            "selector": item.selector,
            "name": item.name,
            "current_price": item.current_price,
            "in_stock": item.in_stock,
            "target_price": item.target_price,
            "custom_prompt": item.custom_prompt,
            "notification_profile": profile.__dict__ if profile else None,
        }

        return item_data, config

    @staticmethod
    def _get_effective_interval(item_int: int | None, profile_int: int | None, global_int: int) -> int:
        """Calculate effective check interval based on hierarchy: Item > Profile > Global."""
        return max((item_int or profile_int or global_int), 5)

    @staticmethod
    async def get_due_items() -> list[tuple[int, int, int]]:
        """
        Get items due for refresh.
        Returns list of (item_id, interval, overdue_minutes).
        """
        async with database.AsyncSessionLocal() as db:
            global_int = int(await SettingsService.get_setting_value(db, "refresh_interval_minutes", "60"))

            stmt = (
                select(
                    models.Item.id,
                    models.Item.check_interval_minutes,
                    models.Item.last_checked,
                    models.NotificationProfile.check_interval_minutes.label("profile_interval"),
                )
                .outerjoin(models.Item.notification_profile)
                .where(models.Item.is_active == True)  # noqa: E712
                .where(models.Item.is_refreshing == False)  # noqa: E712
            )

            rows = (await db.execute(stmt)).all()
            now = datetime.now(UTC)
            due_items = []

            for row in rows:
                interval = ItemService._get_effective_interval(
                    row.check_interval_minutes, row.profile_interval, global_int
                )

                if not row.last_checked:
                    due_items.append((row.id, interval, -1))
                    continue

                last_checked = row.last_checked.replace(tzinfo=UTC) if not row.last_checked.tzinfo else row.last_checked
                time_since = (now - last_checked).total_seconds() / 60

                if time_since >= interval:
                    due_items.append((row.id, interval, int(time_since)))

            return due_items

    @staticmethod
    async def get_analytics_data(
        db: AsyncSession, item_id: int, std_dev_threshold: float | None = None, days_back: int | None = None
    ) -> dict[str, Any]:
        """Get analytics data with caching."""
        cache_key = (item_id, std_dev_threshold, days_back)
        if cache_key in ItemService._analytics_cache:
            data, ts = ItemService._analytics_cache[cache_key]
            if (datetime.now() - ts).total_seconds() < ItemService.CACHE_TTL_SECONDS:
                return data
            del ItemService._analytics_cache[cache_key]

        item = await db.get(models.Item, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        # Build query filters
        filters = [models.PriceHistory.item_id == item_id]
        if days_back:
            start_date = (datetime.now(UTC) - timedelta(days=days_back)).replace(tzinfo=None)
            filters.append(models.PriceHistory.timestamp >= start_date)

        # Execute analytics
        stats = await ItemService._calculate_stats(db, item, filters)
        if not stats:
            return ItemService._empty_analytics(item)

        history = await ItemService._fetch_history(db, item_id, filters, stats, std_dev_threshold)
        annotations = await ItemService._get_annotations(db, stats, filters)

        result = {
            "item_id": item.id,
            "item_name": item.name,
            "stats": stats,
            "history": history,
            "annotations": annotations,
        }

        ItemService._analytics_cache[cache_key] = (result, datetime.now())
        return result

    @staticmethod
    def clear_cache():
        ItemService._analytics_cache.clear()

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

        # Calculate std_dev separately or in python if simpler/db-agnostic
        # For sqlite/postgres compatibility, better to do variance in python if dataset is small,
        # or use 2nd query. Let's do a simplified approach: fetch prices for variance if count < 1000?
        # Or just use the SQL way but gracefully handle errors.
        # Original code used a sum_sq approach which is efficient.

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

        # Grouping by time bucket.
        # Ideally we'd use a database specific date_trunc/strftime, but to keep it simple and portable:
        # Just fetch all (filtered) points and downsample in Python?
        # If history is huge, this is bad. Original code used SQL grouping which is better.
        # Let's use the original SQL grouping strategy but cleaned up.

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
        # optimize: only fetch stock and timestamp
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
