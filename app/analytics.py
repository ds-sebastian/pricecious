from datetime import datetime, timedelta
from operator import attrgetter
from statistics import fmean, pstdev

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import utcnow
from app.models import Item, PriceForecast, PriceHistory

CHART_POINTS = 150
# "Lowest price seen" means little until an item has some history behind it.
LOW_MIN_HISTORY = timedelta(days=14)
LOW_WINDOW = timedelta(days=90)
by_price = attrgetter("price")


async def item_analytics(db: AsyncSession, item: Item, days: int | None, sigma: float | None) -> dict:
    query = select(PriceHistory.timestamp, PriceHistory.price, PriceHistory.in_stock).where(
        PriceHistory.item_id == item.id
    )
    if days:
        query = query.where(PriceHistory.timestamp >= utcnow() - timedelta(days=days))
    rows = (await db.execute(query.order_by(PriceHistory.timestamp))).all()
    forecast = (
        await db.scalars(
            select(PriceForecast).where(PriceForecast.item_id == item.id).order_by(PriceForecast.forecast_date)
        )
    ).all()

    result: dict = {
        "stats": None,
        "history": [],
        "annotations": [],
        "forecast": [
            {"timestamp": f.forecast_date, "price": f.predicted_price, "lower": f.yhat_lower, "upper": f.yhat_upper}
            for f in forecast
        ],
    }
    if not rows:
        return result

    prices = [row.price for row in rows]
    mean, std = fmean(prices), pstdev(prices)
    result["stats"] = {
        "latest": prices[-1],
        "min": min(prices),
        "max": max(prices),
        "avg": mean,
        "std_dev": std,
        "change_24h": _change_since(rows, utcnow() - timedelta(days=1)),
    }
    if sigma and std:
        rows = [row for row in rows if abs(row.price - mean) <= sigma * std]
    result["history"] = _downsample(rows)
    result["annotations"] = _annotations(rows)
    return result


def _change_since(rows: list, since: datetime) -> float | None:
    before = [row.price for row in rows if row.timestamp <= since]
    if not before or not before[-1]:
        return None
    return (rows[-1].price - before[-1]) / before[-1] * 100


def _downsample(rows: list) -> list[dict]:
    """Thin the history to about CHART_POINTS buckets, keeping each bucket's first, last, lowest and highest
    reading. Unlike averaging, this never plots a price that wasn't seen, and it keeps spikes and dips visible."""
    if not rows:
        return []
    start = rows[0].timestamp
    step = max((rows[-1].timestamp - start).total_seconds() / CHART_POINTS, 60)
    buckets: dict[int, list] = {}
    for row in rows:
        buckets.setdefault(int((row.timestamp - start).total_seconds() // step), []).append(row)
    kept: list = []
    for bucket in buckets.values():
        extremes = {bucket[0], min(bucket, key=by_price), max(bucket, key=by_price), bucket[-1]}
        kept.extend(sorted(extremes, key=attrgetter("timestamp")))
    return [{"timestamp": row.timestamp, "price": row.price, "in_stock": row.in_stock} for row in kept]


def _annotations(rows: list) -> list[dict]:
    if not rows:
        return []
    lowest = min(rows, key=by_price)
    highest = max(rows, key=by_price)
    notes = [{"type": "min", "timestamp": lowest.timestamp, "price": lowest.price}]
    if highest.price != lowest.price:
        notes.append({"type": "max", "timestamp": highest.timestamp, "price": highest.price})
    previous = None
    for row in rows:
        if row.in_stock is None:
            continue
        if previous is not None and row.in_stock != previous:
            kind = "restocked" if row.in_stock else "out_of_stock"
            notes.append({"type": kind, "timestamp": row.timestamp, "price": row.price})
        previous = row.in_stock
    return notes


def _trusted(threshold: float):
    """Readings confident enough to have been applied (or entered by hand); misreads mustn't set records."""
    return or_(PriceHistory.price_confidence.is_(None), PriceHistory.price_confidence >= threshold)


async def previous_low(db: AsyncSession, item_id: int, threshold: float) -> float | None:
    """The lowest trusted price so far, once the item has been tracked long enough for that to be meaningful."""
    low, first = (
        await db.execute(
            select(func.min(PriceHistory.price), func.min(PriceHistory.timestamp)).where(
                PriceHistory.item_id == item_id, _trusted(threshold)
            )
        )
    ).one()
    return low if low is not None and utcnow() - first >= LOW_MIN_HISTORY else None


async def deals(db: AsyncSession, items: list[Item], threshold: float) -> dict[int, str]:
    """Items whose current price is the lowest seen ("lowest_seen") or lowest in LOW_WINDOW ("lowest_90d").

    A price that has never been higher isn't a deal, so each needs a higher price in the same period.
    """
    if not items:
        return {}
    now = utcnow()
    cutoff = now - LOW_WINDOW
    recent = case((PriceHistory.timestamp >= cutoff, PriceHistory.price))
    rows = await db.execute(
        select(
            PriceHistory.item_id,
            func.min(PriceHistory.timestamp).label("first"),
            func.min(PriceHistory.price).label("low"),
            func.max(PriceHistory.price).label("high"),
            func.min(recent).label("recent_low"),
            func.max(recent).label("recent_high"),
        )
        .where(PriceHistory.item_id.in_([item.id for item in items]), _trusted(threshold))
        .group_by(PriceHistory.item_id)
    )
    current = {item.id: item.current_price for item in items}
    found = {}
    for row in rows:
        price = current[row.item_id]
        if price is None:
            continue
        if now - row.first >= LOW_MIN_HISTORY and price <= row.low < row.high:
            found[row.item_id] = "lowest_seen"
        elif row.first <= cutoff and row.recent_low is not None and price <= row.recent_low < row.recent_high:
            found[row.item_id] = "lowest_90d"
    return found
