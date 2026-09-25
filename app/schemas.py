from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_serializer,
    field_validator,
)

from app.notify import mask

# Timestamps are stored as naive UTC; label them so browsers don't read them as local time.
UTCDateTime = Annotated[datetime, AfterValidator(lambda v: v if v.tzinfo else v.replace(tzinfo=UTC))]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
OptionalText = Annotated[str | None, BeforeValidator(lambda v: (v.strip() or None) if isinstance(v, str) else v)]
Currency = Annotated[
    str | None,
    BeforeValidator(lambda v: (v.strip().upper() or None) if isinstance(v, str) else v),
    Field(pattern=r"^[A-Z]{3}$"),
]


class ItemIn(BaseModel):
    url: Text
    name: OptionalText = None  # named after the page title on the first check
    currency: Currency = None  # detected on the first check
    selector: OptionalText = None
    target_price: float | None = Field(None, ge=0)
    check_interval_minutes: int | None = Field(None, ge=5)
    tags: OptionalText = None
    description: OptionalText = None
    custom_prompt: OptionalText = None
    notification_profile_id: int | None = None
    current_price: float | None = Field(None, ge=0)
    in_stock: bool | None = None
    is_active: bool = True

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, tags: str | None) -> str | None:
        unique = dict.fromkeys(tag.strip() for tag in (tags or "").split(",") if tag.strip())
        return ", ".join(unique) or None


class ItemOut(BaseModel):
    id: int
    url: str
    name: str | None
    currency: str
    selector: str | None
    target_price: float | None
    check_interval_minutes: int | None
    tags: str | None
    description: str | None
    custom_prompt: str | None
    notification_profile_id: int | None
    current_price: float | None
    current_price_confidence: float | None
    in_stock: bool | None
    in_stock_confidence: float | None
    is_active: bool
    is_refreshing: bool
    last_checked: UTCDateTime | None
    last_error: str | None
    error_type: str | None
    consecutive_failures: int
    interval: int
    next_check: UTCDateTime | None
    screenshot_url: str | None
    deal: Literal["lowest_seen", "lowest_90d"] | None


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: UTCDateTime
    price: float
    price_confidence: float | None
    in_stock: bool | None
    in_stock_confidence: float | None


class HistoryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(1, ge=1)
    size: int = Field(50, ge=1, le=200)
    min_price: float | None = Field(None, ge=0)
    max_price: float | None = Field(None, ge=0)
    stock: Literal["in", "out", "unknown"] | None = None
    min_confidence: float | None = Field(None, ge=0, le=1)
    confidence_below: float | None = Field(None, gt=0, le=1)


class HistoryPage(BaseModel):
    items: list[HistoryOut]
    total: int
    page: int
    size: int


class HistoryUpdate(BaseModel):
    price: float | None = Field(None, ge=0)
    in_stock: bool | None = None


class Stats(BaseModel):
    latest: float
    min: float
    max: float
    avg: float
    std_dev: float
    change_24h: float | None


class ChartPoint(BaseModel):
    timestamp: UTCDateTime
    price: float
    in_stock: bool | None


class ForecastPoint(BaseModel):
    timestamp: UTCDateTime
    price: float
    lower: float
    upper: float


class Annotation(BaseModel):
    type: str
    timestamp: UTCDateTime
    price: float


class Analytics(BaseModel):
    stats: Stats | None
    history: list[ChartPoint]
    forecast: list[ForecastPoint]
    annotations: list[Annotation]


class ProfileIn(BaseModel):
    name: Text
    apprise_url: Text
    notify_on_price_drop: bool = True
    notify_on_target_price: bool = True
    price_drop_threshold_percent: float = Field(10.0, gt=0, le=100)
    notify_on_stock_change: bool = True
    notify_on_new_low: bool = True
    check_interval_minutes: int = Field(60, ge=5)


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    apprise_url: str
    notify_on_price_drop: bool
    notify_on_target_price: bool
    price_drop_threshold_percent: float
    notify_on_stock_change: bool
    notify_on_new_low: bool
    check_interval_minutes: int

    @field_serializer("apprise_url")
    def _mask(self, url: str) -> str:
        return mask(url)


class NotificationTest(BaseModel):
    apprise_url: Text


class AITest(BaseModel):
    item_id: int
    settings: dict[str, Any] = {}  # unsaved changes from the settings form


class AITestResult(BaseModel):
    seconds: float
    reply: str
    extraction: dict[str, Any] | None
    error: str | None
