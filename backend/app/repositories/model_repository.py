"""Model Repository repository for database operations."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database

from app.entities.model_repository import ModelRepository
from .base import BaseRepository


class ModelRepositoryRepository(BaseRepository[ModelRepository]):
    """Repository for ModelRepository entities (Model training flow)."""

    def __init__(self, db: Database):
        super().__init__(db, "model_repositories", ModelRepository)
        self.collection.create_index(
            [("user_id", 1), ("full_name", 1)],
            unique=True,
            background=True,
        )

    def find_by_user_and_full_name(
        self, user_id: str, full_name: str
    ) -> Optional[ModelRepository]:
        return self.find_one(
            {
                "user_id": self._to_object_id(user_id),
                "full_name": full_name,
            }
        )

    def find_by_full_name(self, full_name: str) -> Optional[ModelRepository]:
        return self.find_one({"full_name": full_name})

    def list_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 0,
        query: Optional[Dict[str, Any]] = None,
    ) -> tuple[List[ModelRepository], int]:
        final_query: Dict[str, Any] = {"user_id": self._to_object_id(user_id)}

        if query:
            final_query.update(query)

        return self.paginate(
            final_query, sort=[("created_at", -1)], skip=skip, limit=limit
        )

    def update_repository(
        self, repo_id: str, updates: Dict[str, Any]
    ) -> Optional[ModelRepository]:
        payload = updates.copy()
        payload["updated_at"] = datetime.now(timezone.utc)
        return self.update_one(repo_id, payload)

    def upsert_repository(
        self, user_id: str, full_name: str, data: Dict[str, Any]
    ) -> ModelRepository:
        now = datetime.now(timezone.utc)

        query = {
            "user_id": self._to_object_id(user_id),
            "full_name": full_name,
        }

        update_op = {
            "$set": {**data, "updated_at": now},
            "$setOnInsert": {"created_at": now},
        }

        if "created_at" in update_op["$set"]:
            del update_op["$set"]["created_at"]

        doc = self.collection.find_one_and_update(
            query, update_op, upsert=True, return_document=ReturnDocument.AFTER
        )

        return self._to_model(doc)
