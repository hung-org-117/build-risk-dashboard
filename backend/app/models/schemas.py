"""
Pydantic schemas for request/response validation
"""
from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# Build schemas
class BuildBase(BaseModel):
    repository: str
    branch: str
    commit_sha: str
    build_number: str
    workflow_name: Optional[str] = None
    status: str
    conclusion: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    url: Optional[str] = None
    logs_url: Optional[str] = None


class BuildCreate(BuildBase):
    """Schema for creating a new build"""
    pass


class BuildResponse(BuildBase):
    """Schema for build response"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class BuildListItem(BuildResponse):
    """Build item with related analytics"""
    sonarqube_result: Optional['SonarQubeResultResponse'] = None
    risk_assessment: Optional['RiskScoreResponse'] = None


class BuildListResponse(BaseModel):
    """Schema for paginated build list response"""
    total: int
    skip: int
    limit: int
    builds: List[BuildListItem]


# SonarQube schemas
class SonarQubeResultBase(BaseModel):
    bugs: int = 0
    vulnerabilities: int = 0
    code_smells: int = 0
    coverage: float = 0.0
    duplicated_lines_density: float = 0.0
    technical_debt_minutes: int = 0
    quality_gate_status: Optional[str] = None


class SonarQubeResultResponse(SonarQubeResultBase):
    id: int
    build_id: int
    analyzed_at: datetime
    
    class Config:
        from_attributes = True


# Risk assessment schemas
class RiskScoreResponse(BaseModel):
    """Schema for risk score response"""
    build_id: int
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Risk score from 0 to 1")
    uncertainty: float = Field(..., ge=0.0, le=1.0, description="Model uncertainty")
    risk_level: str = Field(..., description="Risk level: low, medium, high, critical")
    calculated_at: datetime
    
    class Config:
        from_attributes = True


# Build detail with all related data
class BuildDetailResponse(BuildListItem):
    """Schema for detailed build information including all assessments"""


# Dashboard schemas
class DashboardMetrics(BaseModel):
    total_builds: int
    average_risk_score: float
    success_rate: float
    average_duration_minutes: float
    risk_distribution: Dict[str, int]


class DashboardTrendPoint(BaseModel):
    date: str
    builds: int
    risk_score: float
    failures: int


class RepoDistributionEntry(BaseModel):
    repository: str
    builds: int
    high_risk: int = Field(..., alias="highRisk")

    class Config:
        populate_by_name = True


class RiskHeatmapRow(BaseModel):
    day: str
    low: int
    medium: int
    high: int
    critical: int


class HighRiskBuild(BaseModel):
    id: int
    repository: str
    branch: str
    workflow_name: Optional[str]
    risk_level: str
    risk_score: float
    conclusion: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class DashboardSummaryResponse(BaseModel):
    metrics: DashboardMetrics
    trends: List[DashboardTrendPoint]
    repo_distribution: List[RepoDistributionEntry]
    risk_heatmap: List[RiskHeatmapRow]
    high_risk_builds: List[HighRiskBuild]
    
    class Config:
        from_attributes = True


BuildListItem.model_rebuild()
BuildDetailResponse.model_rebuild()


# GitHub integration schemas
class GithubRepositoryStatus(BaseModel):
    name: str
    lastSync: Optional[datetime] = None
    buildCount: int
    highRiskCount: int
    status: str


class GithubIntegrationStatusResponse(BaseModel):
    connected: bool
    organization: Optional[str] = None
    connectedAt: Optional[datetime] = None
    scopes: List[str]
    repositories: List[GithubRepositoryStatus] = []
    lastSyncStatus: str
    lastSyncMessage: Optional[str] = None
    accountLogin: Optional[str] = None
    accountName: Optional[str] = None
    accountAvatarUrl: Optional[str] = None


class GithubAuthorizeResponse(BaseModel):
    authorize_url: str
    state: str


class GithubLoginRequest(BaseModel):
    redirect_path: Optional[str] = None


# Risk explanation schemas
class RiskDriver(BaseModel):
    key: str
    label: str
    impact: Literal["increase", "decrease"]
    contribution: float = Field(..., ge=0.0, le=1.0)
    description: str
    metrics: Dict[str, object] = Field(default_factory=dict)


class RiskExplanationResponse(BaseModel):
    build_id: int
    risk_score: float
    uncertainty: float
    risk_level: str
    summary: str
    confidence: str
    model_version: Optional[str] = None
    updated_at: datetime
    drivers: List[RiskDriver]
    feature_breakdown: Dict[str, float]
    recommended_actions: List[str]


# Data pipeline schemas
class PipelineStage(BaseModel):
    key: str
    label: str
    status: Literal["pending", "running", "completed", "blocked"]
    percent_complete: int = Field(..., ge=0, le=100)
    duration_seconds: Optional[int] = None
    items_processed: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    issues: List[str] = Field(default_factory=list)


class PipelineStatusResponse(BaseModel):
    last_run: datetime
    next_run: datetime
    normalized_features: int
    pending_repositories: int
    anomalies_detected: int
    stages: List[PipelineStage]


# GitHub repository import schemas
class GithubImportRequest(BaseModel):
    repository: str
    branch: str = Field(..., description="Default branch to scan (e.g., main)")
    initiated_by: Optional[str] = Field(default="admin", description="User requesting the import")


class GithubImportJobResponse(BaseModel):
    id: str
    repository: str
    branch: str
    status: Literal["pending", "running", "completed", "failed"]
    progress: int = Field(..., ge=0, le=100)
    builds_imported: int
    commits_analyzed: int
    tests_collected: int
    initiated_by: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_error: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


# Settings & admin schemas
class SystemSettings(BaseModel):
    model_version: str
    risk_threshold_high: float = Field(..., ge=0.0, le=1.0)
    risk_threshold_medium: float = Field(..., ge=0.0, le=1.0)
    uncertainty_threshold: float = Field(..., ge=0.0, le=1.0)
    auto_rescan_enabled: bool = False
    updated_at: datetime
    updated_by: str


class SystemSettingsUpdate(BaseModel):
    model_version: Optional[str] = None
    risk_threshold_high: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    risk_threshold_medium: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    uncertainty_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    auto_rescan_enabled: Optional[bool] = None
    updated_by: Optional[str] = None


class ActivityLogEntry(BaseModel):
    id: str = Field(..., alias="_id")
    action: str
    actor: str
    scope: str
    message: str
    created_at: datetime
    metadata: Dict[str, str] = Field(default_factory=dict)

    class Config:
        populate_by_name = True


class ActivityLogListResponse(BaseModel):
    logs: List[ActivityLogEntry]


class NotificationPolicy(BaseModel):
    risk_threshold_high: float = Field(..., ge=0.0, le=1.0)
    uncertainty_threshold: float = Field(..., ge=0.0, le=1.0)
    channels: List[str]
    muted_repositories: List[str] = []
    last_updated_at: datetime
    last_updated_by: str


class NotificationPolicyUpdate(BaseModel):
    risk_threshold_high: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    uncertainty_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    channels: Optional[List[str]] = None
    muted_repositories: Optional[List[str]] = None
    updated_by: str


class NotificationItem(BaseModel):
    id: str = Field(..., alias="_id")
    build_id: int
    repository: str
    branch: str
    risk_level: str
    risk_score: float
    uncertainty: float
    status: Literal["new", "sent", "acknowledged"]
    created_at: datetime
    message: str

    class Config:
        populate_by_name = True


class NotificationListResponse(BaseModel):
    notifications: List[NotificationItem]


class UserRoleDefinition(BaseModel):
    role: str
    description: str
    permissions: List[str]
    admin_only: bool = False


class RoleListResponse(BaseModel):
    roles: List[UserRoleDefinition]
