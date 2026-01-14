"""
Training Scenario Service - Business logic for Training Pipeline.

Handles:
- Scenario CRUD operations
- Pipeline orchestration (Ingestion → Processing → Generation)
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.dtos.training_scenario import (
    SplittingGroupsResponse,
    TrainingScenarioCreateDTO,
    TrainingScenarioResponse,
    TrainingScenarioUpdateDTO,
)
from app.entities.enums import GroupByDimension
from app.entities.training_scenario import (
    DataSourceConfig,
    FeatureConfig,
    ScenarioStatus,
    TrainingScenario,
)
from app.repositories.feature_vector import FeatureVectorRepository
from app.repositories.raw_repository import RawRepositoryRepository
from app.repositories.sonar_commit_scan import SonarCommitScanRepository
from app.repositories.training_dataset_export import TrainingDatasetExportRepository
from app.repositories.training_dataset_split import TrainingDatasetSplitRepository
from app.repositories.training_enrichment_build import TrainingEnrichmentBuildRepository
from app.repositories.training_ingestion_build import TrainingIngestionBuildRepository
from app.repositories.training_scenario import TrainingScenarioRepository
from app.repositories.trivy_commit_scan import TrivyCommitScanRepository
from app.services.splitting_strategy_service import SplittingStrategyService

logger = logging.getLogger(__name__)


class TrainingScenarioService:
    """Service for Training Scenario operations."""

    def __init__(self, db: Database):
        self.db = db
        self.scenario_repo = TrainingScenarioRepository(db)

        # Repositories for cascading deletes & lookups
        self.enrichment_build_repo = TrainingEnrichmentBuildRepository(db)
        self.ingestion_build_repo = TrainingIngestionBuildRepository(db)
        self.export_repo = TrainingDatasetExportRepository(db)
        self.split_repo = TrainingDatasetSplitRepository(db)
        self.feature_vector_repo = FeatureVectorRepository(db)
        self.trivy_scan_repo = TrivyCommitScanRepository(db)
        self.sonar_scan_repo = SonarCommitScanRepository(db)

    def _to_response(self, scenario: TrainingScenario) -> TrainingScenarioResponse:
        """Convert TrainingScenario entity to TrainingScenarioResponse DTO."""
        from app.dtos.training_scenario import DataSourceConfigDTO, FeatureConfigDTO

        return TrainingScenarioResponse(
            id=str(scenario.id),
            name=scenario.name,
            description=scenario.description,
            version=scenario.version,
            status=scenario.status,
            error_message=scenario.error_message,
            data_source_config=DataSourceConfigDTO(
                languages=scenario.data_source_config.languages,
                build_source_ids=getattr(
                    scenario.data_source_config, "build_source_ids", []
                ),
                date_start=scenario.data_source_config.date_start,
                date_end=scenario.data_source_config.date_end,
                conclusions=scenario.data_source_config.conclusions,
                ci_provider=scenario.data_source_config.ci_provider,
            ),
            feature_config=FeatureConfigDTO(
                dag_features=scenario.feature_config.dag_features,
                scan_metrics=scenario.feature_config.scan_metrics,
                scan_tool_config=scenario.feature_config.scan_tool_config,
                extractor_configs=scenario.feature_config.extractor_configs,
            ),
            yaml_config=scenario.yaml_config,
            builds_total=scenario.builds_total,
            builds_ingested=scenario.builds_ingested,
            builds_features_extracted=scenario.builds_features_extracted,
            builds_missing_resource=scenario.builds_missing_resource,
            builds_failed=scenario.builds_failed,
            scans_total=scenario.scans_total,
            scans_completed=scenario.scans_completed,
            scans_failed=scenario.scans_failed,
            created_by=str(scenario.created_by) if scenario.created_by else None,
            created_at=scenario.created_at,
            updated_at=scenario.updated_at,
            filtering_completed_at=scenario.filtering_completed_at,
            ingestion_completed_at=scenario.ingestion_completed_at,
            processing_completed_at=scenario.processing_completed_at,
            feature_extraction_completed=scenario.feature_extraction_completed,
            scan_extraction_completed=scenario.scan_extraction_completed,
        )

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def list_scenarios(
        self,
        skip: int = 0,
        limit: int = 20,
        status_filter: Optional[ScenarioStatus] = None,
        q: Optional[str] = None,
    ) -> Tuple[List[TrainingScenarioResponse], int]:
        """List all scenarios (shared among all admins)."""
        scenarios, total = self.scenario_repo.list_all(
            skip=skip,
            limit=limit,
            status_filter=status_filter,
            q=q,
        )
        return [self._to_response(s) for s in scenarios], total

    def get_scenario(
        self,
        scenario_id: str,
        user_id: str,
    ) -> TrainingScenarioResponse:
        """Get scenario details."""
        scenario = self.scenario_repo.find_by_id(scenario_id)
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario {scenario_id} not found",
            )

        return self._to_response(scenario)

    def create_scenario(
        self,
        user_id: str,
        data: TrainingScenarioCreateDTO,
    ) -> TrainingScenarioResponse:
        """Create a new scenario from UI config."""
        # Check for duplicate name
        existing = self.scenario_repo.find_by_name(data.name, user_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Scenario with name '{data.name}' already exists",
            )

        # Prepare Configs
        data_source_config = DataSourceConfig()
        if data.data_source_config:
            data_source_config = DataSourceConfig(
                **data.data_source_config.model_dump()
            )

        feature_config = FeatureConfig()
        if data.feature_config:
            feature_config = FeatureConfig(**data.feature_config.model_dump())

        # Create scenario entity
        # Note: splitting_config moved to TrainingDatasetExport
        scenario = TrainingScenario(
            name=data.name,
            description=data.description,
            version=data.version,
            yaml_config="",  # Deprecated
            data_source_config=data_source_config,
            feature_config=feature_config,
            status=ScenarioStatus.QUEUED,
            created_by=ObjectId(user_id),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        created = self.scenario_repo.insert_one(scenario)
        logger.info(f"Created TrainingScenario: {created.id} - {data.name}")
        return self._to_response(created)

    def update_scenario(
        self,
        scenario_id: str,
        user_id: str,
        data: TrainingScenarioUpdateDTO,
    ) -> TrainingScenarioResponse:
        """Update scenario fields."""
        scenario = self.scenario_repo.find_by_id(scenario_id)
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario {scenario_id} not found",
            )

        # Cannot update if processing rules apply (e.g. actively running)
        if scenario.status in (
            ScenarioStatus.FILTERING,
            ScenarioStatus.INGESTING,
            ScenarioStatus.PROCESSING,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update scenario while pipeline is running",
            )

        updates: Dict[str, Any] = {"updated_at": datetime.utcnow()}
        config_changed = False

        if data.name is not None:
            existing = self.scenario_repo.find_by_name(data.name, user_id)
            if existing and str(existing.id) != scenario_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Scenario with name '{data.name}' already exists",
                )
            updates["name"] = data.name

        if data.description is not None:
            updates["description"] = data.description

        if data.data_source_config is not None:
            updates["data_source_config"] = DataSourceConfig(
                **data.data_source_config.model_dump()
            ).model_dump()
            config_changed = True

        if data.feature_config is not None:
            updates["feature_config"] = FeatureConfig(
                **data.feature_config.model_dump()
            ).model_dump()
            config_changed = True

        # Note: splitting_config is now managed by TrainingDatasetExport
        # No longer stored in TrainingScenario

        if config_changed:
            # Reset status to QUEUED if config changed
            updates["status"] = ScenarioStatus.QUEUED.value

            # Reset completion flags
            updates["feature_extraction_completed"] = False
            updates["scan_extraction_completed"] = False

        updated = self.scenario_repo.update_one(scenario_id, updates)
        return self._to_response(updated)

    def delete_scenario(
        self,
        scenario_id: str,
        user_id: str,
    ) -> bool:
        """Delete a scenario and all associated data."""
        scenario = self.scenario_repo.find_by_id(scenario_id)
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario {scenario_id} not found",
            )

        # Delete associated data
        logger.info(f"Starting cascading delete for scenario {scenario_id}...")

        # 1. Delete Dataset Splits (most dependent)
        splits_deleted = self.split_repo.delete_by_scenario(scenario_id)
        logger.info(f"Deleted {splits_deleted} dataset splits")

        # 2. Delete Dataset Exports
        exports_deleted = self.export_repo.delete_by_scenario(scenario_id)
        logger.info(f"Deleted {exports_deleted} dataset exports")

        # 3. Delete Enrichment Builds
        enrichment_deleted = self.enrichment_build_repo.delete_by_scenario(scenario_id)
        logger.info(f"Deleted {enrichment_deleted} enrichment builds")

        # 4. Delete Feature Vectors (Scoped to this scenario)
        features_deleted = self.feature_vector_repo.delete_by_scenario(scenario_id)
        logger.info(f"Deleted {features_deleted} feature vectors")

        # 5. Delete Ingestion Builds
        ingestion_deleted = self.ingestion_build_repo.delete_by_scenario(scenario_id)
        logger.info(f"Deleted {ingestion_deleted} ingestion builds")

        # 6. Delete Scans (Trivy & SonarQube)
        trivy_deleted = self.trivy_scan_repo.delete_by_scenario(scenario_id)
        sonar_deleted = self.sonar_scan_repo.delete_by_scenario(scenario_id)
        logger.info(
            f"Deleted {trivy_deleted} trivy scans and {sonar_deleted} sonar scans"
        )

        # 7. Finally delete the Scenario
        self.scenario_repo.delete(scenario_id)
        logger.info(f"Deleted TrainingScenario: {scenario_id} and all related entities")
        return True

    # =========================================================================
    # Pipeline Orchestration
    # =========================================================================

    def get_scan_status(
        self,
        scenario_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Get scan status summary for a scenario.

        Returns counts of scans completed/pending/failed.
        """
        # Permission check
        scenario = self.get_scenario(scenario_id, user_id)

        return {
            "scans_total": scenario.scans_total or 0,
            "scans_completed": scenario.scans_completed or 0,
            "scans_failed": scenario.scans_failed or 0,
            "scans_pending": max(
                0,
                (scenario.scans_total or 0)
                - (scenario.scans_completed or 0)
                - (scenario.scans_failed or 0),
            ),
        }

    def get_splitting_group_values(
        self,
        scenario_id: str,
        dimension_str: str,
    ) -> SplittingGroupsResponse:
        """
        Get available group values and counts for a dimension.
        Used for populating dropdowns in splitting configuration (e.g., LOO strategy).
        """
        # Validate dimension
        try:
            dimension = GroupByDimension(dimension_str)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid grouping dimension: {dimension_str}",
            ) from None

        # Get all enrichment builds (lightweight)
        enrichment_builds, _ = self.enrichment_build_repo.find_by_scenario(
            scenario_id, limit=0
        )

        if not enrichment_builds:
            return SplittingGroupsResponse(
                group_by=dimension_str,
                groups=[],
                total_builds=0,
            )

        # Prepare minimal data for DataFrame
        data = []

        # Optimization: Fetch raw repos only if needed (for language grouping)
        raw_repos = {}
        if dimension == GroupByDimension.REPO_LANGUAGE:
            unique_repo_ids = list({str(eb.raw_repo_id) for eb in enrichment_builds})
            raw_repo_repo = RawRepositoryRepository(self.db)
            raw_repos_list = raw_repo_repo.find_by_ids(unique_repo_ids)
            raw_repos = {r.id: r for r in raw_repos_list if r}

        for eb in enrichment_builds:
            row = {
                "id": str(eb.id),
                "build_started_at": eb.build_started_at,
            }

            if dimension == GroupByDimension.REPO_LANGUAGE:
                raw_repo = raw_repos.get(eb.raw_repo_id)
                row["repo_language"] = raw_repo.main_lang if raw_repo else "other"

            # For time_of_day, we need build_hour (0-23)
            # SplittingStrategyService._create_time_of_day_bins expects 'build_hour'
            if eb.build_started_at:
                row["build_hour"] = eb.build_started_at.hour
            else:
                row["build_hour"] = 12  # Default

            data.append(row)

        df = pd.DataFrame(data)

        # Use SplittingStrategyService to compute groups
        service = SplittingStrategyService()
        result = service.get_available_groups(df, dimension)

        return SplittingGroupsResponse(**result)
