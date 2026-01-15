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
            builds_total=scenario.builds_total,
            builds_ingested=scenario.builds_ingested,
            builds_features_extracted=scenario.builds_features_extracted,
            builds_missing_resource=scenario.builds_missing_resource,
            builds_ingestion_failed=scenario.builds_ingestion_failed,
            builds_features_extracted_failed=scenario.builds_features_extracted_failed,
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

        with self.scenario_repo.transaction() as session:
            # 1. Delete Dataset Splits (most dependent)
            splits_deleted = self.split_repo.delete_by_scenario(
                scenario_id, session=session
            )
            logger.info(f"Deleted {splits_deleted} dataset splits")

            # 2. Delete Dataset Exports
            exports_deleted = self.export_repo.delete_by_scenario(
                scenario_id, session=session
            )
            logger.info(f"Deleted {exports_deleted} dataset exports")

            # 3. Delete Enrichment Builds
            enrichment_deleted = self.enrichment_build_repo.delete_by_scenario(
                scenario_id, session=session
            )
            logger.info(f"Deleted {enrichment_deleted} enrichment builds")

            # 4. Delete Feature Vectors (Scoped to this scenario)
            features_deleted = self.feature_vector_repo.delete_by_scenario(
                scenario_id, session=session
            )
            logger.info(f"Deleted {features_deleted} feature vectors")

            # 5. Delete Ingestion Builds
            ingestion_deleted = self.ingestion_build_repo.delete_by_scenario(
                scenario_id, session=session
            )
            logger.info(f"Deleted {ingestion_deleted} ingestion builds")

            # 6. Delete Scans (Trivy & SonarQube)
            # Check if repositories support session, otherwise call without
            if (
                hasattr(self.trivy_scan_repo.delete_by_scenario, "__code__")
                and "session"
                in self.trivy_scan_repo.delete_by_scenario.__code__.co_varnames
            ):
                trivy_deleted = self.trivy_scan_repo.delete_by_scenario(
                    scenario_id, session=session
                )
            else:
                trivy_deleted = self.trivy_scan_repo.delete_by_scenario(scenario_id)

            if (
                hasattr(self.sonar_scan_repo.delete_by_scenario, "__code__")
                and "session"
                in self.sonar_scan_repo.delete_by_scenario.__code__.co_varnames
            ):
                sonar_deleted = self.sonar_scan_repo.delete_by_scenario(
                    scenario_id, session=session
                )
            else:
                sonar_deleted = self.sonar_scan_repo.delete_by_scenario(scenario_id)

            logger.info(
                f"Deleted {trivy_deleted} trivy scans and {sonar_deleted} sonar scans"
            )

            # 7. Finally delete the Scenario
            self.scenario_repo.delete_one(scenario_id, session=session)

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

    def get_group_preview(
        self,
        scenario_id: str,
        user_id: str,
        group_by_str: str,
        num_bins: int = 4,
        time_slots: int = 4,
    ) -> Dict[str, Any]:
        """
        Get group distribution preview for export configuration.

        Queries FeatureVector.features for grouping features extracted by Hamilton DAG.
        Supports: repo_language, time_of_day, percentage_of_builds_before, number_of_builds_before.
        """
        # Validate group_by
        try:
            group_by_enum = GroupByDimension(group_by_str)
        except ValueError:
            return {
                "error": f"Invalid group_by: {group_by_str}",
                "valid_options": [e.value for e in GroupByDimension],
            }

        # Verify scenario access and status
        scenario = self.get_scenario(scenario_id, user_id)

        if scenario.status not in ["processed", "completed"]:
            return {
                "error": "Processing not complete",
                "groups": [],
                "total_builds": 0,
            }

        # Map group_by to feature name in FeatureVector.features
        FEATURE_MAP = {
            GroupByDimension.REPO_LANGUAGE: "repo_language",
            GroupByDimension.TIME_OF_DAY: "build_hour",
            GroupByDimension.PERCENTAGE_OF_BUILDS_BEFORE: "percentage_of_builds_before",
            GroupByDimension.NUMBER_OF_BUILDS_BEFORE: "number_of_builds_before",
        }

        feature_name = FEATURE_MAP.get(group_by_enum)
        if not feature_name:
            return {
                "error": f"Unsupported group_by: {group_by_str}",
                "groups": [],
                "total_builds": 0,
            }

        # Aggregate from FeatureVector via enrichment builds
        scenario_oid = ObjectId(scenario_id)

        # MongoDB aggregation pipeline: EnrichmentBuild → FeatureVector
        pipeline = [
            {
                "$match": {
                    "scenario_id": scenario_oid,
                    "extraction_status": "completed",
                    "feature_vector_id": {"$ne": None},
                }
            },
            {
                "$lookup": {
                    "from": "feature_vectors",
                    "localField": "feature_vector_id",
                    "foreignField": "_id",
                    "as": "fv",
                }
            },
            {"$unwind": "$fv"},
            {
                "$project": {
                    "feature_value": f"$fv.features.{feature_name}",
                }
            },
        ]

        results = list(self.db["training_enrichment_builds"].aggregate(pipeline))

        if not results:
            return {
                "group_by": group_by_str,
                "groups": [],
                "total_builds": 0,
            }

        # Process based on group type
        if group_by_enum == GroupByDimension.REPO_LANGUAGE:
            # Aggregate language counts
            language_counts: Dict[str, int] = {}
            for r in results:
                lang = r.get("feature_value")
                if lang:
                    lang = str(lang).lower()
                else:
                    lang = "other"
                language_counts[lang] = language_counts.get(lang, 0) + 1

            groups = [
                {
                    "value": lang,
                    "label": lang.title(),
                    "count": count,
                    **({"warning": "small_sample"} if count < 50 else {}),
                }
                for lang, count in sorted(language_counts.items(), key=lambda x: -x[1])
            ]

        elif group_by_enum == GroupByDimension.TIME_OF_DAY:
            # build_hour is 0-23, group into time slots
            hours_per_slot = 24 // time_slots
            slot_counts: Dict[int, int] = {}

            for r in results:
                hour = r.get("feature_value")
                if hour is None:
                    hour = 12
                else:
                    hour = int(hour)

                slot_start = (hour // hours_per_slot) * hours_per_slot
                slot_counts[slot_start] = slot_counts.get(slot_start, 0) + 1

            groups = []
            for slot_start in sorted(slot_counts.keys()):
                slot_end = min(slot_start + hours_per_slot, 24)
                label = f"{slot_start:02d}:00-{slot_end:02d}:00"
                count = slot_counts[slot_start]
                groups.append(
                    {
                        "value": label,
                        "label": label,
                        "count": count,
                        **({"warning": "small_sample"} if count < 50 else {}),
                    }
                )

        else:
            # percentage_of_builds_before or number_of_builds_before
            # These are numeric (0-100 for percentage, integer for count)
            # Create equal-width bins based on actual data
            values = [
                r.get("feature_value")
                for r in results
                if r.get("feature_value") is not None
            ]

            if not values:
                return {
                    "group_by": group_by_str,
                    "groups": [],
                    "total_builds": 0,
                }

            min_val = min(values)
            max_val = max(values)

            if min_val == max_val:
                # Single value - one bin
                groups = [
                    {
                        "value": f"{int(min_val)}-{int(max_val)}",
                        "label": f"{int(min_val)}-{int(max_val)}",
                        "count": len(values),
                    }
                ]
            else:
                # Create equal-width bins
                bin_width = (max_val - min_val) / num_bins
                bin_counts: Dict[int, int] = {i: 0 for i in range(num_bins)}

                for v in values:
                    bin_idx = min(int((v - min_val) / bin_width), num_bins - 1)
                    bin_counts[bin_idx] += 1

                groups = []
                for i in range(num_bins):
                    bin_start = min_val + i * bin_width
                    bin_end = min_val + (i + 1) * bin_width
                    count = bin_counts[i]
                    groups.append(
                        {
                            "value": f"{int(bin_start)}-{int(bin_end)}",
                            "label": f"{int(bin_start)}-{int(bin_end)}",
                            "count": count,
                            **({"warning": "small_sample"} if count < 50 else {}),
                        }
                    )

        total_builds = sum(g["count"] for g in groups)

        return {
            "group_by": group_by_str,
            "groups": groups,
            "total_builds": total_builds,
            "num_bins": num_bins,
            "time_slots": time_slots,
        }

    def get_data_availability(
        self,
        scenario_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Get data availability summary for export configuration.

        Returns progress of features and scan metrics extraction.
        """
        # Verify scenario access
        scenario = self.get_scenario(scenario_id, user_id)
        scenario_oid = ObjectId(scenario_id)

        # Feature extraction stats from enrichment builds
        feature_stats = self.enrichment_build_repo.count_by_extraction_status(
            scenario_id
        )
        features_total = sum(feature_stats.values())
        features_completed = feature_stats.get("completed", 0)

        # Get detailed scan counts from repositories
        trivy_total = self.trivy_scan_repo.count_by_scenario(scenario_oid)
        trivy_completed = self.trivy_scan_repo.count_completed_by_scenario(scenario_oid)
        sonar_total = self.sonar_scan_repo.count_by_scenario(scenario_oid)
        sonar_completed = self.sonar_scan_repo.count_completed_by_scenario(scenario_oid)

        return {
            "features": {
                "total": features_total,
                "completed": features_completed,
                "coverage_pct": (
                    round(features_completed / features_total * 100)
                    if features_total > 0
                    else 0
                ),
                "ready": scenario.feature_extraction_completed,
            },
            "trivy": {
                "total": trivy_total,
                "completed": trivy_completed,
                "coverage_pct": (
                    round(trivy_completed / trivy_total * 100) if trivy_total > 0 else 0
                ),
                "ready": trivy_completed == trivy_total and trivy_total > 0,
            },
            "sonarqube": {
                "total": sonar_total,
                "completed": sonar_completed,
                "coverage_pct": (
                    round(sonar_completed / sonar_total * 100) if sonar_total > 0 else 0
                ),
                "ready": sonar_completed == sonar_total and sonar_total > 0,
            },
            "all_complete": (
                scenario.feature_extraction_completed
                and (trivy_completed == trivy_total or trivy_total == 0)
                and (sonar_completed == sonar_total or sonar_total == 0)
            ),
        }
