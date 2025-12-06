import csv
import logging
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Optional, Sequence
from uuid import uuid4

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.dtos import (
    DatasetCreateRequest,
    DatasetListResponse,
    DatasetResponse,
    DatasetUpdateRequest,
)
from app.repositories.dataset_repository import DatasetRepository

logger = logging.getLogger(__name__)
DATASET_DIR = Path("../repo-data/datasets")
DATASET_DIR.mkdir(parents=True, exist_ok=True)
REQUIRED_MAPPING_FIELDS = ["build_id", "commit_sha", "repo_name"]


EXAMPLE_DATASETS = [
    {
        "name": "Mobile CI builds Q1",
        "description": "CSV export from GitHub Actions pipelines for the mobile app.",
        "file_name": "mobile_ci_builds_q1.csv",
        "source": "User upload",
        "rows": 12844,
        "size_mb": 42.1,
        "columns": [
            "build_id",
            "repo",
            "commit",
            "branch",
            "status",
            "duration_minutes",
            "started_at",
            "author",
            "tests_failed",
            "tests_total",
            "runner_os",
        ],
        "mapped_fields": {
            "build_id": "build_id",
            "commit_sha": "commit",
            "repo_name": "repo",
            "timestamp": "started_at",
        },
        "stats": {
            "coverage": 0.93,
            "missing_rate": 0.02,
            "duplicate_rate": 0.01,
            "build_coverage": 0.88,
        },
        "tags": ["CSV", "GitHub Actions", "Mobile"],
        "selected_template": "reliability",
        "selected_features": [
            "build_duration_minutes",
            "failed_test_count",
            "test_flakiness_index",
            "gh_repo_age",
        ],
        "preview": [
            {
                "build_id": "GA_235111",
                "repo": "app/mobile",
                "commit": "3bafc9d",
                "status": "success",
                "duration_minutes": 12.4,
                "started_at": "2024-06-01T07:34:00Z",
            },
            {
                "build_id": "GA_235112",
                "repo": "app/mobile",
                "commit": "1c0d92a",
                "status": "failed",
                "duration_minutes": 18.2,
                "started_at": "2024-06-01T08:12:00Z",
            },
            {
                "build_id": "GA_235113",
                "repo": "app/mobile",
                "commit": "b17f223",
                "status": "success",
                "duration_minutes": 10.9,
                "started_at": "2024-06-01T09:05:00Z",
            },
        ],
    },
    {
        "name": "Platform delivery risk",
        "description": "Build and commit level signals for the platform services.",
        "file_name": "platform_delivery_risk.csv",
        "source": "User upload",
        "rows": 8341,
        "size_mb": 27.3,
        "columns": [
            "build_id",
            "repository",
            "commit_sha",
            "status",
            "duration",
            "queued_at",
            "started_at",
            "finished_at",
            "tests_count",
            "tests_failed",
            "trigger",
            "actor",
        ],
        "mapped_fields": {
            "build_id": "build_id",
            "commit_sha": "commit_sha",
            "repo_name": "repository",
            "timestamp": "started_at",
        },
        "stats": {
            "coverage": 0.9,
            "missing_rate": 0.04,
            "duplicate_rate": 0.02,
            "build_coverage": 0.82,
        },
        "tags": ["Delivery risk", "Backend"],
        "selected_template": "delivery",
        "selected_features": [
            "lead_time",
            "deployment_frequency",
            "commit_churn",
            "build_duration_minutes",
        ],
        "preview": [
            {
                "build_id": "CICD_99331",
                "repository": "platform/api",
                "commit_sha": "8e12b5f",
                "status": "success",
                "duration": 14.1,
                "started_at": "2024-05-12T06:30:00Z",
            },
            {
                "build_id": "CICD_99332",
                "repository": "platform/api",
                "commit_sha": "c7d0f2a",
                "status": "failed",
                "duration": 22.6,
                "started_at": "2024-05-12T08:45:00Z",
            },
            {
                "build_id": "CICD_99333",
                "repository": "platform/worker",
                "commit_sha": "a97d141",
                "status": "success",
                "duration": 16.3,
                "started_at": "2024-05-13T11:10:00Z",
            },
        ],
    },
]


class DatasetService:
    def __init__(self, db: Database):
        self.db = db
        self.repo = DatasetRepository(db)

    def _serialize(self, dataset) -> DatasetResponse:
        # Ensure nested models are converted to plain data for Pydantic response DTO
        payload = (
            dataset.model_dump(by_alias=True)
            if hasattr(dataset, "model_dump")
            else dataset
        )
        return DatasetResponse.model_validate(payload)

    def _validate_required_mapping(
        self, mapping: Dict[str, Optional[str]], columns: Sequence[str]
    ) -> None:
        """Ensure required fields are mapped to existing columns."""
        missing = []
        for field in REQUIRED_MAPPING_FIELDS:
            column = mapping.get(field)
            if not column or column not in columns:
                missing.append(field)
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Required mapping fields are missing or invalid",
                    "missing": missing,
                },
            )

    def seed_example_datasets(self, user_id: str) -> None:
        """Insert example datasets for a user if none exist."""
        if not user_id:
            return

        try:
            existing = self.repo.count({"user_id": self.repo._to_object_id(user_id)})
        except Exception as e:
            logger.warning("Failed to count datasets for seeding: %s", e)
            existing = 0

        if existing > 0:
            return

        now = datetime.now(timezone.utc)
        documents = []
        for dataset in EXAMPLE_DATASETS:
            documents.append(
                {
                    **dataset,
                    "user_id": ObjectId(user_id),
                    "created_at": now,
                    "updated_at": now,
                }
            )

        try:
            self.repo.insert_many(documents)
        except Exception as e:
            logger.warning("Failed to seed example datasets: %s", e)

    def list_datasets(
        self, user_id: str, skip: int = 0, limit: int = 20, q: Optional[str] = None
    ) -> DatasetListResponse:
        """List datasets for the current user."""
        self.seed_example_datasets(user_id)
        datasets, total = self.repo.list_by_user(user_id, skip=skip, limit=limit, q=q)
        return DatasetListResponse(
            total=total,
            skip=skip,
            limit=limit,
            items=[self._serialize(ds) for ds in datasets],
        )

    def get_dataset(self, dataset_id: str, user_id: str) -> DatasetResponse:
        dataset = self.repo.find_by_id(dataset_id)
        if not dataset or (dataset.user_id and str(dataset.user_id) != user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
        return self._serialize(dataset)

    def create_dataset(
        self, user_id: str, payload: DatasetCreateRequest
    ) -> DatasetResponse:
        now = datetime.now(timezone.utc)
        data = payload.model_dump(exclude_none=True)
        data["user_id"] = ObjectId(user_id) if user_id else None
        data["created_at"] = now
        data["updated_at"] = now
        if data.get("mapped_fields") and data.get("columns"):
            self._validate_required_mapping(data["mapped_fields"], data["columns"])
        dataset = self.repo.insert_one(data)
        return self._serialize(dataset)

    def update_dataset(
        self, dataset_id: str, user_id: str, payload: DatasetUpdateRequest
    ) -> DatasetResponse:
        dataset = self.repo.find_by_id(dataset_id)
        if not dataset or (dataset.user_id and str(dataset.user_id) != user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

        payload_dict = payload.model_dump(exclude_none=True)
        updates = {}

        if "name" in payload_dict:
            updates["name"] = payload_dict["name"]
        if "description" in payload_dict:
            updates["description"] = payload_dict["description"]
        if "tags" in payload_dict:
            updates["tags"] = payload_dict["tags"]
        if "selected_template" in payload_dict:
            updates["selected_template"] = payload_dict["selected_template"]
        if "selected_features" in payload_dict:
            updates["selected_features"] = payload_dict["selected_features"] or []

        if "mapped_fields" in payload_dict:
            merged = {}
            if getattr(dataset, "mapped_fields", None):
                merged.update(dataset.mapped_fields.model_dump())
            merged.update(payload_dict["mapped_fields"])
            updates["mapped_fields"] = merged
            self._validate_required_mapping(updates["mapped_fields"], dataset.columns)

        if "stats" in payload_dict:
            merged_stats = {}
            if getattr(dataset, "stats", None):
                merged_stats.update(dataset.stats.model_dump())
            merged_stats.update(payload_dict["stats"])
            updates["stats"] = merged_stats

        if not updates:
            return self._serialize(dataset)

        updates["updated_at"] = datetime.now(timezone.utc)
        updated = self.repo.update_one(dataset_id, updates)
        return self._serialize(updated or dataset)

    def _guess_mapping(self, columns: Sequence[str]) -> Dict[str, Optional[str]]:
        """Best-effort mapping for required fields based on column names."""
        def find_match(options: Sequence[str]) -> Optional[str]:
            lowered = [c.lower() for c in columns]
            for opt in options:
                if opt in lowered:
                    return columns[lowered.index(opt)]
            return None

        return {
            "build_id": find_match(
                ["build_id", "build id", "id", "workflow_run_id", "run_id"]
            ),
            "commit_sha": find_match(
                ["commit_sha", "commit sha", "commit", "sha", "revision"]
            ),
            "repo_name": find_match(
                ["repo", "repository", "repo_name", "full_name", "project"]
            ),
            "timestamp": find_match(
                ["timestamp", "started_at", "queued_at", "created_at", "time", "date"]
            ),
        }

    def create_from_upload(
        self,
        user_id: str,
        filename: str,
        upload_file,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
    ) -> DatasetResponse:
        """
        Create a dataset record from an uploaded CSV, streaming to disk to avoid large memory use.

        `upload_file` should be a file-like object (e.g., Starlette UploadFile).
        """
        temp_path = DATASET_DIR / f"tmp_{uuid4()}_{filename}"
        size_bytes = 0

        # Stream to disk
        try:
            with temp_path.open("wb") as out_f:
                while True:
                    chunk = upload_file.read(1024 * 1024)
                    if not chunk:
                        break
                    size_bytes += len(chunk)
                    out_f.write(chunk)
        except Exception as exc:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to persist uploaded file: {exc}",
            )

        # Parse header and preview from disk
        try:
            with temp_path.open("r", newline="", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                try:
                    header = next(reader)
                except StopIteration:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail="CSV file is empty"
                    )

                columns = [col.strip() for col in header if col]
                if not columns:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="CSV header is missing or invalid",
                    )

                preview = []
                row_count = 0
                for row in reader:
                    row_count += 1
                    if len(preview) < 3:
                        entry = {}
                        for idx, col in enumerate(columns):
                            entry[col] = row[idx] if idx < len(row) else ""
                        preview.append(entry)
        except HTTPException:
            temp_path.unlink(missing_ok=True)
            raise
        except Exception as exc:
            temp_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse CSV: {exc}",
            )

        mapping = self._guess_mapping(columns)
        self._validate_required_mapping(mapping, columns)

        size_mb = round(size_bytes / 1024 / 1024, 2)
        coverage = len([v for v in mapping.values() if v]) / 4 if mapping else 0

        now = datetime.now(timezone.utc)
        document: Dict[str, Any] = {
            "user_id": ObjectId(user_id),
            "name": name or filename.rsplit(".", 1)[0],
            "description": description,
            "file_name": filename,
            "source": "upload",
            "rows": row_count,
            "size_mb": size_mb,
            "columns": columns,
            "mapped_fields": mapping,
            "stats": {
                "coverage": coverage,
                "missing_rate": 0.0,
                "duplicate_rate": 0.0,
                "build_coverage": coverage,
            },
            "tags": list(tags or []),
            "selected_template": None,
            "selected_features": [],
            "preview": preview,
            "created_at": now,
            "updated_at": now,
        }

        dataset = self.repo.insert_one(document)

        final_path = DATASET_DIR / f"{dataset.id}_{filename}"
        try:
            temp_path.rename(final_path)
        except Exception as e:
            logger.warning("Failed to move uploaded dataset file into place: %s", e)
            # keep temp file if move fails

        return self._serialize(dataset)
