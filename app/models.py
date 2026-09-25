from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow


class NotificationProfile(Base):
    __tablename__ = "notification_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, index=True)
    apprise_url: Mapped[str]
    notify_on_price_drop: Mapped[bool] = mapped_column(default=True)
    notify_on_target_price: Mapped[bool] = mapped_column(default=True)
    price_drop_threshold_percent: Mapped[float] = mapped_column(default=10.0)
    notify_on_stock_change: Mapped[bool] = mapped_column(default=True)
    notify_on_new_low: Mapped[bool] = mapped_column(default=True, server_default=false())
    check_interval_minutes: Mapped[int] = mapped_column(default=60)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(index=True)
    name: Mapped[str | None]  # None until the first check names it after the page title
    currency: Mapped[str | None] = mapped_column(String(3))  # ISO 4217; detected on the first check if not set
    selector: Mapped[str | None]
    target_price: Mapped[float | None]
    check_interval_minutes: Mapped[int | None]
    custom_prompt: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[str | None]
    description: Mapped[str | None]

    current_price: Mapped[float | None]  # the low end when the page shows a range
    current_price_confidence: Mapped[float | None]
    price_high: Mapped[float | None]
    regular_price: Mapped[float | None]  # the crossed-out "was" price
    promotion: Mapped[str | None]  # the store's sale label, e.g. "Limited Time Offer"
    in_stock: Mapped[bool | None]
    in_stock_confidence: Mapped[float | None]

    is_active: Mapped[bool] = mapped_column(default=True)
    last_checked: Mapped[datetime | None]
    is_refreshing: Mapped[bool] = mapped_column(default=False)
    refresh_started_at: Mapped[datetime | None]
    last_error: Mapped[str | None]
    error_type: Mapped[str | None]
    consecutive_failures: Mapped[int] = mapped_column(default=0, server_default="0")

    # Change detection: the AI is skipped while the page's prices and stock text match the last AI check.
    page_fingerprint: Mapped[str | None] = mapped_column(String(64))
    ai_checked_at: Mapped[datetime | None]
    ai_calls: Mapped[int] = mapped_column(default=0, server_default="0")
    ai_skips: Mapped[int] = mapped_column(default=0, server_default="0")

    notification_profile_id: Mapped[int | None] = mapped_column(ForeignKey("notification_profiles.id"))
    notification_profile: Mapped[NotificationProfile | None] = relationship(lazy="joined")


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (Index("ix_price_history_item_id_timestamp", "item_id", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    timestamp: Mapped[datetime] = mapped_column(default=utcnow)
    price: Mapped[float]
    price_confidence: Mapped[float | None]
    price_high: Mapped[float | None]
    regular_price: Mapped[float | None]
    promotion: Mapped[str | None]
    in_stock: Mapped[bool | None]
    in_stock_confidence: Mapped[float | None]
    ai_model: Mapped[str | None]
    ai_provider: Mapped[str | None]


class PriceForecast(Base):
    __tablename__ = "price_forecasts"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    forecast_date: Mapped[datetime]
    predicted_price: Mapped[float]
    yhat_lower: Mapped[float]
    yhat_upper: Mapped[float]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(Text)
