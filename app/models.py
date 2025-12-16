from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .utils.datetime_utils import utc_now_naive


class NotificationProfile(Base):
    __tablename__ = "notification_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    apprise_url: Mapped[str] = mapped_column(String)
    notify_on_price_drop: Mapped[bool] = mapped_column(default=True)
    notify_on_target_price: Mapped[bool] = mapped_column(default=True)
    price_drop_threshold_percent: Mapped[float] = mapped_column(default=10.0)
    notify_on_stock_change: Mapped[bool] = mapped_column(default=True)
    check_interval_minutes: Mapped[int] = mapped_column(default=60)

    items: Mapped[list["Item"]] = relationship(back_populates="notification_profile")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    url: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    selector: Mapped[str | None] = mapped_column(String, nullable=True)
    target_price: Mapped[float | None] = mapped_column(nullable=True)
    check_interval_minutes: Mapped[int | None] = mapped_column(nullable=True, default=None)
    custom_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    # New fields
    current_price: Mapped[float | None] = mapped_column(nullable=True)
    in_stock: Mapped[bool | None] = mapped_column(nullable=True)
    tags: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    # Confidence scores for latest extraction
    current_price_confidence: Mapped[float | None] = mapped_column(nullable=True)
    in_stock_confidence: Mapped[float | None] = mapped_column(nullable=True)

    is_active: Mapped[bool] = mapped_column(default=True)
    last_checked: Mapped[datetime | None] = mapped_column(nullable=True)
    is_refreshing: Mapped[bool] = mapped_column(default=False)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)

    notification_profile_id: Mapped[int | None] = mapped_column(ForeignKey("notification_profiles.id"), nullable=True)
    notification_profile: Mapped["NotificationProfile | None"] = relationship(back_populates="items")

    price_history: Mapped[list["PriceHistory"]] = relationship(back_populates="item", cascade="all, delete-orphan")
    forecasts: Mapped[list["PriceForecast"]] = relationship(back_populates="item", cascade="all, delete-orphan")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    price: Mapped[float] = mapped_column()
    timestamp: Mapped[datetime] = mapped_column(default=utc_now_naive)
    screenshot_path: Mapped[str | None] = mapped_column(String, nullable=True)

    # Confidence scores and AI metadata
    price_confidence: Mapped[float | None] = mapped_column(nullable=True)
    in_stock_confidence: Mapped[float | None] = mapped_column(nullable=True)
    in_stock: Mapped[bool | None] = mapped_column(nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String, nullable=True)
    ai_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    repair_used: Mapped[bool | None] = mapped_column(nullable=True, default=False)

    item: Mapped["Item"] = relationship(back_populates="price_history")


class PriceForecast(Base):
    __tablename__ = "price_forecasts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    forecast_date: Mapped[datetime] = mapped_column()
    predicted_price: Mapped[float] = mapped_column()
    yhat_lower: Mapped[float] = mapped_column()
    yhat_upper: Mapped[float] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utc_now_naive)

    item: Mapped["Item"] = relationship(back_populates="forecasts")


class Settings(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    value: Mapped[str] = mapped_column(Text)
