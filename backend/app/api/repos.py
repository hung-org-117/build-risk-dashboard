"""Repository management endpoints."""

from __future__ import annotations

from typing import Dict, List

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pymongo.database import Database

from app.database.mongo import get_db
from app.dtos import (
    RepoDetailResponse,
    RepoImportRequest,
    RepoResponse,
    RepoSuggestionListResponse,
    RepoUpdateRequest,
)
from app.middleware.auth import get_current_user
from app.services.github.github_client import (
    get_pipeline_github_client,
    get_user_github_client,
    get_app_github_client,
    get_public_github_client,
)
from app.services.pipeline_exceptions import (
    PipelineConfigurationError,
    PipelineRetryableError,
)
from app.services.pipeline_store_service import PipelineStore

router = APIRouter(prefix="/repos", tags=["Repositories"])


def _prepare_repo_payload(doc: dict) -> dict:
    """Prepare repository document for Pydantic validation with computed fields."""
    payload = doc.copy()
    # PyObjectId in Pydantic will auto-handle _id and user_id conversion

    # Set defaults for optional fields
    payload.setdefault("ci_provider", "github_actions")
    payload.setdefault("monitoring_enabled", True)
    payload.setdefault("sync_status", "healthy")
    payload.setdefault("webhook_status", "inactive")
    payload.setdefault("ci_token_status", "valid")

    # Normalize tracked branches
    branches = payload.get("tracked_branches") or []
    default_branch = payload.get("default_branch")
    if not branches and default_branch:
        branches = [default_branch]
    payload["tracked_branches"] = branches

    # Sync status logic
    if payload.get("monitoring_enabled") is False:
        payload["sync_status"] = "disabled"

    payload["total_builds_imported"] = payload.get("total_builds_imported", 0)
    return payload


def _serialize_repo(doc: dict) -> RepoResponse:
    return RepoResponse.model_validate(_prepare_repo_payload(doc))


def _serialize_repo_detail(doc: dict) -> RepoDetailResponse:
    payload = _prepare_repo_payload(doc)
    payload["metadata"] = doc.get("metadata")
    return RepoDetailResponse.model_validate(payload)


def _normalize_branches(branches: List[str]) -> List[str]:
    seen: Dict[str, bool] = {}
    normalized: List[str] = []
    for branch in branches:
        value = (branch or "").strip()
        if not value or value in seen:
            continue
        seen[value] = True
        normalized.append(value)
    return normalized


@router.post(
    "/sync", response_model=RepoSuggestionListResponse, status_code=status.HTTP_200_OK
)
def sync_repositories(
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Sync available repositories from GitHub (User OAuth + App Installations)."""
    user_id = str(current_user["_id"])
    store = PipelineStore(db)

    # Track seen repos to avoid duplicates
    seen_repos = set()

    # Fetch user's GitHub login from OAuth identity
    identity = db.oauth_identities.find_one(
        {"user_id": ObjectId(user_id), "provider": "github"}
    )

    # 1. Fetch from User OAuth (if available)
    if identity:
        try:
            with get_user_github_client(db, user_id) as gh:
                user_repos = gh.list_authenticated_repositories(per_page=100)
                for repo in user_repos:
                    full_name = repo.get("full_name")
                    if not full_name:
                        continue

                    store.upsert_available_repository(
                        user_id=user_id,
                        repo_data=repo,
                        installation_id=None,  # Will be updated if found in app
                    )
                    seen_repos.add(full_name)
        except Exception as e:
            # Check for expired token (401)
            # PipelineRetryableError wraps httpx.HTTPStatusError
            if isinstance(e, PipelineRetryableError) and "401" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="GitHub token expired or revoked. Please reconnect.",
                    headers={"x-auth-error": "github_token_expired"},
                )

            # Raise exception if user has connected but sync fails
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to sync user repositories: {str(e)}",
            )

    # 2. Fetch from GitHub App Installations (if available)
    github_login = (identity or {}).get("profile", {}).get("login")

    if github_login:
        # Find installations for this user or their orgs
        installations = db.github_installations.find({"account_login": github_login})
        for inst in installations:
            inst_id = inst["installation_id"]
            try:
                with get_app_github_client(db, inst_id) as gh:
                    # List repos for this installation
                    resp = gh._rest_request(
                        "GET", "/installation/repositories", params={"per_page": 100}
                    )
                    app_repos = resp.get("repositories", [])

                    for repo in app_repos:
                        full_name = repo.get("full_name")
                        if not full_name:
                            continue

                        store.upsert_available_repository(
                            user_id=user_id, repo_data=repo, installation_id=inst_id
                        )
                        seen_repos.add(full_name)
            except Exception as e:
                # Raise exception if app sync fails
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to sync app repositories for installation {inst_id}: {str(e)}",
                )

    # Remove repositories that were not found in this sync
    store.delete_stale_available_repositories(user_id, list(seen_repos))

    # Return updated list
    return discover_repositories(db=db, current_user=current_user, q=None, limit=50)


@router.post(
    "/import", response_model=RepoResponse, status_code=status.HTTP_201_CREATED
)
def import_repository(
    payload: RepoImportRequest,
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Register a repository for ingestion."""
    user_id = payload.user_id or str(current_user["_id"])
    store = PipelineStore(db)

    # Check if we have this repo in available_repositories to get installation_id
    available_repo = db.available_repositories.find_one(
        {"user_id": ObjectId(user_id), "full_name": payload.full_name}
    )

    installation_id = payload.installation_id
    if available_repo and available_repo.get("installation_id"):
        installation_id = available_repo.get("installation_id")

    # Enforce GitHub App Installation
    if not installation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This repository must be installed via the GitHub App to be imported. Please install the App for this repository first.",
        )

    try:
        with get_app_github_client(db, installation_id) as gh:
            repo_data = gh.get_repository(payload.full_name)
    except PipelineConfigurationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {str(e)}. Please ensure you have connected GitHub or installed the App.",
        )

    is_private = bool(repo_data.get("private"))
    repo_doc = store.upsert_repository(
        user_id=user_id,
        provider=payload.provider,
        full_name=payload.full_name,
        default_branch=repo_data.get("default_branch", "main"),
        is_private=bool(repo_data.get("private")),
        main_lang=repo_data.get("language"),
        github_repo_id=repo_data.get("id"),
        metadata=repo_data,
        installation_id=installation_id,
        last_scanned_at=None,
    )

    # Trigger Initial Scan Job (Celery)
    from app.tasks.ingestion import trigger_initial_scan

    trigger_initial_scan.delay(str(repo_doc["_id"]))

    return _serialize_repo(repo_doc)


@router.get("/", response_model=list[RepoResponse])
def list_repositories(
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    user_id: str | None = Query(default=None, description="Filter by owner id"),
):
    """List tracked repositories."""
    # If user_id not specified, default to current user's repositories
    filter_user_id = user_id or str(current_user["_id"])

    store = PipelineStore(db)
    repos = store.list_repositories(user_id=filter_user_id)
    return [_serialize_repo(repo) for repo in repos]


@router.get("/available", response_model=RepoSuggestionListResponse)
def discover_repositories(
    q: str | None = Query(
        default=None,
        description="Optional filter by name",
    ),
    limit: int = Query(default=50, ge=1, le=100),
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List available repositories from cache (sync first to update)."""
    store = PipelineStore(db)
    user_id = str(current_user["_id"])

    # Get already tracked repos to mark them
    tracked = {
        repo.get("full_name") for repo in store.list_repositories(user_id=user_id)
    }

    # Get available repos from DB
    available_repos = store.list_available_repositories(user_id=user_id)

    # Filter by query
    if q:
        query = q.lower().strip()
        available_repos = [
            r for r in available_repos if query in r.get("full_name", "").lower()
        ]

    items = []
    for repo in available_repos[:limit]:
        full_name = repo.get("full_name")
        if not full_name:
            continue

        items.append(
            {
                "full_name": full_name,
                "description": repo.get("description"),
                "default_branch": repo.get("default_branch"),
                "private": bool(repo.get("private")),
                "owner": full_name.split("/")[0],
                "installed": full_name in tracked,
                "requires_installation": bool(repo.get("private"))
                and not repo.get("installation_id"),
                "source": "app" if repo.get("installation_id") else "owned",
                "installation_id": repo.get("installation_id"),
                "html_url": repo.get("html_url"),
            }
        )

    return RepoSuggestionListResponse(items=items)


@router.get("/{repo_id}", response_model=RepoDetailResponse)
def get_repository_detail(
    repo_id: str = Path(..., description="Repository id (Mongo ObjectId)"),
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    store = PipelineStore(db)
    repo_doc = store.get_repository(repo_id)
    if not repo_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found"
        )

    # Verify user owns this repository
    repo_user_id = str(repo_doc.get("user_id", ""))
    current_user_id = str(current_user["_id"])
    if repo_user_id != current_user_id and current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this repository",
        )

    return _serialize_repo_detail(repo_doc)


@router.patch("/{repo_id}", response_model=RepoDetailResponse)
def update_repository_settings(
    repo_id: str,
    payload: RepoUpdateRequest,
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    store = PipelineStore(db)
    repo_doc = store.get_repository(repo_id)
    if not repo_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found"
        )

    # Verify user owns this repository
    repo_user_id = str(repo_doc.get("user_id", ""))
    current_user_id = str(current_user["_id"])
    if repo_user_id != current_user_id and current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this repository",
        )

    updates = payload.model_dump(exclude_unset=True)
    if "tracked_branches" in updates:
        updates["tracked_branches"] = _normalize_branches(
            updates.get("tracked_branches") or []
        )
    default_branch = updates.get("default_branch")
    if default_branch:
        existing_branches = updates.get("tracked_branches") or repo_doc.get(
            "tracked_branches", []
        )
        if default_branch not in existing_branches:
            updates["tracked_branches"] = _normalize_branches(
                existing_branches + [default_branch]
            )

    if not updates:
        updated = repo_doc
    else:
        updated = store.update_repository(repo_id, updates)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found"
            )

    return _serialize_repo_detail(updated)
