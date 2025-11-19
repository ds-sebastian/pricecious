from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class NotificationProfile(Base):
    __tablename__ = "notification_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    apprise_url = Column(String)
    notify_on_price_drop = Column(Boolean, default=True)
    notify_on_target_price = Column(Boolean, default=True)
    price_drop_threshold_percent = Column(Float, default=10.0)
    notify_on_stock_change = Column(Boolean, default=True)
    check_interval_minutes = Column(Integer, default=60)

    items = relationship("Item", back_populates="notification_profile")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, index=True)
    name = Column(String)
    selector = Column(String, nullable=True)
    target_price = Column(Float, nullable=True)
    check_interval_minutes = Column(Integer, default=60)

    # New fields
    current_price = Column(Float, nullable=True)
    in_stock = Column(Boolean, nullable=True)
    tags = Column(String, nullable=True)  # Comma separated
    description = Column(String, nullable=True)

    is_active = Column(Boolean, default=True)
    last_checked = Column(DateTime, nullable=True)
    is_refreshing = Column(Boolean, default=False)
    last_error = Column(String, nullable=True)

    notification_profile_id = Column(Integer, ForeignKey("notification_profiles.id"), nullable=True)
    notification_profile = relationship("NotificationProfile", back_populates="items")

    price_history = relationship("PriceHistory", back_populates="item", cascade="all, delete-orphan")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    price = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    screenshot_path = Column(String, nullable=True)

    item = relationship("Item", back_populates="price_history")


class Settings(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(Text)
