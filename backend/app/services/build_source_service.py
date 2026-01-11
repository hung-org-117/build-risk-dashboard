"""BuildSource service - Business logic for build source management."""

import csv
import io
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from fastapi import UploadFile

from app.ci_providers.models import CIProvider
from app.entities.build_source import (
    BuildSource,
    SourceMapping,
    ValidationStats,
    ValidationStatus,
)
from app.repositories.build_source import BuildSourceRepository
from app.repositories.source_build import SourceBuildRepository
from app.repositories.source_repo_stats import SourceRepoStatsRepository

# Preview rows in response
PREVIEW_ROWS = 10


class BuildSourceService:
    """Service for managing build sources (CSV uploads)."""

    def __init__(
        self,
        build_source_repo: BuildSourceRepository,
        source_build_repo: SourceBuildRepository,
        source_repo_stats_repo: SourceRepoStatsRepository,
        upload_dir: str = "/tmp/build_sources",
    ):
        self.build_source_repo = build_source_repo
        self.source_build_repo = source_build_repo
        self.source_repo_stats_repo = source_repo_stats_repo
        self.upload_dir = upload_dir

        # Ensure upload directory exists
        os.makedirs(self.upload_dir, exist_ok=True)

    async def upload_csv(
        self,
        file: UploadFile,
        name: str,
        description: Optional[str],
        user_id: Optional[str],
    ) -> BuildSource:
        """Upload a CSV file and create a BuildSource record."""
        # Read file content
        content = await file.read()
        text = content.decode("utf-8")

        # Parse CSV
        reader = csv.DictReader(io.StringIO(text))
        rows_list = list(reader)
        columns = reader.fieldnames or []

        # Save file to disk
        file_name = file.filename or "upload.csv"
        file_path = os.path.join(self.upload_dir, f"{ObjectId()}_{file_name}")
        with open(file_path, "wb") as f:
            f.write(content)

        # Create preview (first N rows)
        preview = rows_list[:PREVIEW_ROWS]

        # Create BuildSource record
        source = BuildSource(
            user_id=ObjectId(user_id) if user_id else None,
            name=name or file_name.replace(".csv", ""),
            description=description,
            file_name=file_name,
            file_path=file_path,
            rows=len(rows_list),
            size_bytes=len(content),
            columns=list(columns),
            preview=preview,
            validation_status=ValidationStatus.PENDING,
            setup_step=1,
        )

        created = self.build_source_repo.create(source)
        return created

    def get(self, source_id: str) -> Optional[BuildSource]:
        """Get a build source by ID."""
        return self.build_source_repo.find_by_id(source_id)

    def list_all(
        self,
        skip: int = 0,
        limit: int = 20,
        q: Optional[str] = None,
    ) -> Tuple[List[BuildSource], int]:
        """List all build sources (shared among admins)."""
        return self.build_source_repo.list_all(
            skip=skip,
            limit=limit,
            q=q,
        )

    def update(
        self,
        source_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        mapped_fields: Optional[Dict[str, Any]] = None,
        ci_provider: Optional[str] = None,
    ) -> Optional[BuildSource]:
        """Update a build source."""
        update_data: Dict[str, Any] = {"updated_at": datetime.utcnow()}

        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if mapped_fields is not None:
            update_data["mapped_fields"] = SourceMapping(**mapped_fields)
        if ci_provider is not None:
            update_data["ci_provider"] = CIProvider(ci_provider)

        return self.build_source_repo.update(source_id, **update_data)

    def delete(self, source_id: str) -> bool:
        """Delete a build source and its related data."""
        source = self.build_source_repo.find_by_id(source_id)
        if not source:
            return False

        # Delete related data
        self.source_build_repo.delete_by_source(source_id)
        self.source_repo_stats_repo.delete_by_source(source_id)

        # Delete file if exists
        if source.file_path and os.path.exists(source.file_path):
            try:
                os.remove(source.file_path)
            except OSError:
                pass

        # Delete source record
        return self.build_source_repo.delete(source_id)

    def start_validation(self, source_id: str, task_id: str) -> Optional[BuildSource]:
        """Mark source as validating and set task ID."""
        return self.build_source_repo.update(
            source_id,
            validation_status=ValidationStatus.VALIDATING,
            validation_task_id=task_id,
            validation_started_at=datetime.utcnow(),
            validation_progress=0,
            validation_error=None,
        )

    def complete_validation(
        self,
        source_id: str,
        stats: ValidationStats,
        error: Optional[str] = None,
    ) -> Optional[BuildSource]:
        """Mark validation as completed or failed."""
        status = ValidationStatus.FAILED if error else ValidationStatus.COMPLETED
        return self.build_source_repo.update(
            source_id,
            validation_status=status,
            validation_completed_at=datetime.utcnow(),
            validation_progress=100,
            validation_stats=stats,
            validation_error=error,
            setup_step=2 if not error else 1,
        )

    def update_validation_progress(
        self, source_id: str, progress: int
    ) -> Optional[BuildSource]:
        """Update validation progress percentage."""
        return self.build_source_repo.update(
            source_id,
            validation_progress=min(100, max(0, progress)),
        )

    def get_repo_stats(self, source_id: str) -> List[Any]:
        """Get repository stats for a source."""
        return self.source_repo_stats_repo.find_by_source(source_id)

    def get_builds(
        self,
        source_id: str,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Any]:
        """Get builds for a source."""
        from app.entities.source_build import SourceBuildStatus

        status_enum = SourceBuildStatus(status) if status else None
        return self.source_build_repo.find_by_source(
            source_id, status=status_enum, skip=skip, limit=limit
        )
