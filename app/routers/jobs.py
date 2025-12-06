from apscheduler.triggers.interval import IntervalTrigger
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import database, models, schemas
from app.limiter import limiter
from app.services.scheduler_service import process_item_check, scheduled_refresh, scheduler
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/config")
async def get_job_config(db: AsyncSession = Depends(database.get_db)):
    interval_str = await SettingsService.get_setting_value(db, "refresh_interval_minutes", "60")
    interval = int(interval_str)

    next_run = None
    job = scheduler.get_job("refresh_job")
    if job:
        next_run = job.next_run_time

    return {"refresh_interval_minutes": interval, "next_run": next_run, "running": scheduler.running}


@router.post("/config")
async def update_job_config(config: schemas.SettingsUpdate, db: AsyncSession = Depends(database.get_db)):
    if config.key != "refresh_interval_minutes":
        raise HTTPException(status_code=400, detail="Invalid setting key for job config")

    try:
        interval = int(config.value)
        if interval < 1:
            raise ValueError("Interval must be at least 1 minute")
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid interval value") from e

    await SettingsService.update_setting(db, config)

    try:
        scheduler.reschedule_job("refresh_job", trigger=IntervalTrigger(minutes=interval))
    except Exception:
        scheduler.add_job(scheduled_refresh, IntervalTrigger(minutes=interval), id="refresh_job", replace_existing=True)

    return {"message": "Job configuration updated", "refresh_interval_minutes": interval}


@router.post("/refresh-all")
@limiter.limit("5/minute")
async def refresh_all_items(
    request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(database.get_db)
):
    result = await db.execute(select(models.Item).where(models.Item.is_active))
    items = result.scalars().all()

    # Mark all items as refreshing immediately so UI updates persist
    for item in items:
        item.is_refreshing = True
    await db.commit()

    for item in items:
        if item.id is not None:
            background_tasks.add_task(process_item_check, int(item.id))

    return {"message": f"Triggered refresh for {len(items)} items"}
