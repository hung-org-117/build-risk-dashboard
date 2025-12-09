"""Enrichment Repository entity - repos auto-imported during dataset enrichment."""

from enum import Enum
from typing import Optional

from .base import BaseEntity, PyObjectId
from app.ci_providers.models import CIProvider


class EnrichmentImportStatus(str, Enum):
    PENDING = "pending"
    IMPORTED = "imported"
    FAILED = "failed"


class EnrichmentRepository(BaseEntity):
    dataset_id: PyObjectId
    full_name: str

    ci_provider: CIProvider = CIProvider.GITHUB_ACTIONS
    import_status: EnrichmentImportStatus = EnrichmentImportStatus.IMPORTED

    github_repo_id: int | None = None
    default_branch: str | None = None
    is_private: bool = False

    class Config:
        collection = "enrichment_repositories"
