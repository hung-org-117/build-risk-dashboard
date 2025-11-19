"""Initial Scan Job entity - tracks backfill progress"""

from datetime import datetime
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, Field


class InitialScanJob(BaseModel):
    id: Optional[ObjectId] = Field(None, alias="_id")
    repo_id: ObjectId
    status: str = "queued"  # queued, running, completed, failed
    phase: str = "pending"  # pending, discovering, processing, finalizing
    total_runs: int = 0
    processed_runs: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
