"""Repository layer for database operations"""

from .base import BaseRepository
from .data_quality_repository import DataQualityRepository
from .dataset_build_repository import DatasetBuildRepository

# Dataset enrichment flow repositories
from .dataset_enrichment_build import DatasetEnrichmentBuildRepository
from .dataset_import_build import DatasetImportBuildRepository

# Dataset repositories
from .dataset_repository import DatasetRepository
from .dataset_template_repository import DatasetTemplateRepository
from .feature_audit_log import FeatureAuditLogRepository

# Model training flow repositories
from .model_repo_config import ModelRepoConfigRepository
from .model_training_build import ModelTrainingBuildRepository
from .notification import NotificationRepository

# ML Scenario Builder repositories
from .ml_scenario import MLScenarioRepository
from .ml_scenario_import_build import MLScenarioImportBuildRepository
from .ml_scenario_enrichment_build import MLScenarioEnrichmentBuildRepository
from .ml_dataset_split import MLDatasetSplitRepository

# Other repositories
# from .github_installation import GithubInstallationRepository
from .oauth_identity import OAuthIdentityRepository
from .raw_build_run import RawBuildRunRepository

# Raw data repositories (shared across flows)
from .raw_repository import RawRepositoryRepository
from .user import UserRepository

__all__ = [
    "BaseRepository",
    # Raw data (shared)
    "RawRepositoryRepository",
    "RawBuildRunRepository",
    # Model training flow
    "ModelRepoConfigRepository",
    "ModelTrainingBuildRepository",
    # Dataset enrichment flow
    "DatasetEnrichmentBuildRepository",
    "DatasetImportBuildRepository",
    "DatasetRepository",
    "DatasetBuildRepository",
    "OAuthIdentityRepository",
    "UserRepository",
    "DatasetTemplateRepository",
    "FeatureAuditLogRepository",
    "NotificationRepository",
    # Data Quality
    "DataQualityRepository",
    # ML Scenario Builder
    "MLScenarioRepository",
    "MLScenarioImportBuildRepository",
    "MLScenarioEnrichmentBuildRepository",
    "MLDatasetSplitRepository",
]
