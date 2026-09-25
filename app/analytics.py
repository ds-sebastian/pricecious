from datetime import datetime, timedelta
from operator import attrgetter
from statistics import fmean, pstdev

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import utcnow
from app.models import Item, PriceForecast, PriceHistory

CHART_POINTS = 150
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
