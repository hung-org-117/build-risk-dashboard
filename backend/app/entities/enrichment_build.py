from enum import Enum
from typing import Dict, Optional

from .base import BaseEntity, PyObjectId


class EnrichmentExtractionStatus(str, Enum):
    """Enrichment extraction status."""

    PENDING = "pending"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class EnrichmentBuild(BaseEntity):
    enrichment_repo_id: PyObjectId
    dataset_id: PyObjectId

    build_id: str
    commit_sha: Optional[str] = None

    extraction_status: EnrichmentExtractionStatus = EnrichmentExtractionStatus.PENDING
    error_message: str | None = None

    features: Dict = {}

    class Config:
        collection = "enrichment_builds"
        use_enum_values = True
