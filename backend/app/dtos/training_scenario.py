from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.entities.training_scenario import ScenarioStatus


class DataSourceConfigDTO(BaseModel):
    languages: List[str] = []
    build_source_ids: List[str] = []

    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    conclusions: List[str] = []
    ci_providers: List[str] = []


class FeatureConfigDTO(BaseModel):
    dag_features: List[str] = []
    scan_metrics: Dict[str, List[str]] = {}
    # Tool configurations (editable via UI)
    scan_tool_config: Dict[str, Any] = {}  # SonarQube/Trivy tool settings
    extractor_configs: Dict[str, Any] = {}  # Per-language/framework extractor settings


class TrainingScenarioCreateDTO(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    version: str = "1.0"

    # UI-based config
    data_source_config: Optional[DataSourceConfigDTO] = None
    feature_config: Optional[FeatureConfigDTO] = None


class TrainingScenarioUpdateDTO(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    # Config updates
    data_source_config: Optional[DataSourceConfigDTO] = None
    feature_config: Optional[FeatureConfigDTO] = None


class TrainingScenarioResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    version: str
    status: ScenarioStatus
    error_message: Optional[str] = None

    # Configs (serialized)
    data_source_config: DataSourceConfigDTO
    feature_config: FeatureConfigDTO  # Includes scan_tool_config and extractor_configs
    yaml_config: Optional[str] = ""

    # Statistics
    builds_total: int = 0
    builds_ingested: int = 0
    builds_features_extracted: int = 0
    builds_missing_resource: int = 0
    builds_ingestion_failed: int = 0
    builds_features_extracted_failed: int = 0

    # Scan Stats
    scans_total: int = 0
    scans_completed: int = 0
    scans_failed: int = 0

    # User info
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Phase timestamps
    filtering_completed_at: Optional[datetime] = None
    ingestion_completed_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None

    # Flags
    feature_extraction_completed: bool = False
    scan_extraction_completed: bool = False


class TrainingScenarioListResponse(BaseModel):
    items: List[TrainingScenarioResponse]
    total: int
    skip: int
    limit: int


class GroupInfo(BaseModel):
    value: str
    label: str
    count: int
    warning: Optional[str] = None


class SplittingGroupsResponse(BaseModel):
    group_by: str
    groups: List[GroupInfo]
    total_builds: int


class TrainingIngestionBuildResponse(BaseModel):
    id: str
    ci_run_id: str
    commit_sha: str
    repo_full_name: str
    status: str
    resource_status: Dict[str, Any]
    required_resources: List[str]
    ingestion_error: Optional[str] = None
    created_at: Optional[str] = None
    ingested_at: Optional[str] = None


class TrainingIngestionBuildListResponse(BaseModel):
    items: List[TrainingIngestionBuildResponse]
    total: int
    page: int
    size: int


class TrainingEnrichmentBuildResponse(BaseModel):
    id: str
    raw_build_run_id: str
    ci_run_id: str
    commit_sha: str
    repo_full_name: str
    extraction_status: str
    extraction_error: Optional[str] = None
    feature_count: int
    expected_feature_count: int
    created_at: Optional[str] = None
    enriched_at: Optional[str] = None
    # Details (optional/heavy)
    features: Optional[Dict[str, Any]] = None
    missing_resources: Optional[List[str]] = None
    skipped_features: Optional[List[str]] = None


class TrainingEnrichmentBuildListResponse(BaseModel):
    items: List[TrainingEnrichmentBuildResponse]
    total: int
    page: int
    size: int
