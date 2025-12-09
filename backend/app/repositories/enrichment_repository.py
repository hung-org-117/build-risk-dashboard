"""Enrichment Repository repository for database operations."""

from typing import Any, Dict, List, Optional

from pymongo.database import Database

from app.entities.enrichment_repository import EnrichmentRepository
from .base import BaseRepository


class EnrichmentRepositoryRepository(BaseRepository[EnrichmentRepository]):
    """Repository for EnrichmentRepository entities (Dataset enrichment flow)."""

    def __init__(self, db: Database):
        super().__init__(db, "enrichment_repositories", EnrichmentRepository)
        # Index on dataset_id for fast lookups (not unique - allows duplicates)
        self.collection.create_index("dataset_id", background=True)

    def find_by_dataset_and_full_name(
        self, dataset_id: str, full_name: str
    ) -> Optional[EnrichmentRepository]:
        """Find a repository by dataset and full name."""
        return self.find_one(
            {
                "dataset_id": self._to_object_id(dataset_id),
                "full_name": full_name,
            }
        )

    def list_by_dataset(
        self, dataset_id: str, skip: int = 0, limit: int = 0
    ) -> tuple[List[EnrichmentRepository], int]:
        """List repositories for a dataset with pagination."""
        return self.paginate(
            {"dataset_id": self._to_object_id(dataset_id)},
            sort=[("created_at", -1)],
            skip=skip,
            limit=limit,
        )

    def create_for_dataset(
        self, dataset_id: str, full_name: str, ci_provider: str
    ) -> EnrichmentRepository:
        """Create a new enrichment repository for a dataset."""
        repo = EnrichmentRepository(
            dataset_id=self._to_object_id(dataset_id),
            full_name=full_name,
            ci_provider=ci_provider,
        )
        return self.insert_one(repo)
