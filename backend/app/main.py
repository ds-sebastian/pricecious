from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, APIRouter, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import os
import logging
from . import models, database, scraper, ai, notifications
from .database import engine

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=engine)

# Simple migration to ensure new columns exist
def run_migrations():
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            # Check if columns exist
            try:
                conn.execute(text("ALTER TABLE notification_profiles ADD COLUMN notify_on_target_price BOOLEAN DEFAULT TRUE"))
                logger.info("Added notify_on_target_price column")
            except Exception:
                pass
            
            try:
                conn.execute(text("ALTER TABLE notification_profiles ADD COLUMN price_drop_threshold_percent FLOAT DEFAULT 10.0"))
                logger.info("Added price_drop_threshold_percent column")
            except Exception:
                pass
            conn.commit()
    except Exception as e:
        logger.error(f"Migration error: {e}")

run_migrations()

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
if os.path.exists("/app/static"):
    logger.info("Mounting static files from /app/static")
    app.mount("/assets", StaticFiles(directory="/app/static/assets"), name="assets")
else:
    logger.warning("Static files directory /app/static not found")

# Mount screenshots
os.makedirs("/app/screenshots", exist_ok=True)
app.mount("/screenshots", StaticFiles(directory="/app/screenshots"), name="screenshots")

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
    selector: Optional[str] = None
    target_price: Optional[float] = None
    check_interval_minutes: int = 60
    tags: Optional[str] = None
    description: Optional[str] = None
    notification_profile_id: Optional[int] = None

class ItemResponse(ItemCreate):
    id: int
    current_price: Optional[float]
    in_stock: Optional[bool]
    is_active: bool
    last_checked: Optional[datetime]
    screenshot_url: Optional[str] = None
    
    class Config:
        orm_mode = True

    @staticmethod
    def resolve_screenshot_url(item_id: int):
        # Check if file exists
        if os.path.exists(f"/app/screenshots/item_{item_id}.png"):
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
@api_router.get("/notification-profiles", response_model=List[NotificationProfileResponse])
def get_notification_profiles(db: Session = Depends(database.get_db)):
    return db.query(models.NotificationProfile).all()

@api_router.post("/notification-profiles", response_model=NotificationProfileResponse)
def create_notification_profile(profile: NotificationProfileCreate, db: Session = Depends(database.get_db)):
    db_profile = models.NotificationProfile(**profile.dict())
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile

@api_router.delete("/notification-profiles/{profile_id}")
def delete_notification_profile(profile_id: int, db: Session = Depends(database.get_db)):
    profile = db.query(models.NotificationProfile).filter(models.NotificationProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    db.delete(profile)
    db.commit()
    return {"ok": True}

# --- Items ---
@api_router.get("/items", response_model=List[ItemResponse])
def get_items(db: Session = Depends(database.get_db)):
    items = db.query(models.Item).all()
    # Manually inject screenshot URL since it's not in DB
    response_items = []
    for item in items:
        item_dict = item.__dict__
        item_dict['screenshot_url'] = ItemResponse.resolve_screenshot_url(item.id)
        response_items.append(item_dict)
    return response_items

@api_router.post("/items", response_model=ItemResponse)
def create_item(item: ItemCreate, db: Session = Depends(database.get_db)):
    logger.info(f"Creating item: {item.name} - {item.url}")
    db_item = models.Item(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    logger.info(f"Item created with ID: {db_item.id}")
    return db_item

@api_router.put("/items/{item_id}", response_model=ItemResponse)
def update_item(item_id: int, item_update: ItemCreate, db: Session = Depends(database.get_db)):
    db_item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    for key, value in item_update.dict().items():
        setattr(db_item, key, value)
    
    db.commit()
    db.refresh(db_item)
    return db_item

@api_router.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(database.get_db)):
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Delete screenshot if exists
    try:
        if os.path.exists(f"/app/screenshots/item_{item_id}.png"):
            os.remove(f"/app/screenshots/item_{item_id}.png")
    except Exception as e:
        logger.error(f"Error deleting screenshot: {e}")

    db.delete(item)
    db.commit()
    return {"ok": True}

@api_router.post("/items/{item_id}/check")
def check_item(item_id: int, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    logger.info(f"Triggering check for item ID: {item_id}")
    background_tasks.add_task(process_item_check, item_id, db)
    return {"message": "Check triggered"}

# ... (previous imports)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# ... (previous code)

# Scheduler
scheduler = AsyncIOScheduler()

async def scheduled_refresh():
    logger.info("Heartbeat: Checking for items due for refresh")
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        items = db.query(models.Item).filter(models.Item.is_active == True).all()
        
        # Get global default interval
        global_setting = db.query(models.Settings).filter(models.Settings.key == "refresh_interval_minutes").first()
        global_interval = int(global_setting.value) if global_setting else 60
        
        triggered_count = 0
        for item in items:
            # Determine item's interval
            interval = global_interval
            if item.notification_profile and item.notification_profile.check_interval_minutes:
                interval = item.notification_profile.check_interval_minutes
            
            # Check if due
            if item.last_checked:
                time_since_check = (datetime.utcnow() - item.last_checked).total_seconds() / 60
                if time_since_check >= interval:
                    logger.info(f"Item {item.id} due for check (Interval: {interval}m, Last check: {int(time_since_check)}m ago)")
                    await process_item_check(item.id, db)
                    triggered_count += 1
            else:
                # Never checked, check now
                logger.info(f"Item {item.id} never checked, checking now")
                await process_item_check(item.id, db)
                triggered_count += 1
                
        if triggered_count > 0:
            logger.info(f"Heartbeat: Triggered checks for {triggered_count} items")
            
    except Exception as e:
        logger.error(f"Error in scheduled refresh: {e}")
    finally:
        db.close()

@app.on_event("startup")
async def start_scheduler():
    logger.info("Starting smart scheduler (Heartbeat: 1 minute)")
    # Run every minute to check if any items are due
    scheduler.add_job(scheduled_refresh, IntervalTrigger(minutes=1), id="refresh_job", replace_existing=True)
    scheduler.start()

@api_router.get("/jobs/config")
def get_job_config(db: Session = Depends(database.get_db)):
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
def update_job_config(config: SettingsUpdate, db: Session = Depends(database.get_db)):
    if config.key != "refresh_interval_minutes":
        raise HTTPException(status_code=400, detail="Invalid setting key for job config")
    
    try:
        interval = int(config.value)
        if interval < 1:
            raise ValueError("Interval must be at least 1 minute")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid interval value")

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
def refresh_all_items(background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    items = db.query(models.Item).filter(models.Item.is_active == True).all()
    logger.info(f"Triggering refresh for all {len(items)} items")
    for item in items:
        background_tasks.add_task(process_item_check, item.id, db)
    return {"message": f"Triggered refresh for {len(items)} items"}

async def process_item_check(item_id: int, db: Session):
    # Re-query item to ensure we have latest session attached
    # Note: We need a new session for background tasks ideally, but here we are passing one.
    # For simplicity in this design, we'll use the passed session but be careful.
    # Actually, FastAPI dependency injection session might be closed. 
    # Better to create a new session.
    
    from app.database import SessionLocal
    db = SessionLocal()
    
    try:
        item = db.query(models.Item).filter(models.Item.id == item_id).first()
        if not item:
            logger.error(f"process_item_check: Item ID {item_id} not found")
            return

        # Fetch Settings
        settings_map = {s.key: s.value for s in db.query(models.Settings).all()}
        smart_scroll = settings_map.get("smart_scroll_enabled", "false").lower() == "true"
        smart_scroll_pixels = int(settings_map.get("smart_scroll_pixels", "350"))
        text_context_enabled = settings_map.get("text_context_enabled", "false").lower() == "true"
        text_length = int(settings_map.get("text_context_length", "5000")) if text_context_enabled else 0

        logger.info(f"Checking item: {item.name} ({item.url}) [Scroll: {smart_scroll} ({smart_scroll_pixels}px), Text: {text_length}]")
        
        screenshot_path, page_text = await scraper.scrape_item(
            item.url, 
            item.selector, 
            item_id, 
            smart_scroll=smart_scroll, 
            scroll_pixels=smart_scroll_pixels,
            text_length=text_length
        )
        
        if screenshot_path:
            logger.info(f"Screenshot captured: {screenshot_path}")
            result = ai.analyze_image(screenshot_path, page_text=page_text)
            if result:
                price = result.get("price")
                in_stock = result.get("in_stock")
                
                logger.info(f"Analysis result: Price={price}, Stock={in_stock}")
                
                # Update item
                old_price = item.current_price
                old_stock = item.in_stock
                
                if price is not None:
                    item.current_price = price
                
                if in_stock is not None:
                    item.in_stock = in_stock

                # Save history
                if price is not None:
                    history = models.PriceHistory(item_id=item.id, price=price, screenshot_path=screenshot_path)
                    db.add(history)
                
                # Notifications
                if item.notification_profile_id:
                    profile = item.notification_profile
                    if profile:
                        # Price Drop (Percentage)
                        if profile.notify_on_price_drop and price is not None and old_price is not None:
                            if price < old_price:
                                drop_percent = ((old_price - price) / old_price) * 100
                                if drop_percent >= profile.price_drop_threshold_percent:
                                    notifications.send_notification(
                                        [profile.apprise_url], 
                                        f"Price Drop Alert: {item.name}", 
                                        f"Price dropped by {drop_percent:.1f}%! Now ${price} (was ${old_price})"
                                    )

                        # Target Price
                        if profile.notify_on_target_price and price is not None and item.target_price and price <= item.target_price:
                             notifications.send_notification([profile.apprise_url], f"Target Price Alert: {item.name}", f"Price is ${price} (Target: ${item.target_price})")
                        
                        # Stock Change
                        if profile.notify_on_stock_change and in_stock is not None and old_stock is not None and in_stock != old_stock:
                            status = "In Stock" if in_stock else "Out of Stock"
                            notifications.send_notification([profile.apprise_url], f"Stock Alert: {item.name}", f"Item is now {status}")

                item.last_checked = datetime.utcnow()
                db.commit()
            else:
                logger.error("AI analysis failed to return a result")
        else:
            logger.error("Failed to capture screenshot")
    except Exception as e:
        logger.error(f"Error in process_item_check: {e}")
    finally:
        db.close()

@api_router.get("/settings")
def get_settings(db: Session = Depends(database.get_db)):
    return db.query(models.Settings).all()

@api_router.post("/settings")
def update_setting(setting: SettingsUpdate, db: Session = Depends(database.get_db)):
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
    if os.path.exists("/app/static/index.html"):
        return FileResponse("/app/static/index.html")
    return {"message": "Frontend not built or not found"}

# Catch-all for SPA
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if os.path.exists("/app/static/index.html"):
        return FileResponse("/app/static/index.html")
    return {"message": "Frontend not built or not found"}
