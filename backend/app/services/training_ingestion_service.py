"""
Training Ingestion Service.

Handles Phase 1 of the Training Pipeline:
- Starting ingestion for a scenario
- Listing ingestion builds (with resource status)
- Retrying failed ingestion builds
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from pymongo.database import Database

from app.dtos.training_scenario import (
    TrainingIngestionBuildListResponse,
    TrainingIngestionBuildResponse,
)
from app.entities.training_ingestion_build import IngestionStatus
from app.entities.training_scenario import ScenarioStatus
from app.repositories.training_ingestion_build import TrainingIngestionBuildRepository
from app.repositories.training_scenario import TrainingScenarioRepository

logger = logging.getLogger(__name__)


class TrainingIngestionService:
    """Service for Training Ingestion operations."""

    def __init__(self, db: Database):
        self.db = db
        self.scenario_repo = TrainingScenarioRepository(db)
        self.ingestion_build_repo = TrainingIngestionBuildRepository(db)

    def start_ingestion(self, scenario_id: str, user_id: str) -> Dict[str, Any]:
        """Phase 1: Start ingestion."""
        from app.tasks.training_ingestion import start_scenario_ingestion

        scenario = self.scenario_repo.find_by_id(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

        # Allow retry if Failed or Queued
        if scenario.status not in [
            ScenarioStatus.QUEUED.value,
            ScenarioStatus.FAILED.value,
            ScenarioStatus.INGESTED.value,
        ]:
            raise HTTPException(
                status_code=400,
                detail=f"Scenario cannot start ingestion in current status: {scenario.status}",
            )

        res = start_scenario_ingestion.delay(scenario_id)
        return {"status": "queued", "task_id": res.id}

    def retry_ingestion(self, scenario_id: str, user_id: str) -> Dict[str, Any]:
        """Retry failed ingestion builds."""
        from app.tasks.training_ingestion import reingest_failed_builds

        scenario = self.scenario_repo.find_by_id(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

        # Allow retry if Failed or Ingested (partial failure)
        if scenario.status not in [
            ScenarioStatus.FAILED.value,
            ScenarioStatus.INGESTED.value,
        ]:
            raise HTTPException(
                status_code=400,
                detail=f"Scenario cannot retry ingestion in current status: {scenario.status}",
            )

        res = reingest_failed_builds.delay(scenario_id)
        return {"status": "queued", "task_id": res.id}

    def get_ingestion_builds(
        self,
        scenario_id: str,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        status_filter: Optional[str] = None,
    ) -> TrainingIngestionBuildListResponse:
        """
        List ingestion builds for a scenario (Phase 1).
        """
        # Verify scenario exists
        scenario = self.scenario_repo.find_by_id(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

        # Convert status filter to enum
        status_enum = None
        if status_filter:
            try:
                status_enum = IngestionStatus(status_filter)
            except ValueError:
                pass

        builds, total = self.ingestion_build_repo.find_by_scenario(
            scenario_id=scenario_id,
            status_filter=status_enum,
            skip=skip,
            limit=limit,
        )

        items = []
        for build in builds:
            items.append(
                TrainingIngestionBuildResponse(
                    id=str(build.id),
                    ci_run_id=build.ci_run_id or "",
                    commit_sha=build.commit_sha or "",
                    repo_full_name=build.repo_full_name or "",
                    status=(
                        build.status.value
                        if hasattr(build.status, "value")
                        else build.status
                    ),
                    resource_status=build.resource_status or {},
                    required_resources=build.required_resources or [],
                    ingestion_error=build.ingestion_error,
                    created_at=(
                        build.created_at.isoformat() if build.created_at else None
                    ),
                    ingested_at=(
                        build.ingested_at.isoformat() if build.ingested_at else None
                    ),
                )
            )

        return TrainingIngestionBuildListResponse(
            items=items,
            total=total,
            page=(skip // limit) + 1 if limit > 0 else 1,
            size=limit,
        )
