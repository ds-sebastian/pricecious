import asyncio
import logging
import os
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import ai, database, models, notifications, scraper

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Manual migrations removed in favor of Alembic
# models.Base.metadata.create_all(bind=engine) # Alembic should handle this

VERSION = "0.1.0"

app = FastAPI(title="Pricecious API", version=VERSION)

# Middleware for logging requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.debug(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.debug(f"Response: {response.status_code}")
    return response

# Mount static files
if os.path.exists("static"):
    logger.info("Mounting static files from static")
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
else:
    logger.warning("Static files directory static not found")

# Mount screenshots
os.makedirs("screenshots", exist_ok=True)
app.mount("/screenshots", StaticFiles(directory="screenshots"), name="screenshots")

# Pydantic models
class NotificationProfileCreate(BaseModel):
    name: str
    apprise_url: str
    notify_on_price_drop: bool = True
    notify_on_target_price: bool = True
    price_drop_threshold_percent: float = 10.0
    notify_on_stock_change: bool = True
    check_interval_minutes: int = 60

class NotificationProfileResponse(NotificationProfileCreate):
    id: int
    class Config:
        orm_mode = True

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
    is_active: bool
    last_checked: datetime | None
    is_refreshing: bool = False
    last_error: str | None = None
    screenshot_url: str | None = None

    class Config:
        orm_mode = True

    @staticmethod
    def resolve_screenshot_url(item_id: int):
        # Check if file exists
        if os.path.exists(f"screenshots/item_{item_id}.png"):
            return f"/screenshots/item_{item_id}.png"
        return None

class SettingsUpdate(BaseModel):
    key: str
    value: str

# API Router
api_router = APIRouter(prefix="/api")

@api_router.get("/")
def read_root():
    return {"message": "Welcome to Pricecious API"}

# --- Notification Profiles ---
@api_router.get("/notification-profiles", response_model=list[NotificationProfileResponse])
def get_notification_profiles(db: Session = Depends(database.get_db)):  # noqa: B008
    return db.query(models.NotificationProfile).all()

@api_router.post("/notification-profiles", response_model=NotificationProfileResponse)
def create_notification_profile(profile: NotificationProfileCreate, db: Session = Depends(database.get_db)):  # noqa: B008
    db_profile = models.NotificationProfile(**profile.dict())
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile

@api_router.delete("/notification-profiles/{profile_id}")
def delete_notification_profile(profile_id: int, db: Session = Depends(database.get_db)):  # noqa: B008
    profile = db.query(models.NotificationProfile).filter(models.NotificationProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    db.delete(profile)
    db.commit()
    return {"ok": True}

# --- Items ---
@api_router.get("/items", response_model=list[ItemResponse])
def get_items(db: Session = Depends(database.get_db)):  # noqa: B008
    items = db.query(models.Item).all()
    # Manually inject screenshot URL since it's not in DB
    response_items = []
    for item in items:
        item_dict = item.__dict__
        item_dict['screenshot_url'] = ItemResponse.resolve_screenshot_url(item.id)
        response_items.append(item_dict)
    return response_items

@api_router.post("/items", response_model=ItemResponse)
def create_item(item: ItemCreate, db: Session = Depends(database.get_db)):  # noqa: B008
    logger.info(f"Creating item: {item.name} - {item.url}")
    db_item = models.Item(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    logger.info(f"Item created with ID: {db_item.id}")
    return db_item

@api_router.put("/items/{item_id}", response_model=ItemResponse)
def update_item(item_id: int, item_update: ItemCreate, db: Session = Depends(database.get_db)):  # noqa: B008
    db_item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    for key, value in item_update.dict().items():
        setattr(db_item, key, value)

    db.commit()
    db.refresh(db_item)
    return db_item

@api_router.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(database.get_db)):  # noqa: B008
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Delete screenshot if exists
    try:
        if os.path.exists(f"screenshots/item_{item_id}.png"):
            os.remove(f"screenshots/item_{item_id}.png")
    except Exception as e:
        logger.error(f"Error deleting screenshot: {e}")

    db.delete(item)
    db.commit()
    return {"ok": True}

@api_router.post("/items/{item_id}/check")
def check_item(item_id: int, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):  # noqa: B008
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    logger.info(f"Triggering check for item ID: {item_id}")

    # Set refreshing state immediately
    item.is_refreshing = True
    item.last_error = None
    db.commit()

    # Don't pass the request-scoped DB session to the background task
    background_tasks.add_task(process_item_check, item_id)
    return {"message": "Check triggered"}

# Scheduler
scheduler = AsyncIOScheduler()

async def scheduled_refresh():
    logger.info("Heartbeat: Checking for items due for refresh")
    # Use module-level import
    SessionLocal = database.SessionLocal

    loop = asyncio.get_running_loop()

    def get_due_items():
        db = SessionLocal()
        try:
            items = db.query(models.Item).filter(models.Item.is_active).all()

            # Get global default interval
            global_setting = db.query(models.Settings).filter(models.Settings.key == "refresh_interval_minutes").first()
            global_interval = int(global_setting.value) if global_setting else 60

            due_items = []
            for item in items:
                # Determine item's interval
                interval = global_interval
                if item.notification_profile and item.notification_profile.check_interval_minutes:
                    interval = item.notification_profile.check_interval_minutes

                # Check if due
                if item.last_checked:
                    time_since_check = (datetime.utcnow() - item.last_checked).total_seconds() / 60
                    if time_since_check >= interval:
                        due_items.append((item.id, interval, int(time_since_check)))
                else:
                    # Never checked, check now
                    due_items.append((item.id, interval, -1))
            return due_items
        finally:
            db.close()

    try:
        due_items = await loop.run_in_executor(None, get_due_items)

        triggered_count = 0
        for item_id, interval, time_since in due_items:
            if time_since == -1:
                logger.info(f"Item {item_id} never checked, checking now")
            else:
                logger.info(f"Item {item_id} due for check (Interval: {interval}m, Last check: {time_since}m ago)")

            await process_item_check(item_id)
            triggered_count += 1

        if triggered_count > 0:
            logger.info(f"Heartbeat: Triggered checks for {triggered_count} items")

    except Exception as e:
        logger.error(f"Error in scheduled refresh: {e}")


@app.on_event("startup")
async def start_scheduler():
    logger.info("Starting smart scheduler (Heartbeat: 1 minute)")
    # Run every minute to check if any items are due
    scheduler.add_job(scheduled_refresh, IntervalTrigger(minutes=1), id="refresh_job", replace_existing=True)
    scheduler.start()

@api_router.get("/jobs/config")
def get_job_config(db: Session = Depends(database.get_db)):  # noqa: B008
    setting = db.query(models.Settings).filter(models.Settings.key == "refresh_interval_minutes").first()
    interval = int(setting.value) if setting else 60

    next_run = None
    job = scheduler.get_job("refresh_job")
    if job:
        next_run = job.next_run_time

    return {
        "refresh_interval_minutes": interval,
        "next_run": next_run,
        "running": scheduler.running
    }

@api_router.post("/jobs/config")
def update_job_config(config: SettingsUpdate, db: Session = Depends(database.get_db)):  # noqa: B008
    if config.key != "refresh_interval_minutes":
        raise HTTPException(status_code=400, detail="Invalid setting key for job config")

    try:
        interval = int(config.value)
        if interval < 1:
            raise ValueError("Interval must be at least 1 minute")
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid interval value") from e

    # Update DB
    setting = db.query(models.Settings).filter(models.Settings.key == "refresh_interval_minutes").first()
    if not setting:
        setting = models.Settings(key="refresh_interval_minutes", value=str(interval))
        db.add(setting)
    else:
        setting.value = str(interval)
    db.commit()

    # Update Job
    try:
        scheduler.reschedule_job("refresh_job", trigger=IntervalTrigger(minutes=interval))
        logger.info(f"Rescheduled refresh job to {interval} minutes")
    except Exception as e:
        logger.error(f"Failed to reschedule job: {e}")
        # If job doesn't exist for some reason, add it
        scheduler.add_job(scheduled_refresh, IntervalTrigger(minutes=interval), id="refresh_job", replace_existing=True)

    return {"message": "Job configuration updated", "refresh_interval_minutes": interval}

@api_router.post("/jobs/refresh-all")
def refresh_all_items(background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):  # noqa: B008
    items = db.query(models.Item).filter(models.Item.is_active).all()
    logger.info(f"Triggering refresh for all {len(items)} items")
    for item in items:
        background_tasks.add_task(process_item_check, item.id)
    return {"message": f"Triggered refresh for {len(items)} items"}

async def process_item_check(item_id: int, db: Session = None):  # noqa: PLR0912, PLR0915
    """
    Background task to check an item's price/stock.
    Creates its own DB session to ensure thread safety and avoid closed session errors.
    """
    # Use module-level import
    SessionLocal = database.SessionLocal

    # Create a new session for this background task
    # We use run_in_executor for blocking DB operations until we switch to AsyncSession completely
    loop = asyncio.get_running_loop()

    def get_item_data():
        session = SessionLocal()
        try:
            item = session.query(models.Item).filter(models.Item.id == item_id).first()
            if not item:
                return None, None

            # Eager load profile to avoid detached instance errors later
            # or just fetch what we need
            profile = item.notification_profile

            # Fetch Settings
            settings_map = {s.key: s.value for s in session.query(models.Settings).all()}

            # Return detached data or keep session open?
            # Keeping session open in thread is tricky if we mix async.
            # Let's keep it simple: use session in the thread for read, then separate write.
            # Actually, for this refactor, let's keep the session open but be careful.
            # Better pattern: Read data -> Close Session -> Async Work -> Open Session -> Write Data

            item_data = {
                "id": item.id,
                "url": item.url,
                "selector": item.selector,
                "name": item.name,
                "current_price": item.current_price,
                "in_stock": item.in_stock,
                "target_price": item.target_price,
                "notification_profile": {
                    "apprise_url": profile.apprise_url,
                    "notify_on_price_drop": profile.notify_on_price_drop,
                    "price_drop_threshold_percent": profile.price_drop_threshold_percent,
                    "notify_on_target_price": profile.notify_on_target_price,
                    "notify_on_stock_change": profile.notify_on_stock_change
                } if profile else None
            }

            config = {
                "smart_scroll": settings_map.get("smart_scroll_enabled", "false").lower() == "true",
                "smart_scroll_pixels": int(settings_map.get("smart_scroll_pixels", "350")),
                "text_context_enabled": settings_map.get("text_context_enabled", "false").lower() == "true",
                "text_length": int(settings_map.get("text_context_length", "5000"))
                if settings_map.get("text_context_enabled", "false").lower() == "true"
                else 0,
                "scraper_timeout": int(settings_map.get("scraper_timeout", "90000"))
            }

            return item_data, config
        finally:
            session.close()

    item_data, config = await loop.run_in_executor(None, get_item_data)

    if not item_data:
        logger.error(f"process_item_check: Item ID {item_id} not found")
        return

    if not item_data:
        logger.error(f"process_item_check: Item ID {item_id} not found")
        return

    try:
        logger.info(
            f"Checking item: {item_data['name']} ({item_data['url']}) "
            f"[Scroll: {config['smart_scroll']} ({config['smart_scroll_pixels']}px), "
            f"Text: {config['text_length']}, Timeout: {config['scraper_timeout']}]"
        )

        screenshot_path, page_text = await scraper.scrape_item(
            item_data['url'],
            item_data['selector'],
            item_id,
            smart_scroll=config['smart_scroll'],
            scroll_pixels=config['smart_scroll_pixels'],
            text_length=config['text_length'],
            timeout=config['scraper_timeout']
        )

        if screenshot_path:
            logger.info(f"Screenshot captured: {screenshot_path}")
            result = await ai.analyze_image(screenshot_path, page_text=page_text)
            if result:
                price = result.get("price")
                in_stock = result.get("in_stock")

                logger.info(f"Analysis result: Price={price}, Stock={in_stock}")

                # Update DB
                def update_db():
                    session = SessionLocal()
                    try:
                        item = session.query(models.Item).filter(models.Item.id == item_id).first()
                        if not item:
                            return

                        old_price = item.current_price
                        old_stock = item.in_stock

                        if price is not None:
                            item.current_price = price

                        if in_stock is not None:
                            item.in_stock = in_stock

                        # Save history
                        if price is not None:
                            history = models.PriceHistory(item_id=item.id, price=price, screenshot_path=screenshot_path)
                            session.add(history)

                        item.last_checked = datetime.utcnow()
                        item.is_refreshing = False # Reset refreshing state
                        item.last_error = None # Clear error
                        session.commit()

                        return old_price, old_stock
                    finally:
                        session.close()

                old_price, old_stock = await loop.run_in_executor(None, update_db)

                # Notifications
                profile = item_data['notification_profile']
                if profile:
                    # Price Drop (Percentage)
                    if profile['notify_on_price_drop'] and price is not None and old_price is not None:
                        if price < old_price:
                            drop_percent = ((old_price - price) / old_price) * 100
                            if drop_percent >= profile['price_drop_threshold_percent']:
                                await notifications.send_notification(
                                    [profile['apprise_url']],
                                    f"Price Drop Alert: {item_data['name']}",
                                    f"Price dropped by {drop_percent:.1f}%! Now ${price} (was ${old_price})"
                                )

                    # Target Price
                    if (
                        profile['notify_on_target_price']
                        and price is not None
                        and item_data['target_price']
                        and price <= item_data['target_price']
                    ):
                        await notifications.send_notification(
                            [profile['apprise_url']],
                            f"Target Price Alert: {item_data['name']}",
                            f"Price is ${price} (Target: ${item_data['target_price']})",
                        )

                    # Stock Change
                    if (
                        profile['notify_on_stock_change']
                        and in_stock is not None
                        and old_stock is not None
                        and in_stock != old_stock
                    ):
                        status = "In Stock" if in_stock else "Out of Stock"
                        await notifications.send_notification(
                            [profile['apprise_url']],
                            f"Stock Alert: {item_data['name']}",
                            f"Item is now {status}",
                        )
            else:
                error_msg = "AI analysis failed to return a result"
                logger.error(error_msg)
                raise Exception(error_msg)
        else:
            error_msg = "Failed to capture screenshot"
            logger.error(error_msg)
            raise Exception(error_msg)

    except Exception as e:
        logger.error(f"Error in process_item_check: {e}")
        # Update DB with error
        error_str = str(e)
        def update_db_error():
            session = SessionLocal()
            try:
                item = session.query(models.Item).filter(models.Item.id == item_id).first()
                if item:
                    item.is_refreshing = False
                    item.last_error = error_str
                    session.commit()
            finally:
                session.close()
        await loop.run_in_executor(None, update_db_error)


@api_router.get("/settings")
def get_settings(db: Session = Depends(database.get_db)):  # noqa: B008
    return db.query(models.Settings).all()

@api_router.post("/settings", response_model=SettingsUpdate)
def update_setting(setting: SettingsUpdate, db: Session = Depends(database.get_db)):  # noqa: B008
    db_setting = db.query(models.Settings).filter(models.Settings.key == setting.key).first()
    if db_setting:
        db_setting.value = setting.value
    else:
        db_setting = models.Settings(key=setting.key, value=setting.value)
        db.add(db_setting)
    db.commit()
    return db_setting

app.include_router(api_router)

# Serve index.html at root
@app.get("/")
async def serve_index():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "Frontend not built or not found"}

# Catch-all for SPA
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "Frontend not built or not found"}
