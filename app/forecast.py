import asyncio
import logging

from sqlalchemy import delete, select

from app import database
from app.models import Item, PriceForecast, PriceHistory

logger = logging.getLogger(__name__)
logging.getLogger("prophet.plot").setLevel(logging.CRITICAL)  # warns that optional plotly is missing
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)

MIN_POINTS = 14
MIN_DAYS_FOR_YEARLY_SEASONALITY = 500
HORIZON_DAYS = 30
_lock = asyncio.Lock()


def _predict(timestamps: list, prices: list[float]) -> list[tuple]:
    """Fit Prophet and return (date, price, lower, upper) rows; CPU-bound, run in a thread."""
    import pandas as pd  # heavy imports, only needed here
    from prophet import Prophet

    df = pd.DataFrame({"ds": pd.to_datetime(timestamps), "y": prices})
    span_days = (df["ds"].max() - df["ds"].min()).days
    horizon = min(HORIZON_DAYS, max(1, span_days // 10))

    def black_friday(dates: pd.Series) -> pd.Series:
        return ((dates.dt.month == 11) & dates.dt.day.between(20, 30)).astype(int)

    df["black_friday"] = black_friday(df["ds"])
    use_black_friday = 0 < df["black_friday"].sum() < len(df)
    model = Prophet(
        seasonality_mode="multiplicative",
        changepoint_prior_scale=0.01,
        seasonality_prior_scale=1.0,
        daily_seasonality=False,
        weekly_seasonality=True,
        yearly_seasonality=span_days >= MIN_DAYS_FOR_YEARLY_SEASONALITY,
    )
    if use_black_friday:
        model.add_regressor("black_friday")
    model.fit(df)

    future = model.make_future_dataframe(periods=horizon)
    if use_black_friday:
        future["black_friday"] = black_friday(future["ds"])
    predicted = model.predict(future)
    predicted = predicted[predicted["ds"] > df["ds"].max()]
    return [
        (row.ds.to_pydatetime(), max(0.0, row.yhat), max(0.0, row.yhat_lower), max(0.0, row.yhat_upper))
        for row in predicted.itertuples()
    ]


async def forecast_item(item_id: int) -> None:
    async with database.SessionLocal() as db:
        rows = (
            await db.execute(
                select(PriceHistory.timestamp, PriceHistory.price)
                .where(PriceHistory.item_id == item_id)
                .order_by(PriceHistory.timestamp)
            )
        ).all()
    if len(rows) < MIN_POINTS:
        return

    predictions = await asyncio.to_thread(_predict, [r.timestamp for r in rows], [r.price for r in rows])
    async with database.SessionLocal() as db:
        await db.execute(delete(PriceForecast).where(PriceForecast.item_id == item_id))
        db.add_all(
            PriceForecast(item_id=item_id, forecast_date=date, predicted_price=price, yhat_lower=low, yhat_upper=high)
            for date, price, low, high in predictions
        )
        await db.commit()


def is_running() -> bool:
    return _lock.locked()


async def forecast_all() -> None:
    """Refresh forecasts for every active item, unless a run is already in progress."""
    if _lock.locked():
        return
    async with _lock:
        async with database.SessionLocal() as db:
            item_ids = (await db.scalars(select(Item.id).where(Item.is_active))).all()
        logger.info(f"Forecasting {len(item_ids)} items")
        for item_id in item_ids:  # sequential: Prophet is memory hungry
            try:
                await forecast_item(item_id)
            except Exception:
                logger.exception(f"Forecast failed for item {item_id}")
