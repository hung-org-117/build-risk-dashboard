from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import Field

from .base import BaseEntity, PyObjectId
from app.ci_providers.models import CIProvider, BuildStatus, BuildConclusion


class WorkflowRunRaw(BaseEntity):
    repo_id: PyObjectId
    workflow_run_id: int
    ci_provider: CIProvider = CIProvider.GITHUB_ACTIONS
    head_sha: str
    run_number: int
    status: BuildStatus = BuildStatus.UNKNOWN
    conclusion: BuildConclusion = BuildConclusion.NONE
    branch: str
    ci_created_at: datetime
    ci_updated_at: datetime

    raw_payload: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        collection = "workflow_runs"
        use_enum_values = True
