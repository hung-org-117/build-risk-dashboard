"""DTOs for pipeline API."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ============================================================================
# Node and Run DTOs
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


class PipelineRunDTO(BaseModel):
    """Pipeline run summary."""

    id: str
    build_sample_id: str
    repo_id: str
    workflow_run_id: int
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    feature_count: int = 0
    nodes_executed: int = 0
    nodes_failed: int = 0
    nodes_skipped: int = 0
    total_retries: int = 0
    dag_version: Optional[str] = None
    errors: List[str] = []
    warnings: List[str] = []
    created_at: datetime


class PipelineRunDetailDTO(PipelineRunDTO):
    """Pipeline run with full details."""

    features_extracted: List[str] = []
    node_results: List[NodeResultDTO] = []


# ============================================================================
# Stats and DAG DTOs
# ============================================================================


class PipelineStatsDTO(BaseModel):
    """Pipeline statistics."""

    total_runs: int
    completed: int
    failed: int
    success_rate: float
    avg_duration_ms: float
    total_features: int
    total_retries: int
    avg_nodes_executed: float
    period_days: int


class DAGInfoDTO(BaseModel):
    """DAG information."""

    version: str
    node_count: int
    feature_count: int
    nodes: List[str]
    groups: List[str]


# ============================================================================
# List Response DTOs
# ============================================================================


class PipelineRunListResponse(BaseModel):
    """Paginated list of pipeline runs."""

    items: List[PipelineRunDTO]
    total: int
    skip: int
    limit: int
