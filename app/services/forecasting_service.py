import logging

import pandas as pd
from prophet import Prophet
from sqlalchemy import delete, select

from app import database
from app.models import PriceForecast, PriceHistory

logger = logging.getLogger(__name__)

BLACK_FRIDAY_MONTH = 11
BLACK_FRIDAY_START_DAY = 20
BLACK_FRIDAY_END_DAY = 30
MIN_HISTORY_FOR_FORECAST = 5


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
    async def generate_forecast(item_id: int, days: int = 30):
        """
        Generate and persist price forecast for an item.
        """
        async with database.AsyncSessionLocal() as session:
            # 1. Fetch History
            result = await session.execute(
                select(PriceHistory).where(PriceHistory.item_id == item_id).order_by(PriceHistory.timestamp)
            )
            history = result.scalars().all()

            if len(history) < MIN_HISTORY_FOR_FORECAST:
                logger.info(f"Not enough data to forecast for item {item_id} (found {len(history)} records)")
                return

            # 2. Prepare Data
            df = pd.DataFrame(
                [
                    {
                        "ds": h.timestamp,
                        "y": h.price,
                    }
                    for h in history
                ]
            )

            # Remove time zone info to avoid Prophet warning
            df["ds"] = df["ds"].dt.tz_localize(None)

            # 3. Configure Prophet
            df["black_friday"] = df["ds"].apply(ForecastingService._is_black_friday_week)

            m = Prophet(seasonality_mode="multiplicative")
            m.add_regressor("black_friday")

            # 4. Fit & Predict
            try:
                m.fit(df)
            except Exception as e:
                logger.error(f"Prophet fit failed for item {item_id}: {e}")
                return

            future = m.make_future_dataframe(periods=days)
            future["black_friday"] = future["ds"].apply(ForecastingService._is_black_friday_week)

            forecast = m.predict(future)

            # Filter for future dates only
            last_date = df["ds"].max()
            future_forecast = forecast[forecast["ds"] > last_date]

            # 5. Persist
            # Delete old forecasts
            await session.execute(delete(PriceForecast).where(PriceForecast.item_id == item_id))

            new_forecasts = []
            for _, row in future_forecast.iterrows():
                new_forecasts.append(
                    PriceForecast(
                        item_id=item_id,
                        forecast_date=row["ds"],
                        predicted_price=row["yhat"],
                        yhat_lower=row["yhat_lower"],
                        yhat_upper=row["yhat_upper"],
                    )
                )

            session.add_all(new_forecasts)
            await session.commit()

            logger.info(f"Generated {len(new_forecasts)} forecast points for item {item_id}")
