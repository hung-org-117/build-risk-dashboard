"""Repository layer for database operations"""

from .base import BaseRepository
from .dataset_build_repository import DatasetBuildRepository

# Dataset enrichment flow repositories
from .dataset_enrichment_build import DatasetEnrichmentBuildRepository

# Dataset repositories
from .dataset_repository import DatasetRepository
from .dataset_template_repository import DatasetTemplateRepository

# Model training flow repositories
from .model_repo_config import ModelRepoConfigRepository
from .model_training_build import ModelTrainingBuildRepository
from .notification import NotificationRepository

# Other repositories
# from .github_installation import GithubInstallationRepository
from .oauth_identity import OAuthIdentityRepository
from .pipeline_run import PipelineRunRepository
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
    "DatasetRepository",
    "DatasetBuildRepository",
    "OAuthIdentityRepository",
    "UserRepository",
    "DatasetTemplateRepository",
    "PipelineRunRepository",
    "NotificationRepository",
]
