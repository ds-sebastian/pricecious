import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from fastapi import HTTPException
from sqlalchemy import Integer, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.expression import cast

from app import database, models, schemas
from app.services.settings_service import SettingsService
from app.url_validation import URLValidationError, validate_url

logger = logging.getLogger(__name__)


class ItemService:
    @staticmethod
    async def get_items(db: AsyncSession):
        stmt = select(models.Item).options(selectinload(models.Item.notification_profile))
        result = await db.execute(stmt)
        items = result.scalars().all()

        global_interval_str = await SettingsService.get_setting_value(db, "refresh_interval_minutes", "60")
        global_interval = int(global_interval_str)

        result_list = []
        for item in items:
            # Determine interval (Effective Interval Logic)
            interval = item.check_interval_minutes
            if not interval and item.notification_profile:
                interval = item.notification_profile.check_interval_minutes
            interval = max(interval or global_interval, 5)

            # Display logic: Keep it aware or naive?
            # If we want to display next_check, it's safer to keep it consistent.
            # But the failure was in SQL.
            next_check = None
            if item.last_checked:
                # Treat DB value as UTC
                last_checked = item.last_checked.replace(tzinfo=UTC)
                next_check = last_checked + timedelta(minutes=interval)

            item_dict = {k: v for k, v in item.__dict__.items() if not k.startswith("_sa_")}

            result_list.append(
                {
                    **item_dict,
                    "screenshot_url": f"/screenshots/item_{item.id}.png",
                    "next_check": next_check,
                    "interval": interval,
                }
            )

        return result_list

    @staticmethod
    async def create_item(db: AsyncSession, item: schemas.ItemCreate):
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
    async def update_item(db: AsyncSession, item_id: int, item_update: schemas.ItemCreate):
        stmt = select(models.Item).where(models.Item.id == item_id)
        result = await db.execute(stmt)
        db_item = result.scalars().first()

        if not db_item:
            raise HTTPException(status_code=404, detail="Item not found")

        for key, value in item_update.model_dump().items():
            setattr(db_item, key, value)

        await db.commit()
        await db.refresh(db_item)
        return db_item

    @staticmethod
    async def delete_item(db: AsyncSession, item_id: int):
        stmt = select(models.Item).where(models.Item.id == item_id)
        result = await db.execute(stmt)
        item = result.scalars().first()

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        # Clean up screenshot if it exists (best effort)
        screenshot_path = f"screenshots/item_{item_id}.png"
        if os.path.exists(screenshot_path):
            try:
                os.remove(screenshot_path)
            except OSError:
                pass

        await db.delete(item)
        await db.commit()
        return {"ok": True}

    @staticmethod
    async def get_item(db: AsyncSession, item_id: int):
        stmt = select(models.Item).where(models.Item.id == item_id)
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_item_data_for_checking(db: AsyncSession, item_id: int):
        stmt = (
            select(models.Item).options(selectinload(models.Item.notification_profile)).where(models.Item.id == item_id)
        )
        result = await db.execute(stmt)
        item = result.scalars().first()

        if not item:
            return None, None

        stmt_settings = select(models.Settings)
        result_settings = await db.execute(stmt_settings)
        settings_list = result_settings.scalars().all()
        settings = {s.key: s.value for s in settings_list}

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

        # Parse settings with defaults
        smart_scroll = settings.get("smart_scroll_enabled", "false").lower() == "true"
        text_context = settings.get("text_context_enabled", "false").lower() == "true"

        config = {
            "smart_scroll": smart_scroll,
            "smart_scroll_pixels": int(settings.get("smart_scroll_pixels", "350")),
            "text_length": int(settings.get("text_context_length", "5000")) if text_context else 0,
            "scraper_timeout": int(settings.get("scraper_timeout", "90000")),
        }
        return item_data, config

    @staticmethod
    async def get_due_items():
        """Get items due for refresh. Creates and manages its own session."""
        async with database.AsyncSessionLocal() as db:
            global_int_str = await SettingsService.get_setting_value(db, "refresh_interval_minutes", "60")
            global_int = int(global_int_str)
            now = datetime.now(UTC)

            # Join with NotificationProfile to access its check_interval
            # Logic:
            # 1. Item has specific interval -> use it
            # 2. Item has no interval, Profile has interval -> use it
            # 3. Neither -> use global
            # Calc 'due_threshold' for each: last_checked < now - interval

            # Using coalesce(item.int, profile.int, global) is the check_interval.
            # We want: last_checked < now - interval MINUTES
            # Since SQLAlchemy interval math varies, we can use a hybrid approach or simpler filtering.

            # Efficient Approach:
            # Select IDs, last_checked, and the determined interval components.
            # Filtering fully in SQL is better but requires DB-specific date math.
            # We will fetch only candidates that MIGHT be due (last_checked < now - 5 min)
            # and verify precise interval in python, avoiding full table scan.

            # items with NO last_checked are due immediately
            # items active only

            stmt = (
                select(models.Item)
                .options(selectinload(models.Item.notification_profile))
                .where(models.Item.is_active == True)  # noqa
            )

            result = await db.execute(stmt)
            items = result.scalars().all()

            due_items = []

            for item in items:
                if item.is_refreshing:
                    continue

                # Effective Interval
                interval = item.check_interval_minutes
                if not interval and item.notification_profile:
                    interval = item.notification_profile.check_interval_minutes
                interval = max(interval or global_int, 5)

                if not item.last_checked:
                    logger.info(f"Item {item.id} due: Never checked (Interval: {interval}m)")
                    due_items.append((item.id, interval, -1))
                    continue

                # Check time
                # Ensure UTC awareness for calculation
                last_checked = item.last_checked
                if last_checked.tzinfo is None:
                    last_checked = last_checked.replace(tzinfo=UTC)

                time_since = (now - last_checked).total_seconds() / 60

                if time_since >= interval:
                    logger.info(f"Item {item.id} due: Last checked {time_since:.1f}m ago (Interval: {interval}m)")
                    due_items.append((item.id, interval, int(time_since)))

            return due_items

    _analytics_cache: ClassVar[dict[tuple, tuple[dict[str, Any], datetime]]] = {}
    CACHE_TTL_SECONDS = 300

    @staticmethod
    def clear_cache():
        ItemService._analytics_cache.clear()

    @staticmethod
    async def get_analytics_data(
        db: AsyncSession, item_id: int, std_dev_threshold: float | None = None, days_back: int | None = None
    ):
        # 1. Check Cache
        cached = ItemService._get_cached_analytics(item_id, std_dev_threshold, days_back)
        if cached:
            return cached

        stmt = select(models.Item).where(models.Item.id == item_id)
        result = await db.execute(stmt)
        item = result.scalars().first()

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        # Base Filters
        filters = [models.PriceHistory.item_id == item_id]
        if days_back:
            # Use NAIVE UTC for DB query
            search_start_date = (datetime.now(UTC) - timedelta(days=days_back)).replace(tzinfo=None)
            filters.append(models.PriceHistory.timestamp >= search_start_date)

        # 2. Calculate Stats (SQL)
        stats = await ItemService._calculate_analytics_stats_sql(db, item, filters)
        if not stats:
            return ItemService._empty_analytics_response(item)

        # 3. Annotations
        annotations = []
        annotations.extend(await ItemService._generate_min_max_annotations(db, stats, filters))
        annotations.extend(await ItemService._generate_stock_annotations(db, filters))

        # Limit annotations to prevent accumulation?
        # For now, let's keep all within the window as it's useful info.

        # 4. Aggregation Query
        final_history = await ItemService._fetch_aggregated_history_sql(db, item_id, filters, stats, std_dev_threshold)

        result = {
            "item_id": item.id,
            "item_name": item.name,
            "stats": stats,
            "history": final_history,
            "annotations": annotations,
        }

        # Save to Cache
        cache_key = (item_id, std_dev_threshold, days_back)
        ItemService._analytics_cache[cache_key] = (result, datetime.now())

        return result

    @staticmethod
    async def _generate_min_max_annotations(db: AsyncSession, stats: dict, filters: list) -> list[dict]:
        annotations = []
        # Min Price Annotation
        if stats["min_price"] > 0:
            stmt_min = (
                select(models.PriceHistory)
                .filter(*filters, models.PriceHistory.price == stats["min_price"])
                .order_by(models.PriceHistory.timestamp.asc())  # First occurrence
                .limit(1)
            )
            result_min = await db.execute(stmt_min)
            min_record = result_min.scalars().first()

            if min_record:
                annotations.append(
                    {
                        "type": "min",
                        "value": min_record.price,
                        "timestamp": min_record.timestamp,
                        "label": f"Lowest: ${min_record.price:.2f}",
                    }
                )

        # Max Price Annotation
        if stats["max_price"] > 0 and stats["max_price"] != stats["min_price"]:
            stmt_max = (
                select(models.PriceHistory)
                .filter(*filters, models.PriceHistory.price == stats["max_price"])
                .order_by(models.PriceHistory.timestamp.asc())  # First occurrence
                .limit(1)
            )
            result_max = await db.execute(stmt_max)
            max_record = result_max.scalars().first()

            if max_record:
                annotations.append(
                    {
                        "type": "max",
                        "value": max_record.price,
                        "timestamp": max_record.timestamp,
                        "label": f"Highest: ${max_record.price:.2f}",
                    }
                )
        return annotations

    @staticmethod
    async def _generate_stock_annotations(db: AsyncSession, filters: list) -> list[dict]:
        # Optimization: Fetch ONLY necessary columns
        stmt = (
            select(models.PriceHistory.timestamp, models.PriceHistory.in_stock, models.PriceHistory.price)
            .filter(*filters)
            .order_by(models.PriceHistory.timestamp.asc())
        )
        # Further optimization potential: Use SQL window functions to find edges
        # But reducing payload is a good first step.
        result = await db.execute(stmt)
        # Using a generator/iteration to avoid loading all into list if possible, but driver might load all.
        stock_history = result.all()

        annotations = []
        last_status = None

        for timestamp, in_stock, price in stock_history:
            if in_stock is None:
                continue

            if last_status is not None and in_stock != last_status:
                annotations.append(
                    {
                        "type": "stock_depleted" if not in_stock else "stock_restocked",
                        "value": price,
                        "timestamp": timestamp,
                        "label": "Stock Depleted" if not in_stock else "Back in Stock",
                    }
                )
            last_status = in_stock

        return annotations

    @staticmethod
    def _get_cached_analytics(item_id, std_dev_threshold, days_back):
        cache_key = (item_id, std_dev_threshold, days_back)
        if cache_key in ItemService._analytics_cache:
            cached_data, timestamp = ItemService._analytics_cache[cache_key]
            if (datetime.now() - timestamp).total_seconds() < ItemService.CACHE_TTL_SECONDS:
                return cached_data
            else:
                del ItemService._analytics_cache[cache_key]
        return None

    @staticmethod
    async def _calculate_analytics_stats_sql(db: AsyncSession, item: models.Item, filters: list):
        # We need: Min, Max, Avg, StdDev (approx), Count, StartTime, EndTime
        stats_query = select(
            func.count(models.PriceHistory.id).label("count"),
            func.min(models.PriceHistory.price).label("min_price"),
            func.max(models.PriceHistory.price).label("max_price"),
            func.avg(models.PriceHistory.price).label("avg_price"),
            func.sum(models.PriceHistory.price * models.PriceHistory.price).label("sum_sq"),
            func.min(models.PriceHistory.timestamp).label("start_time"),
            func.max(models.PriceHistory.timestamp).label("end_time"),
        ).filter(*filters)

        stats_result_exec = await db.execute(stats_query)
        stats_result = stats_result_exec.one_or_none()

        if not stats_result or stats_result.count == 0:
            return None

        count = stats_result.count
        avg_price = float(stats_result.avg_price or 0)
        sum_sq = float(stats_result.sum_sq or 0)

        # Std Dev Calc
        std_dev = 0.0
        if count > 1:
            try:
                variance = (sum_sq / count) - (avg_price**2)
                if variance > 0:
                    std_dev = variance**0.5
            except Exception:
                pass

        # Combine Latest & 24h Change Queries
        # Use NAIVE UTC for DB query
        yesterday = (datetime.now(UTC) - timedelta(days=1)).replace(tzinfo=None)

        # Fetch latest and one approx 24h ago
        # We can do this in two small queries (efficient enough) or one union.
        # Let's keep distinct queries but clean up.

        latest_record_query = (
            select(models.PriceHistory.price)
            .filter(models.PriceHistory.item_id == item.id)
            .order_by(models.PriceHistory.timestamp.desc())
            .limit(1)
        )
        latest_price = (await db.execute(latest_record_query)).scalar_one_or_none() or 0.0

        price_24h_query = (
            select(models.PriceHistory.price)
            .filter(models.PriceHistory.item_id == item.id, models.PriceHistory.timestamp <= yesterday)
            .order_by(models.PriceHistory.timestamp.desc())
            .limit(1)
        )
        price_24h = (await db.execute(price_24h_query)).scalar_one_or_none()

        price_change = 0.0
        if price_24h:
            price_change = ((latest_price - price_24h) / price_24h) * 100

        return {
            "min_price": float(stats_result.min_price or 0),
            "max_price": float(stats_result.max_price or 0),
            "avg_price": round(avg_price, 2),
            "std_dev": round(std_dev, 2),
            "latest_price": latest_price,
            "price_change_24h": round(price_change, 2),
            "_start_time": stats_result.start_time,
            "_end_time": stats_result.end_time,
            "_std_dev_raw": std_dev,
        }

    @staticmethod
    async def _fetch_aggregated_history_sql(
        db: AsyncSession, item_id: int, filters: list, stats: dict, std_dev_threshold: float | None
    ):
        target_points = 150
        # These come from DB so they are naive (but represent UTC).
        start_time = stats.get("_start_time") or datetime.now(UTC).replace(tzinfo=None)
        end_time = stats.get("_end_time") or datetime.now(UTC).replace(tzinfo=None)

        duration_seconds = (end_time - start_time).total_seconds()

        if duration_seconds <= 0:
            step_seconds = 60
        else:
            step_seconds = duration_seconds / target_points
            step_seconds = max(step_seconds, 60)

        agg_filters = filters.copy()
        std_dev = stats.get("_std_dev_raw", 0.0)
        avg_price = stats.get("avg_price", 0.0)

        if std_dev_threshold and std_dev > 0:
            lower_bound = avg_price - (std_dev_threshold * std_dev)
            upper_bound = avg_price + (std_dev_threshold * std_dev)
            agg_filters.append(models.PriceHistory.price >= lower_bound)
            agg_filters.append(models.PriceHistory.price <= upper_bound)

        # Determine dialect from connection
        # async engine bind dialect
        dialect_name = db.bind.dialect.name
        is_sqlite = dialect_name == "sqlite"

        if is_sqlite:
            epoch_col = cast(func.strftime("%s", models.PriceHistory.timestamp), Integer)
        else:
            epoch_col = extract("epoch", models.PriceHistory.timestamp)

        start_ts_epoch = start_time.timestamp()
        bucket_expr = cast((epoch_col - start_ts_epoch) / step_seconds, Integer)

        agg_query = (
            select(
                func.avg(models.PriceHistory.price).label("price"),
                func.min(models.PriceHistory.timestamp).label("timestamp"),
                func.max(cast(models.PriceHistory.in_stock, Integer)).label("in_stock"),
            )
            .filter(*agg_filters)
            .group_by(bucket_expr)
            .order_by(func.min(models.PriceHistory.timestamp))
        )

        agg_results_exec = await db.execute(agg_query)
        agg_results = agg_results_exec.all()

        return [
            models.PriceHistory(
                id=0,
                item_id=item_id,
                price=r.price,
                timestamp=r.timestamp,
                in_stock=bool(r.in_stock) if r.in_stock is not None else None,
            )
            for r in agg_results
        ]

    @staticmethod
    def _empty_analytics_response(item):
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
