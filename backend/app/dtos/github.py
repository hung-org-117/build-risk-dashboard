"""GitHub integration DTOs"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class GithubRepositoryStatus(BaseModel):
    name: str
    lastSync: Optional[datetime] = None
    buildCount: int
    status: str


class GithubAuthorizeResponse(BaseModel):
    authorize_url: str
    state: str


class GithubOAuthInitRequest(BaseModel):
    redirect_path: Optional[str] = None


# Removed GithubInstallationResponse and GithubInstallationListResponse
# as we moved to single-tenant config based installation ID.
