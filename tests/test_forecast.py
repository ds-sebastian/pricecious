from datetime import datetime, timedelta

from sqlalchemy import select

from app import forecast
from app.models import Item, PriceForecast, PriceHistory


async def test_forecast_item_replaces_previous_forecast(db):
    item = Item(url="https://example.com", name="Widget")
    db.add(item)
    await db.flush()
    start = datetime(2025, 1, 1)
    db.add_all(PriceHistory(item_id=item.id, timestamp=start + timedelta(days=d), price=100 + d % 5) for d in range(60))
    db.add(PriceForecast(item_id=item.id, forecast_date=start, predicted_price=1, yhat_lower=1, yhat_upper=1))
    await db.commit()

    await forecast.forecast_item(item.id)

    rows = (await db.scalars(select(PriceForecast).order_by(PriceForecast.forecast_date))).all()
    assert len(rows) == 5  # horizon is capped at a tenth of the 59-day history span
    assert rows[0].forecast_date > start + timedelta(days=59)
    assert all(row.yhat_lower <= row.predicted_price <= row.yhat_upper for row in rows)


async def test_short_history_is_not_forecast(db):
    item = Item(url="https://example.com", name="Widget")
    db.add(item)
    await db.flush()
    db.add(PriceHistory(item_id=item.id, price=1))
    await db.commit()

    await forecast.forecast_item(item.id)

    assert (await db.scalars(select(PriceForecast))).all() == []
