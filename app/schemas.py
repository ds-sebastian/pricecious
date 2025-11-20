import os
from datetime import datetime

from pydantic import BaseModel


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

    model_config = {"from_attributes": True}


class ItemCreate(BaseModel):
    url: str
    name: str
    selector: str | None = None
    target_price: float | None = None
    check_interval_minutes: int = 60
    tags: str | None = None
    description: str | None = None
    notification_profile_id: int | None = None


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

    model_config = {"from_attributes": True}

    @staticmethod
    def resolve_screenshot_url(item_id: int):
        # Check if file exists
        if os.path.exists(f"screenshots/item_{item_id}.png"):
            return f"/screenshots/item_{item_id}.png"
        return None


class SettingsUpdate(BaseModel):
    key: str
    value: str
