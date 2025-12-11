"""Model Repository entity - for Bayesian model training flow."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .base import BaseEntity, PyObjectId


class Provider(str, Enum):
    GITHUB = "github"


class TestFramework(str, Enum):
    # Python
    PYTEST = "pytest"
    UNITTEST = "unittest"
    # Ruby
    RSPEC = "rspec"
    MINITEST = "minitest"
    TESTUNIT = "testunit"
    CUCUMBER = "cucumber"
    # Java
    JUNIT = "junit"
    TESTNG = "testng"
    # JavaScript/TypeScript
    JEST = "jest"
    MOCHA = "mocha"
    JASMINE = "jasmine"
    VITEST = "vitest"
    # Go
    GOTEST = "gotest"
    GOTESTSUM = "gotestsum"
    # C/C++
    GTEST = "gtest"
    CATCH2 = "catch2"
    CTEST = "ctest"


class ImportStatus(str, Enum):
    QUEUED = "queued"
    IMPORTING = "importing"
    IMPORTED = "imported"
    FAILED = "failed"


class SyncStatus(str, Enum):
    """Repository sync status."""

    SUCCESS = "success"
    FAILED = "failed"


from app.ci_providers.models import CIProvider


class ModelRepository(BaseEntity):
    user_id: PyObjectId
    provider: Provider = Provider.GITHUB

    full_name: str
    github_repo_id: int | None = None
    default_branch: str | None = None
    is_private: bool = False
    main_lang: str | None = None

    test_frameworks: List[TestFramework] = []
    source_languages: List[str] = []

    ci_provider: CIProvider = CIProvider.GITHUB_ACTIONS
    installation_id: str | None = None

    import_status: ImportStatus = ImportStatus.QUEUED
    total_builds_imported: int = 0
    last_scanned_at: datetime | None = None
    last_sync_error: str | None = None
    notes: str | None = None

    last_synced_at: Optional[datetime] = None
    last_sync_status: Optional[SyncStatus] = None
    latest_synced_run_created_at: datetime | None = None

    max_builds_to_ingest: Optional[int] = None

    metadata: Dict[str, Any] = {}

    class Config:
        collection = "model_repositories"
        use_enum_values = True
