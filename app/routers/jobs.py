from apscheduler.triggers.interval import IntervalTrigger
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import database, models, schemas
from app.limiter import limiter
from app.services.scheduler_service import process_item_check, scheduled_refresh, scheduler
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/config")
def get_job_config(db: Session = Depends(database.get_db)):
    interval = int(SettingsService.get_setting_value(db, "refresh_interval_minutes", "60"))

    next_run = None
    job = scheduler.get_job("refresh_job")
    if job:
        next_run = job.next_run_time

    return {"refresh_interval_minutes": interval, "next_run": next_run, "running": scheduler.running}


@router.post("/config")
def update_job_config(config: schemas.SettingsUpdate, db: Session = Depends(database.get_db)):
    if config.key != "refresh_interval_minutes":
        raise HTTPException(status_code=400, detail="Invalid setting key for job config")

    try:
        interval = int(config.value)
        if interval < 1:
            raise ValueError("Interval must be at least 1 minute")
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid interval value") from e

    SettingsService.update_setting(db, config)

    try:
        scheduler.reschedule_job("refresh_job", trigger=IntervalTrigger(minutes=interval))
    except Exception:
        scheduler.add_job(scheduled_refresh, IntervalTrigger(minutes=interval), id="refresh_job", replace_existing=True)

    return {"message": "Job configuration updated", "refresh_interval_minutes": interval}


@router.post("/refresh-all")
@limiter.limit("5/minute")
def refresh_all_items(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    items = db.query(models.Item).filter(models.Item.is_active).all()
    for item in items:
        if item.id is not None:
            background_tasks.add_task(process_item_check, int(item.id))
    return {"message": f"Triggered refresh for {len(items)} items"}
