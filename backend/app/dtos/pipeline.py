"""DTOs for pipeline and audit log API."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

# ============================================================================
# Node and Audit Log DTOs
# ============================================================================


class NodeResultDTO(BaseModel):
    """Node execution result."""

    node_name: str
    status: str
    duration_ms: float
    features_extracted: List[str]
    error: Optional[str] = None
    warning: Optional[str] = None
    retry_count: int = 0


class FeatureAuditLogDTO(BaseModel):
    """Feature audit log summary."""

    id: str
    raw_build_run_id: str
    raw_repo_id: str
    category: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    feature_count: int = 0
    nodes_executed: int = 0
    nodes_failed: int = 0
    nodes_skipped: int = 0
    total_retries: int = 0
    errors: List[str] = []
    warnings: List[str] = []
    created_at: datetime


class FeatureAuditLogDetailDTO(FeatureAuditLogDTO):
    """Feature audit log with full details."""

    features_extracted: List[str] = []
    node_results: List[NodeResultDTO] = []


# ============================================================================
# List Response DTOs
# ============================================================================


class FeatureAuditLogListResponse(BaseModel):
    """Paginated list of feature audit logs."""

    items: List[FeatureAuditLogDTO]
    total: int
    skip: int
    limit: int
