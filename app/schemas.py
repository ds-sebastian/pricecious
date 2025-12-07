from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationProfileCreate(BaseModel):
    name: str
    apprise_url: str
    notify_on_price_drop: bool = True
    notify_on_target_price: bool = True
    price_drop_threshold_percent: float = 10.0
    notify_on_stock_change: bool = True
    check_interval_minutes: int = 60


class NotificationProfileUpdate(NotificationProfileCreate):
    pass


class NotificationProfileResponse(NotificationProfileCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ItemCreate(BaseModel):
    url: str
    name: str
    selector: str | None = None
    target_price: float | None = None
    check_interval_minutes: int | None = None
    tags: str | None = None
    description: str | None = None
    custom_prompt: str | None = None
    notification_profile_id: int | None = None
    current_price: float | None = None
    in_stock: bool | None = None


class ItemResponse(ItemCreate):
    id: int
    current_price: float | None
    in_stock: bool | None
    current_price_confidence: float | None = None
    in_stock_confidence: float | None = None
    is_active: bool
    last_checked: datetime | None
    is_refreshing: bool = False
    last_error: str | None = None
    screenshot_url: str | None = None
    next_check: datetime | None = None
    interval: int | None = None
    model_config = ConfigDict(from_attributes=True)


class SettingsUpdate(BaseModel):
    key: str
    value: str


class PriceHistoryResponse(BaseModel):
    id: int
    price: float
    timestamp: datetime
    screenshot_path: str | None = None
    price_confidence: float | None = None
    in_stock_confidence: float | None = None
    in_stock: bool | None = None
    model_config = ConfigDict(from_attributes=True)


class ItemStats(BaseModel):
    min_price: float
    max_price: float
    avg_price: float
    std_dev: float
    latest_price: float
    price_change_24h: float | None = None


class AnalyticsResponse(BaseModel):
    item_id: int
    item_name: str
    stats: ItemStats
    history: list[PriceHistoryResponse]
