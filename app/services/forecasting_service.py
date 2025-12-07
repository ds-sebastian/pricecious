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

            # 3. Analyze Data Characteristics
            duration_days = (df["ds"].max() - df["ds"].min()).days

            # Horizon Capping (10:1 ratio)
            max_horizon = max(1, duration_days // HORIZON_CAP_RATIO)
            prediction_days = min(days, max_horizon)

            # Dynamic Seasonality
            use_yearly = duration_days >= MIN_HISTORY_FOR_YEARLY_SEASONALITY

            # Regressor Safety Check
            df["black_friday"] = df["ds"].apply(ForecastingService._is_black_friday_week)
            has_bf = df["black_friday"].sum() > 0
            has_non_bf = (df["black_friday"] == 0).sum() > 0
            use_bf_regressor = has_bf and has_non_bf

            m = Prophet(
                seasonality_mode="multiplicative",
                changepoint_prior_scale=0.01,
                seasonality_prior_scale=1.0,
                daily_seasonality=False,
                weekly_seasonality=True,
                yearly_seasonality=use_yearly,
            )

            if use_bf_regressor:
                m.add_regressor("black_friday")

            # 4. Fit & Predict
            try:
                m.fit(df)
            except Exception as e:
                logger.error(f"Prophet fit failed for item {item_id}: {e}")
                return

            future = m.make_future_dataframe(periods=prediction_days)
            if use_bf_regressor:
                future["black_friday"] = future["ds"].apply(ForecastingService._is_black_friday_week)
            else:
                # If regressor wasn't added to model, we don't need it in future df,
                # but Prophet might complain if we don't handle it consistently
                # if we had added it. Since we conditionally add_regressor,
                # we only need the column if we added it.
                # However, to be safe against any residual state (unlikely here),
                # we can skip adding the column to future if not used.
                pass

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
                        predicted_price=max(0, row["yhat"]),
                        yhat_lower=max(0, row["yhat_lower"]),
                        yhat_upper=max(0, row["yhat_upper"]),
                    )
                )

            session.add_all(new_forecasts)
            await session.commit()

            logger.info(f"Generated {len(new_forecasts)} forecast points for item {item_id}")
