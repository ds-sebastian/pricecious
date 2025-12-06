from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app import database, schemas
from app.limiter import limiter
from app.services.item_service import ItemService
from app.services.scheduler_service import process_item_check

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=list[schemas.ItemResponse])
async def get_items(db: AsyncSession = Depends(database.get_db)):
    return await ItemService.get_items(db)


@router.post("", response_model=schemas.ItemResponse)
async def create_item(item: schemas.ItemCreate, db: AsyncSession = Depends(database.get_db)):
    return await ItemService.create_item(db, item)


@router.put("/{item_id}", response_model=schemas.ItemResponse)
async def update_item(item_id: int, item_update: schemas.ItemCreate, db: AsyncSession = Depends(database.get_db)):
    return await ItemService.update_item(db, item_id, item_update)


@router.delete("/{item_id}")
async def delete_item(item_id: int, db: AsyncSession = Depends(database.get_db)):
    return await ItemService.delete_item(db, item_id)


@router.post("/{item_id}/check")
@limiter.limit("10/minute")
async def check_item(
    request: Request, item_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(database.get_db)
):
    item = await ItemService.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.is_refreshing = True
    item.last_error = None
    await db.commit()

    background_tasks.add_task(process_item_check, item_id)
    return {"message": "Check triggered"}


@router.get("/{item_id}/analytics", response_model=schemas.AnalyticsResponse)
async def get_item_analytics(
    item_id: int,
    std_dev_threshold: float | None = None,
    days: int | None = None,
    db: AsyncSession = Depends(database.get_db),
):
    return await ItemService.get_analytics_data(db, item_id, std_dev_threshold, days)
