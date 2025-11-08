"""Data pipeline status endpoints."""

from fastapi import APIRouter, Depends
from pymongo.database import Database

from app.database.mongo import get_db
from app.models.schemas import PipelineStatusResponse
from app.services.data_pipeline import compute_pipeline_status

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


@router.get("/status", response_model=PipelineStatusResponse)
def get_pipeline_status(db: Database = Depends(get_db)):
    """Return the latest preprocessing / normalization pipeline status."""
    return compute_pipeline_status(db)
