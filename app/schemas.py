from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, field_validator


def _ensure_utc(v):
    """Add UTC timezone to naive datetimes."""
    return v.replace(tzinfo=UTC) if isinstance(v, datetime) and v.tzinfo is None else v


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
    _normalize_tz = field_validator("last_checked", "next_check", mode="before")(_ensure_utc)


class SettingsUpdate(BaseModel):
    key: str
    value: str


class PriceHistoryUpdate(BaseModel):
    price: float | None = None
    in_stock: bool | None = None


class PriceHistoryResponse(BaseModel):
    id: int
    price: float
    timestamp: datetime
    screenshot_path: str | None = None
    price_confidence: float | None = None
    in_stock_confidence: float | None = None
    in_stock: bool | None = None
    model_config = ConfigDict(from_attributes=True)
    _normalize_tz = field_validator("timestamp", mode="before")(_ensure_utc)


class PriceForecastResponse(BaseModel):
    id: int
    forecast_date: datetime
    predicted_price: float
    yhat_lower: float
    yhat_upper: float
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
    _normalize_tz = field_validator("forecast_date", "created_at", mode="before")(_ensure_utc)


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
    forecast: list[PriceForecastResponse] | None = None


class HistoryFilter(BaseModel):
    page: int = 1
    size: int = 50
    sort: str = "desc"
    min_price: float | None = None
    max_price: float | None = None
    in_stock: bool | None = None
    min_confidence: float | None = None


class PriceHistoryPaginatedResponse(BaseModel):
    items: list[PriceHistoryResponse]
    total: int
    page: int
    size: int
