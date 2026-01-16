"""
Training Export Service.

Handles Phase 3 of the Training Pipeline (Exports):
- Creating, listing, retrieving Exports
- Triggering dataset generation tasks
- Managing export split files (listing, downloading)
"""

import logging
import zipfile
from io import BytesIO
from typing import Any, Dict, List, Tuple

from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pymongo.database import Database

from app import paths
from app.dtos.training_export import ExportCreateDTO, ExportResponse, SplitResponse
from app.entities.training_dataset_export import ExportStatus
from app.entities.training_scenario import ScenarioStatus
from app.repositories.training_dataset_export import TrainingDatasetExportRepository
from app.repositories.training_dataset_split import TrainingDatasetSplitRepository
from app.repositories.training_scenario import TrainingScenarioRepository

logger = logging.getLogger(__name__)


class TrainingExportService:
    """Service for Training Export operations."""

    def __init__(self, db: Database):
        self.db = db
        self.scenario_repo = TrainingScenarioRepository(db)
        self.export_repo = TrainingDatasetExportRepository(db)
        self.split_repo = TrainingDatasetSplitRepository(db)

    # =========================================================================
    # Export CRUD
    # =========================================================================

    def list_exports(
        self,
        scenario_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[ExportResponse], int]:
        """List all exports for a scenario."""
        # Verify scenario
        scenario = self.scenario_repo.find_by_id(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

        exports, total = self.export_repo.find_by_scenario(
            scenario_id, skip=skip, limit=limit
        )
        return [ExportResponse.from_entity(e) for e in exports], total

    def create_export(
        self,
        scenario_id: str,
        user_id: str,
        dto: ExportCreateDTO,
    ) -> ExportResponse:
        """
        Create a new export for a scenario and automatically trigger generation.

        This combines create + generate into one step for better UX.
        """
        scenario = self.scenario_repo.find_by_id(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

        # Must be Processed
        if scenario.status != ScenarioStatus.PROCESSED:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Scenario must be processed to create export. "
                    f"Current status: {scenario.status}"
                ),
            )

        # Generate default name if needed
        name = dto.name
        if not name:
            _, total = self.export_repo.find_by_scenario(scenario_id)
            name = f"Export v{total + 1}"

        export = self.export_repo.create_export(
            scenario_id=scenario_id,
            name=name,
            splitting_config=dto.splitting_config,
            preprocessing_config=dto.preprocessing_config,
            output_config=dto.output_config,
            created_by=user_id,
        )

        # Auto-trigger generation
        export_id = str(export.id)
        self.export_repo.update_status(export_id, ExportStatus.GENERATING)

        from app.tasks.training_export import generate_export_dataset

        task = generate_export_dataset.delay(
            scenario_id=scenario_id, export_id=export_id
        )
        self.export_repo.update_status(
            export_id, ExportStatus.GENERATING, task_id=task.id
        )

        # Return with updated status
        updated_export = self.export_repo.find_by_id(export_id)
        if not updated_export:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve created export"
            )
        return ExportResponse.from_entity(updated_export)

    def get_export(self, scenario_id: str, export_id: str) -> ExportResponse:
        """Get export details."""
        export = self.export_repo.find_by_id(export_id)
        if not export or str(export.scenario_id) != scenario_id:
            raise HTTPException(status_code=404, detail="Export not found")
        return ExportResponse.from_entity(export)

    def delete_export(self, scenario_id: str, export_id: str) -> bool:
        """Delete an export and its data."""
        export = self.export_repo.find_by_id(export_id)
        if not export or str(export.scenario_id) != scenario_id:
            raise HTTPException(status_code=404, detail="Export not found")

        # Delete splits first
        self.split_repo.delete_by_export(export_id)
        # Delete export
        if export.id:
            self.export_repo.delete_one(export.id)

        # TODO: Cleanup physical files if implementation allows
        # Currently files are tracked in splits, which are deleted from DB,
        # but cleanup_training_dataset_files handles scenario level.
        # Ideally, we should delete split files here too.

        return True

    # =========================================================================
    # Generation
    # =========================================================================

    def generate_export(
        self,
        scenario_id: str,
        export_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Trigger dataset generation task for an export."""
        export = self.export_repo.find_by_id(export_id)
        if not export or str(export.scenario_id) != scenario_id:
            raise HTTPException(status_code=404, detail="Export not found")

        if export.status == ExportStatus.GENERATING:
            raise HTTPException(
                status_code=400, detail="Export is already being generated"
            )

        # Update status
        self.export_repo.update_status(export_id, ExportStatus.GENERATING)

        # Dispatch Task
        from app.tasks.training_export import generate_export_dataset

        task = generate_export_dataset.delay(
            scenario_id=scenario_id, export_id=export_id
        )

        # Save task ID
        self.export_repo.update_status(
            export_id, ExportStatus.GENERATING, task_id=task.id
        )

        return {
            "success": True,
            "message": "Dataset generation started",
            "task_id": task.id,
            "export_id": export_id,
        }

    # =========================================================================
    # Splits & Files
    # =========================================================================

    def get_export_splits(
        self, scenario_id: str, export_id: str
    ) -> List[SplitResponse]:
        """Get splits for an export."""
        # Validate export access
        export = self.export_repo.find_by_id(export_id)
        if not export or str(export.scenario_id) != scenario_id:
            raise HTTPException(status_code=404, detail="Export not found")

        splits = self.split_repo.find_by_export(export_id)
        return [
            SplitResponse(
                id=str(s.id),
                export_id=str(s.export_id),
                split_type=s.split_type,
                record_count=s.record_count,
                feature_count=s.feature_count,
                class_distribution=s.class_distribution,
                group_distribution=s.group_distribution,
                file_path=s.file_path,
                file_size_bytes=s.file_size_bytes,
                file_format=s.file_format,
                generated_at=s.generated_at.isoformat(),
            )
            for s in splits
        ]

    def download_split(
        self, scenario_id: str, export_id: str, split_id: str
    ) -> FileResponse:
        """Download a split file."""
        # Validate hierarchy
        split = self.split_repo.find_by_id(split_id)
        if not split or str(split.export_id) != export_id:
            raise HTTPException(status_code=404, detail="Split not found")

        # Check export.scenario_id matches via export_id
        # Split → Export → Scenario hierarchy validation
        export = self.export_repo.find_by_id(export_id)
        if not export or str(export.scenario_id) != scenario_id:
            raise HTTPException(status_code=404, detail="Export not found for scenario")

        file_path = paths.DATA_DIR / split.file_path
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Split file not found on disk")

        return FileResponse(
            path=file_path,
            filename=file_path.name,
            media_type="application/octet-stream",
        )

    def download_all_splits(
        self, scenario_id: str, export_id: str
    ) -> StreamingResponse:
        """
        Download all splits for an export as a zip file.

        Creates an in-memory zip containing all split files with folder structure:
        - Single-split: train.parquet, val.parquet, test.parquet
        - CV: fold_id/train.parquet, fold_id/val.parquet, fold_id/test.parquet
        """
        # Validate export
        export = self.export_repo.find_by_id(export_id)
        if not export or str(export.scenario_id) != scenario_id:
            raise HTTPException(status_code=404, detail="Export not found")

        splits = self.split_repo.find_by_export(export_id)
        if not splits:
            raise HTTPException(status_code=404, detail="No splits found for export")

        # Create in-memory zip
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for split in splits:
                file_path = paths.DATA_DIR / split.file_path
                if file_path.exists():
                    # Extract relative path after export_id/
                    # e.g., "training_datasets/scenario/export/fold_1/train.parquet"
                    # -> "fold_1/train.parquet" or "train.parquet"
                    rel_parts = split.file_path.split(f"{export_id}/")
                    arcname = rel_parts[-1] if len(rel_parts) > 1 else file_path.name
                    zf.write(file_path, arcname)

        zip_buffer.seek(0)

        # Generate filename
        export_name = export.name.replace(" ", "_") if export.name else export_id[:8]
        filename = f"export_{export_name}.zip"

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
