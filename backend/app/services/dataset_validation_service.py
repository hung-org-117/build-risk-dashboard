"""Service for dataset validation operations."""

from bson import ObjectId
from fastapi import HTTPException
from pymongo.database import Database

from app.core.redis import get_async_redis
from app.entities.dataset import DatasetProject, DatasetValidationStatus
from app.repositories.dataset_build_repository import DatasetBuildRepository
from app.repositories.dataset_repository import DatasetRepository
from app.tasks.dataset_validation import dataset_validation_orchestrator


class DatasetValidationService:
    """Service handling dataset validation operations."""

    def __init__(self, db: Database):
        self.db = db
        self.dataset_repo = DatasetRepository(db)
        self.build_repo = DatasetBuildRepository(db)

    def _get_dataset_or_404(self, dataset_id: str) -> DatasetProject:
        """Get dataset or raise 404."""

        dataset = self.dataset_repo.find_one({"_id": ObjectId(dataset_id)})
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        return dataset

    async def start_validation(self, dataset_id: str) -> dict:
        """Start async validation of builds in a dataset."""
        dataset = self._get_dataset_or_404(dataset_id)

        if dataset.validation_status == DatasetValidationStatus.VALIDATING:
            raise HTTPException(status_code=400, detail="Validation is already in progress")

        mapped_fields = dataset.mapped_fields or {}
        if not mapped_fields.build_id or not mapped_fields.repo_name:
            raise HTTPException(
                status_code=400,
                detail="Dataset mapping not configured. Please map build_id and repo_name columns.",
            )

        # Clear any existing cancel flag before starting/resuming
        redis = await get_async_redis()
        await redis.delete(f"dataset_validation:{dataset_id}:cancelled")

        task = dataset_validation_orchestrator.delay(dataset_id)
        return {"task_id": task.id, "message": "Validation started"}

    def get_validation_status(self, dataset_id: str) -> dict:
        """Get current validation progress and status."""
        dataset = self._get_dataset_or_404(dataset_id)

        return {
            "dataset_id": dataset_id,
            "status": dataset.validation_status or DatasetValidationStatus.PENDING,
            "progress": dataset.validation_progress or 0,
            "task_id": dataset.validation_task_id,
            "started_at": dataset.validation_started_at,
            "completed_at": dataset.validation_completed_at,
            "error": dataset.validation_error,
            "stats": dataset.validation_stats,
        }

    async def cancel_validation(self, dataset_id: str) -> dict:
        """Cancel ongoing validation (resumable)."""
        dataset = self._get_dataset_or_404(dataset_id)

        if dataset.validation_status != DatasetValidationStatus.VALIDATING:
            raise HTTPException(status_code=400, detail="No validation in progress")

        redis = await get_async_redis()
        await redis.set(
            f"dataset_validation:{dataset_id}:cancelled",
            "1",
            ex=3600,
        )

        # Update status to CANCELLED (allows resume)
        self.dataset_repo.update_one(
            dataset_id,
            {"validation_status": DatasetValidationStatus.CANCELLED},
        )

        return {"message": "Validation paused. You can resume later.", "can_resume": True}

    async def reset_validation(self, dataset_id: str) -> dict:
        """Reset validation state and delete build records."""
        self._get_dataset_or_404(dataset_id)

        # Cancel any running task
        redis = await get_async_redis()
        await redis.set(f"dataset_validation:{dataset_id}:cancelled", "1", ex=3600)

        # Reset validation status
        self.dataset_repo.update_one(
            dataset_id,
            {
                "validation_status": "pending",
                "validation_progress": 0,
                "validation_task_id": None,
                "validation_error": None,
                "setup_step": 2,
            },
        )

        # Delete all build records for this dataset
        deleted_count = self.build_repo.delete_by_dataset(dataset_id)

        return {"message": f"Reset validation. Deleted {deleted_count} build records."}
