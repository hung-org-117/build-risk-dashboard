# CI Provider
from app.ci_providers.models import CIProvider

from .base import BaseEntity, PyObjectId
from .data_quality import (
    DataQualityMetric,
    DataQualityReport,
    QualityEvaluationStatus,
    QualityIssue,
    QualityIssueSeverity,
)

# === NEW ENTITIES (Architecture Merge) ===
# Build Source (data collection layer)
from .build_source import (
    BuildSource,
    SourceMapping,
    ValidationStats,
    ValidationStatus,
)
from .source_build import SourceBuild, SourceBuildStatus
from .source_repo_stats import SourceRepoStats

# Training Pipeline (training layer)
from .training_scenario import (
    DataSourceConfig,
    FeatureConfig,
    GroupByDimension,
    OutputConfig,
    PreprocessingConfig,
    ScenarioStatus,
    SplitStrategy,
    SplittingConfig,
    TrainingScenario,
)
from .training_ingestion_build import (
    TrainingIngestionBuild,
    IngestionStatus,
    ResourceStatus,
    ResourceStatusEntry,
)
from .training_enrichment_build import TrainingEnrichmentBuild
from .training_dataset_split import TrainingDatasetSplit

# === LEGACY ENTITIES (to be removed after migration) ===
# Dataset entities (legacy - use BuildSource instead)
from .dataset import (
    DatasetMapping,
    DatasetProject,
    DatasetStats,
    DatasetValidationStatus,
    ValidationStats as LegacyValidationStats,
)
from .dataset_build import DatasetBuild, DatasetBuildStatus
from .dataset_repo_stats import DatasetRepoStats

# Dataset enrichment flow entities (legacy - use unified entities)
from .dataset_enrichment_build import DatasetEnrichmentBuild
from .dataset_import_build import DatasetImportBuild, DatasetImportBuildStatus
from .dataset_template import DatasetTemplate
from .dataset_version import DatasetVersion, VersionStatus


# Shared enums
from .enums import (
    ExtractionStatus,
    TestFramework,
)
from .export_job import ExportFormat, ExportJob, ExportStatus
from .feature_audit_log import (
    AuditLogCategory,
    FeatureAuditLog,
    NodeExecutionResult,
    NodeExecutionStatus,
)

# Model training flow entities
from .model_import_build import ModelImportBuild, ModelImportBuildStatus
from .model_repo_config import ModelImportStatus, ModelRepoConfig
from .model_training_build import ModelTrainingBuild
from .notification import Notification, NotificationType

# Other entities
from .oauth_identity import OAuthIdentity
from .raw_build_run import RawBuildRun

# Raw data entities (shared across flows)
from .raw_repository import RawRepository
from .user import User

__all__ = [
    # Base
    "BaseEntity",
    "PyObjectId",
    # === NEW ENTITIES ===
    # Build Source
    "BuildSource",
    "SourceMapping",
    "ValidationStats",
    "ValidationStatus",
    "SourceBuild",
    "SourceBuildStatus",
    "SourceRepoStats",
    # Training Scenario
    "TrainingScenario",
    "ScenarioStatus",
    "DataSourceConfig",
    "FeatureConfig",
    "SplittingConfig",
    "PreprocessingConfig",
    "OutputConfig",
    "SplitStrategy",
    "GroupByDimension",
    # Ingestion & Enrichment
    "TrainingIngestionBuild",
    "IngestionStatus",
    "ResourceStatus",
    "ResourceStatusEntry",
    "TrainingEnrichmentBuild",
    "TrainingDatasetSplit",
    # === LEGACY ENTITIES ===
    # Enums
    "TestFramework",
    "ExtractionStatus",
    "ModelImportStatus",
    "CIProvider",
    "RawRepository",
    "RawBuildRun",
    "ModelRepoConfig",
    "ModelImportBuild",
    "ModelImportBuildStatus",
    "ModelTrainingBuild",
    # Legacy dataset
    "DatasetEnrichmentBuild",
    "DatasetImportBuild",
    "DatasetImportBuildStatus",
    "DatasetProject",
    "DatasetMapping",
    "DatasetStats",
    "DatasetValidationStatus",
    "DatasetBuild",
    "DatasetBuildStatus",
    "DatasetRepoStats",
    "DatasetVersion",
    "VersionStatus",
    # Legacy ML Scenario
    "MLScenario",
    "MLScenarioStatus",
    "MLScenarioImportBuild",
    "MLScenarioImportBuildStatus",
    "MLScenarioEnrichmentBuild",
    "MLDatasetSplit",
    # Other
    "OAuthIdentity",
    "User",
    "DatasetTemplate",
    "FeatureAuditLog",
    "AuditLogCategory",
    "NodeExecutionResult",
    "NodeExecutionStatus",
    "ExportJob",
    "ExportStatus",
    "ExportFormat",
    "Notification",
    "NotificationType",
    "DataQualityReport",
    "DataQualityMetric",
    "QualityEvaluationStatus",
    "QualityIssue",
    "QualityIssueSeverity",
]
