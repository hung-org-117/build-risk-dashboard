from typing import List, Optional

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.dtos import (
    RepoDetailResponse,
    RepoImportRequest,
    RepoResponse,
    RepoSuggestionListResponse,
    RepoUpdateRequest,
)
from app.repositories.available_repository import AvailableRepositoryRepository
from app.repositories.imported_repository import ImportedRepositoryRepository
from app.services.github.github_client import get_app_github_client
from app.services.github.github_sync import sync_user_available_repos
from app.services.github.exceptions import GithubConfigurationError
from app.tasks.ingestion import import_repo


def _prepare_repo_payload(doc: dict) -> dict:
    payload = doc.copy()

    # Set defaults for optional fields
    payload.setdefault("ci_provider", "github_actions")
    payload.setdefault("sync_status", "healthy")
    payload.setdefault("ci_token_status", "valid")
    payload.setdefault("test_frameworks", [])
    payload.setdefault("source_languages", [])

    payload["total_builds_imported"] = payload.get("total_builds_imported", 0)
    return payload


def _serialize_repo(doc: dict) -> RepoResponse:
    return RepoResponse.model_validate(_prepare_repo_payload(doc))


def _serialize_repo_detail(doc: dict) -> RepoDetailResponse:
    payload = _prepare_repo_payload(doc)
    payload["metadata"] = doc.get("metadata")
    return RepoDetailResponse.model_validate(payload)


class RepositoryService:
    def __init__(self, db: Database):
        self.db = db
        self.repo_repo = ImportedRepositoryRepository(db)
        self.available_repo_repo = AvailableRepositoryRepository(db)

    def import_repository(
        self, user_id: str, payload: RepoImportRequest
    ) -> RepoResponse:
        available_repo = self.db.available_repositories.find_one(
            {"user_id": ObjectId(user_id), "full_name": payload.full_name}
        )

        installation_id = payload.installation_id
        if available_repo and available_repo.get("installation_id"):
            installation_id = available_repo.get("installation_id")

        if not installation_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This repository must be installed via the GitHub App to be imported. Please install the App for this repository first.",
            )

        # Create stub repository
        repo_doc = self.repo_repo.upsert_repository(
            user_id=user_id,
            provider=payload.provider,
            full_name=payload.full_name,
            default_branch="main",
            is_private=False,
            main_lang=None,
            github_repo_id=None,
            metadata={},
            installation_id=installation_id,
            last_scanned_at=None,
            test_frameworks=payload.test_frameworks or [],
            source_languages=payload.source_languages or [],
            ci_provider=payload.ci_provider or "github_actions",
        )

        # Trigger async import
        import_repo.delay(
            user_id=user_id,
            full_name=payload.full_name,
            installation_id=installation_id,
            provider=payload.provider,
            test_frameworks=payload.test_frameworks,
            source_languages=payload.source_languages,
            ci_provider=payload.ci_provider,
        )

        return RepoResponse.model_validate(repo_doc)

    def bulk_import_repositories(
        self, user_id: str, payloads: List[RepoImportRequest]
    ) -> List[RepoResponse]:
        results = []

        # Pre-fetch available repos to check installation_ids
        full_names = [p.full_name for p in payloads]
        available_repos = list(
            self.db.available_repositories.find(
                {"user_id": ObjectId(user_id), "full_name": {"$in": full_names}}
            )
        )
        available_map = {r["full_name"]: r for r in available_repos}

        for payload in payloads:
            target_user_id = user_id

            available_repo = available_map.get(payload.full_name)
            installation_id = payload.installation_id

            if available_repo and available_repo.get("installation_id"):
                installation_id = available_repo.get("installation_id")

            if not installation_id:
                # Skip or log
                continue

            try:
                # Create stub repository
                repo_doc = self.repo_repo.upsert_repository(
                    user_id=target_user_id,
                    provider=payload.provider,
                    full_name=payload.full_name,
                    default_branch="main",
                    is_private=False,
                    main_lang=None,
                    github_repo_id=None,
                    metadata={},
                    installation_id=installation_id,
                    last_scanned_at=None,
                    test_frameworks=payload.test_frameworks or [],
                    source_languages=payload.source_languages or [],
                    ci_provider=payload.ci_provider or "github_actions",
                )

                # Trigger async import
                import_repo.delay(
                    user_id=target_user_id,
                    full_name=payload.full_name,
                    installation_id=installation_id,
                    provider=payload.provider,
                    test_frameworks=payload.test_frameworks,
                    source_languages=payload.source_languages,
                    ci_provider=payload.ci_provider,
                )

                results.append(repo_doc)

            except Exception as e:
                # Log error and continue
                print(f"Failed to import {payload.full_name}: {e}")
                continue

        return [RepoResponse.model_validate(doc) for doc in results]

    def sync_repositories(self, user_id: str, limit: int) -> RepoSuggestionListResponse:
        """Sync available repositories from GitHub App Installations."""
        try:
            sync_user_available_repos(self.db, user_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to sync repositories: {str(e)}",
            )

        return self.available_repo_repo.discover_available_repositories(
            user_id=user_id, q=None, limit=limit
        )

    def list_repositories(self, user_id: str) -> List[RepoResponse]:
        """List tracked repositories."""
        repos = self.repo_repo.list_by_user(user_id)
        return [_serialize_repo(repo) for repo in repos]

    def discover_repositories(
        self, user_id: str, q: str | None, limit: int
    ) -> RepoSuggestionListResponse:
        """List available repositories."""
        items = self.repo_repo.discover_available_repositories(
            user_id=user_id, q=q, limit=limit
        )
        return RepoSuggestionListResponse(items=items)

    def get_repository_detail(
        self, repo_id: str, current_user: dict
    ) -> RepoDetailResponse:
        repo_doc = self.repo_repo.get_repository(repo_id)
        if not repo_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found"
            )

        # Verify user owns this repository
        repo_user_id = str(repo_doc.get("user_id", ""))
        current_user_id = str(current_user["_id"])
        if repo_user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this repository",
            )

        return _serialize_repo_detail(repo_doc)

    def update_repository_settings(
        self, repo_id: str, payload: RepoUpdateRequest, current_user: dict
    ) -> RepoDetailResponse:
        repo_doc = self.repo_repo.get_repository(repo_id)
        if not repo_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found"
            )

        # Verify user owns this repository
        repo_user_id = str(repo_doc.get("user_id", ""))
        current_user_id = str(current_user["_id"])
        if repo_user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this repository",
            )

        updates = payload.model_dump(exclude_unset=True)

        if not updates:
            updated = repo_doc
        else:
            updated = self.repo_repo.update_repository(repo_id, updates)
            if not updated:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found"
                )

        return _serialize_repo_detail(updated)
