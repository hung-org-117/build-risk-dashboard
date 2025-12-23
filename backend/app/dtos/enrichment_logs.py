"""
Enrichment Logs DTOs - Data Transfer Objects for enrichment log endpoints.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PhaseResultResponse(BaseModel):
    """Phase result response DTO."""

    phase_name: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    total_items: int = 0
    processed_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0
    errors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PipelineRunResponse(BaseModel):
    """Pipeline run response DTO."""

    pipeline_run_id: str
    correlation_id: str
    pipeline_type: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    total_builds: int = 0
    processed_builds: int = 0
    failed_builds: int = 0
    phases: List[PhaseResultResponse] = Field(default_factory=list)
    result_summary: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    triggered_by: Optional[str] = None


class NodeExecutionResultResponse(BaseModel):
    """Node execution result response DTO."""

    node_name: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: float = 0.0
    features_extracted: List[str] = Field(default_factory=list)
    resources_used: List[str] = Field(default_factory=list)
    resources_missing: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    warning: Optional[str] = None
    skip_reason: Optional[str] = None


class FeatureAuditLogResponse(BaseModel):
    """Feature audit log response DTO."""

    audit_log_id: str
    correlation_id: Optional[str] = None
    category: str
    raw_repo_id: str
    raw_build_run_id: str
    enrichment_build_id: Optional[str] = None
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[float] = None
    feature_count: int = 0
    features_extracted: List[str] = Field(default_factory=list)
    node_results: List[NodeExecutionResultResponse] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    nodes_executed: int = 0
    nodes_succeeded: int = 0
    nodes_failed: int = 0
    nodes_skipped: int = 0
    total_retries: int = 0


class AuditLogListResponse(BaseModel):
    """Paginated audit log list response."""

    items: List[FeatureAuditLogResponse]
    total: int
    skip: int
    limit: int
