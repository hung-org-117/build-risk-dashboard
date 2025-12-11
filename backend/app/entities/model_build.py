from datetime import datetime
from enum import Enum
from typing import Dict

from .base import BaseEntity, PyObjectId


class ModelBuildConclusion(str, Enum):
    """Build conclusion/result - the final outcome of the build."""

    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class ExtractionStatus(str, Enum):
    """Feature extraction status."""

    PENDING = "pending"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ModelBuild(BaseEntity):
    repo_id: PyObjectId
    workflow_run_id: int
    head_sha: str
    build_number: int
    build_created_at: datetime

    status: ModelBuildConclusion = ModelBuildConclusion.SUCCESS
    extraction_status: ExtractionStatus = ExtractionStatus.PENDING
    error_message: str | None = None
    is_missing_commit: bool = False

    features: Dict = {}

    class Config:
        collection = "model_builds"
        use_enum_values = True
