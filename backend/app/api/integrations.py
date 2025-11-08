"""Integration endpoints for third-party services."""
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pymongo.database import Database

from app.config import settings
from app.database.mongo import get_db
from app.models.schemas import (
    GithubAuthorizeResponse,
    GithubImportJobResponse,
    GithubImportRequest,
    GithubIntegrationStatusResponse,
    GithubLoginRequest,
)
from app.services.github_integration import (
    create_import_job,
    get_github_status,
    list_import_jobs,
)
from app.services.github_oauth import (
    build_authorize_url,
    create_oauth_state,
    exchange_code_for_token,
)

router = APIRouter(prefix="/integrations", tags=["Integrations"])


@router.get("/github", response_model=GithubIntegrationStatusResponse)
def get_github_integration_status(db: Database = Depends(get_db)):
    """Return the current GitHub OAuth integration status."""
    return get_github_status(db)


@router.post("/github/login", response_model=GithubAuthorizeResponse)
def initiate_github_login(
    payload: GithubLoginRequest | None = Body(default=None),
    db: Database = Depends(get_db),
):
    """Initiate GitHub OAuth flow by creating a state token."""
    payload = payload or GithubLoginRequest()
    oauth_state = create_oauth_state(db, redirect_url=payload.redirect_path)
    authorize_url = build_authorize_url(oauth_state["_id"])
    return {"authorize_url": authorize_url, "state": oauth_state["_id"]}


@router.post("/github/revoke", status_code=status.HTTP_204_NO_CONTENT)
def revoke_github_token(db: Database = Depends(get_db)):
    """Remove stored GitHub access tokens."""
    result = db.github_connection.delete_many({})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy token để thu hồi.")


@router.get("/github/callback")
async def github_oauth_callback(
    code: str = Query(..., description="GitHub authorization code"),
    state: str = Query(..., description="GitHub OAuth state token"),
    db: Database = Depends(get_db),
):
    """Handle GitHub OAuth callback, exchange code for token, and redirect to frontend."""
    _, redirect_path = await exchange_code_for_token(db, code=code, state=state)
    redirect_target = settings.FRONTEND_BASE_URL.rstrip('/')
    if redirect_path:
        redirect_target = f"{redirect_target}{redirect_path}"
    else:
        redirect_target = f"{redirect_target}/integrations/github?status=success"
    return RedirectResponse(url=redirect_target)


@router.get("/github/imports", response_model=List[GithubImportJobResponse])
def list_github_import_jobs(db: Database = Depends(get_db)):
    """List history of GitHub repository import jobs."""
    return list_import_jobs(db)


@router.post("/github/imports", response_model=GithubImportJobResponse, status_code=status.HTTP_201_CREATED)
def start_github_import(payload: GithubImportRequest, db: Database = Depends(get_db)):
    """Create a mock import job for a repository."""
    initiated_by = payload.initiated_by or "admin"
    return create_import_job(db, repository=payload.repository, branch=payload.branch, initiated_by=initiated_by)
