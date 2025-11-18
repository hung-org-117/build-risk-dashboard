"""Integration endpoints for third-party services."""

import json
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pymongo.database import Database

from app.config import settings
from app.database.mongo import get_db
from app.models.schemas import (
    GithubAuthorizeResponse,
    GithubImportJobResponse,
    GithubImportRequest,
    GithubInstallationListResponse,
    GithubInstallationResponse,
    GithubIntegrationStatusResponse,
    GithubOAuthInitRequest,
)
from app.services.github_integration import (
    create_import_job,
    get_github_status,
    list_import_jobs,
)
from app.services.github_webhook import handle_github_event, verify_signature
from app.services.github_oauth import (
    build_authorize_url,
    create_oauth_state,
    exchange_code_for_token,
)
from app.services.auth import create_access_token

router = APIRouter(prefix="/integrations", tags=["Integrations"])


@router.get("/github", response_model=GithubIntegrationStatusResponse)
def get_github_integration_status(db: Database = Depends(get_db)):
    """Return the current GitHub OAuth integration status."""
    return get_github_status(db)


@router.post("/github/login", response_model=GithubAuthorizeResponse)
def initiate_github_login(
    payload: GithubOAuthInitRequest | None = Body(default=None),
    db: Database = Depends(get_db),
):
    """Initiate GitHub OAuth flow by creating a state token."""
    payload = payload or GithubOAuthInitRequest()
    oauth_state = create_oauth_state(db, redirect_url=payload.redirect_path)
    authorize_url = build_authorize_url(oauth_state["_id"])
    return {"authorize_url": authorize_url, "state": oauth_state["_id"]}


@router.post("/github/revoke", status_code=status.HTTP_204_NO_CONTENT)
def revoke_github_token(db: Database = Depends(get_db)):
    """Remove stored GitHub access tokens."""
    result = db.oauth_identities.update_many(
        {"provider": "github"},
        {
            "$unset": {
                "access_token": "",
                "refresh_token": "",
                "token_expires_at": "",
                "scopes": "",
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No GitHub identities found to revoke.",
        )


@router.get("/github/callback")
async def github_oauth_callback(
    code: str = Query(..., description="GitHub authorization code"),
    state: str = Query(..., description="GitHub OAuth state token"),
    db: Database = Depends(get_db),
):
    """Handle GitHub OAuth callback, exchange code for token, and redirect to frontend."""
    identity_doc, redirect_path = await exchange_code_for_token(
        db, code=code, state=state
    )
    user_id = identity_doc.get("user_id")
    jwt_token = create_access_token(subject=user_id)
    redirect_target = settings.FRONTEND_BASE_URL.rstrip("/")
    if redirect_path:
        redirect_target = f"{redirect_target}{redirect_path}"
    else:
        redirect_target = f"{redirect_target}/integrations/github?status=success"
    response = RedirectResponse(url=redirect_target)
    # Set cookie for frontend usage; allow credentials cross-site
    response.set_cookie(
        key="access_token",
        value=jwt_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    # Also append the token to the query string for convenience while debugging
    # (not recommended for production). If there's already a token or params,
    # we skip this step.
    if settings.DEBUG and "token=" not in redirect_target:
        sep = "?" if "?" not in redirect_target else "&"
        response.headers["location"] = f"{redirect_target}{sep}token={jwt_token}"
    return response


@router.get("/github/imports", response_model=List[GithubImportJobResponse])
def list_github_import_jobs(db: Database = Depends(get_db)):
    """List history of GitHub repository import jobs."""
    return list_import_jobs(db)


@router.post(
    "/github/imports",
    response_model=GithubImportJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_github_import(payload: GithubImportRequest, db: Database = Depends(get_db)):
    """Create a mock import job for a repository."""
    initiated_by = payload.initiated_by or "admin"
    owner_user_id = payload.user_id
    return create_import_job(
        db,
        repository=payload.repository,
        branch=payload.branch,
        initiated_by=initiated_by,
        user_id=owner_user_id,
    )


@router.post("/github/webhook")
async def github_webhook(request: Request, db: Database = Depends(get_db)):
    """Receive GitHub webhook events for workflow runs."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    event = request.headers.get("X-GitHub-Event", "")
    verify_signature(signature, body)

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - invalid payload
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload"
        ) from exc

    return handle_github_event(db, event, payload)


@router.get("/github/installations", response_model=GithubInstallationListResponse)
def list_github_installations(db: Database = Depends(get_db)):
    """List all GitHub App installations."""
    installations = list(db.github_installations.find().sort("installed_at", -1))
    return {"installations": installations}


@router.get(
    "/github/installations/{installation_id}", response_model=GithubInstallationResponse
)
def get_github_installation(installation_id: str, db: Database = Depends(get_db)):
    """Get details of a specific GitHub App installation."""
    installation = db.github_installations.find_one({"_id": installation_id})
    if not installation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Installation {installation_id} not found",
        )
    return installation
