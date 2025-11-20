"""Repository repository for database operations"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo.database import Database

from .base import BaseRepository


class ImportedRepositoryRepository(BaseRepository):
    """Repository for repository entities (yes, repo of repos!)"""

    def __init__(self, db: Database):
        super().__init__(db, "repositories")

    def find_by_full_name(self, provider: str, full_name: str) -> Optional[Dict]:
        """Find a repository by provider and full name"""
        return self.find_one({"provider": provider, "full_name": full_name})

    def list_by_user(self, user_id: Optional[str] = None) -> List[Dict]:
        """List repositories for a user or all if no user specified"""
        query: Dict[str, Any] = {}
        if user_id is not None:
            query["user_id"] = self._to_object_id(user_id)
        return self.find_many(query, sort=[("created_at", -1)])

    def upsert_repository(
        self,
        *,
        user_id: Optional[str],
        provider: str,
        full_name: str,
        default_branch: str,
        is_private: bool,
        main_lang: Optional[str],
        github_repo_id: Optional[int],
        metadata: Dict[str, Any],
        last_scanned_at: Optional[datetime] = None,
        installation_id: Optional[str] = None,
        test_frameworks: Optional[List[str]] = None,
        source_languages: Optional[List[str]] = None,
        ci_provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert or update a repository"""
        now = datetime.now(timezone.utc)
        existing = self.find_by_full_name(provider, full_name)

        owner_id = self._to_object_id(user_id) if user_id else None

        document = {
            "user_id": owner_id,
            "provider": provider,
            "full_name": full_name,
            "default_branch": default_branch,
            "is_private": is_private,
            "main_lang": main_lang,
            "github_repo_id": github_repo_id,
            "metadata": metadata,
            "updated_at": now,
        }

        # Preserve existing settings
        if existing:
            document["sync_status"] = existing.get("sync_status", "healthy")
            document["ci_token_status"] = existing.get("ci_token_status", "valid")
            document["test_frameworks"] = existing.get("test_frameworks", [])
            document["source_languages"] = existing.get("source_languages", [])
            document["last_sync_error"] = existing.get("last_sync_error")
            document["notes"] = existing.get("notes")
            # Only update ci_provider if explicitly provided
            if ci_provider is not None:
                document["ci_provider"] = ci_provider
            else:
                document["ci_provider"] = existing.get("ci_provider", "github_actions")
        else:
            document["sync_status"] = "healthy"
            document["ci_token_status"] = "valid"
            document["test_frameworks"] = test_frameworks or []
            document["source_languages"] = source_languages or []
            document["ci_provider"] = ci_provider or "github_actions"
            document["last_sync_error"] = None
            document["notes"] = None

        # Update config fields if explicitly provided for existing repos
        if existing:
            if test_frameworks is not None:
                document["test_frameworks"] = test_frameworks
            if source_languages is not None:
                document["source_languages"] = source_languages

        # Handle installation_id
        if installation_id is not None:
            document["installation_id"] = installation_id
        elif existing:
            document["installation_id"] = existing.get("installation_id")

        # Handle last_scanned_at
        if last_scanned_at is not None:
            document["last_scanned_at"] = last_scanned_at
        elif existing:
            document["last_scanned_at"] = existing.get("last_scanned_at")
        else:
            document["last_scanned_at"] = None

        if existing:
            self.collection.update_one({"_id": existing["_id"]}, {"$set": document})
            return self.find_by_id(existing["_id"])
        else:
            document["created_at"] = now
            return self.insert_one(document)

    def update_repository(
        self, repo_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update repository fields"""
        payload = updates.copy()
        payload["updated_at"] = datetime.now(timezone.utc)
        return self.update_one(repo_id, payload)
