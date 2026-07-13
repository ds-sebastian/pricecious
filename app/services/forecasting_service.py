import asyncio
import logging

import pandas as pd
from prophet import Prophet
from sqlalchemy import delete, select

from app import database
from app.models import PriceForecast, PriceHistory
from app.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

BLACK_FRIDAY_MONTH = 11
BLACK_FRIDAY_START_DAY = 20
BLACK_FRIDAY_END_DAY = 30
MIN_HISTORY_FOR_FORECAST = 14
MIN_HISTORY_FOR_YEARLY_SEASONALITY = 500
HORIZON_CAP_RATIO = 10


class ForecastingService:
    @staticmethod
    def _is_black_friday_week(ds):
        """
        Check if the date is within Black Friday week (late Nov).
        Simple heuristic: Nov 20-30.
        """
        date = pd.to_datetime(ds)
        return (
            1
            if (date.month == BLACK_FRIDAY_MONTH and BLACK_FRIDAY_START_DAY <= date.day <= BLACK_FRIDAY_END_DAY)
            else 0
        )

    @staticmethod
    def _run_prophet(df: pd.DataFrame, days: int, item_id: int):
        """Fit and predict synchronously; callers must run this off the event loop."""
        duration_days = (df["ds"].max() - df["ds"].min()).days
        prediction_days = min(days, max(1, duration_days // HORIZON_CAP_RATIO))
        df["black_friday"] = df["ds"].apply(ForecastingService._is_black_friday_week)
        use_bf_regressor = df["black_friday"].any() and (df["black_friday"] == 0).any()
        model = Prophet(
            seasonality_mode="multiplicative",
            changepoint_prior_scale=0.01,
            seasonality_prior_scale=1.0,
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=duration_days >= MIN_HISTORY_FOR_YEARLY_SEASONALITY,
        )
        if use_bf_regressor:
            model.add_regressor("black_friday")
        try:
            model.fit(df)
        except Exception as exc:
            logger.error(f"Prophet fit failed for item {item_id}: {exc}")
            return None

        future = model.make_future_dataframe(periods=prediction_days)
        if use_bf_regressor:
            future["black_friday"] = future["ds"].apply(ForecastingService._is_black_friday_week)
        forecast = model.predict(future)
        return forecast[forecast["ds"] > df["ds"].max()]

    @staticmethod
    async def generate_forecast(item_id: int, days: int = 30):
        """
        Generate and persist price forecast for an item.
        """
        async with database.AsyncSessionLocal() as session:
            result = await session.execute(
                select(PriceHistory).where(PriceHistory.item_id == item_id).order_by(PriceHistory.timestamp)
            )
            history = result.scalars().all()

        if len(history) < MIN_HISTORY_FOR_FORECAST:
            logger.info(f"Not enough data to forecast for item {item_id} (found {len(history)} records)")
            return

        df = pd.DataFrame([{"ds": h.timestamp, "y": h.price} for h in history])
        df["ds"] = df["ds"].dt.tz_localize(None)
        future_forecast = await asyncio.to_thread(ForecastingService._run_prophet, df, days, item_id)
        if future_forecast is None:
            return

        async with database.AsyncSessionLocal() as session:
            await session.execute(delete(PriceForecast).where(PriceForecast.item_id == item_id))
            new_forecasts = [
                PriceForecast(
                    item_id=item_id,
                    forecast_date=row["ds"],
                    predicted_price=max(0, row["yhat"]),
                    yhat_lower=max(0, row["yhat_lower"]),
                    yhat_upper=max(0, row["yhat_upper"]),
                )
                for _, row in future_forecast.iterrows()
            ]

            session.add_all(new_forecasts)
            await session.commit()
        AnalyticsService.invalidate_item(item_id)
        logger.info(f"Generated {len(new_forecasts)} forecast points for item {item_id}")
