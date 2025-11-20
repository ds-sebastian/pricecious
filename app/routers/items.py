from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import database, schemas
from app.limiter import limiter
from app.services.item_service import ItemService
from app.services.scheduler_service import process_item_check

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=list[schemas.ItemResponse])
def get_items(db: Session = Depends(database.get_db)):
    return ItemService.get_items(db)


@router.post("", response_model=schemas.ItemResponse)
def create_item(item: schemas.ItemCreate, db: Session = Depends(database.get_db)):
    return ItemService.create_item(db, item)


@router.put("/{item_id}", response_model=schemas.ItemResponse)
def update_item(item_id: int, item_update: schemas.ItemCreate, db: Session = Depends(database.get_db)):
    return ItemService.update_item(db, item_id, item_update)


@router.delete("/{item_id}")
def delete_item(item_id: int, db: Session = Depends(database.get_db)):
    return ItemService.delete_item(db, item_id)


@router.post("/{item_id}/check")
@limiter.limit("10/minute")
def check_item(
    request: Request, item_id: int, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)
):
    item = ItemService.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.is_refreshing = True
    item.last_error = None
    db.commit()

    background_tasks.add_task(process_item_check, item_id)
    return {"message": "Check triggered"}
