"""Activity logging endpoints."""
from fastapi import APIRouter, Depends, Query
from pymongo.database import Database

from app.database.mongo import get_db
from app.models.schemas import ActivityLogListResponse

router = APIRouter(prefix="/logs", tags=["Logging"])


@router.get("/", response_model=ActivityLogListResponse)
def list_logs(
    limit: int = Query(50, ge=1, le=200),
    db: Database = Depends(get_db),
):
    cursor = (
        db.activity_logs.find()
        .sort("created_at", -1)
        .limit(limit)
    )
    logs = list(cursor)
    return {"logs": logs}
