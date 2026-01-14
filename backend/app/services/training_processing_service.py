"""
Training Processing Service.

Handles Phase 2 of the Training Pipeline:
- Starting processing/feature extraction
- Listing enrichment builds (with features)
- Viewing detailed enrichment build info (with audit logs)
- Retrying failed processing builds
"""

import logging
from typing import Any, Dict, Optional

from fastapi import HTTPException
from pymongo.database import Database

from app.dtos.training_scenario import (
    TrainingEnrichmentBuildListResponse,
    TrainingEnrichmentBuildResponse,
)
from app.entities.enums import ExtractionStatus
from app.entities.training_scenario import ScenarioStatus
from app.repositories.feature_audit_log import FeatureAuditLogRepository
from app.repositories.raw_build_run import RawBuildRunRepository
from app.repositories.training_enrichment_build import TrainingEnrichmentBuildRepository
from app.repositories.training_scenario import TrainingScenarioRepository

logger = logging.getLogger(__name__)


class TrainingProcessingService:
    """Service for Training Processing operations."""

    def __init__(self, db: Database):
        self.db = db
        self.scenario_repo = TrainingScenarioRepository(db)
        self.enrichment_build_repo = TrainingEnrichmentBuildRepository(db)
        self.raw_build_run_repo = RawBuildRunRepository(db)
        self.audit_log_repo = FeatureAuditLogRepository(db)

    def start_processing(self, scenario_id: str, user_id: str) -> Dict[str, Any]:
        """Phase 2: Start processing."""
        from app.tasks.training_processing import start_scenario_processing

        scenario = self.scenario_repo.find_by_id(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

        # Must be INGESTED (or PROCESSED/FAILED to retry)
        if scenario.status not in [
            ScenarioStatus.INGESTED.value,
            ScenarioStatus.PROCESSED.value,
            ScenarioStatus.FAILED.value,
        ]:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Scenario must be INGESTED to start processing (current: {scenario.status})"
                ),
            )

        res = start_scenario_processing.delay(scenario_id)
        return {"status": "queued", "task_id": res.id}

    def reprocess_failed_feature_extraction(
        self, scenario_id: str, user_id: str
    ) -> Dict[str, Any]:
        """Retry failed processing builds."""
        from app.tasks.training_processing import reprocess_failed_feature_extraction

        scenario = self.scenario_repo.find_by_id(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

        res = reprocess_failed_feature_extraction.delay(scenario_id)
        return {"status": "queued", "task_id": res.id}

    def get_enrichment_builds(
        self,
        scenario_id: str,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        extraction_status: Optional[str] = None,
    ) -> TrainingEnrichmentBuildListResponse:
        """
        List enrichment builds for a scenario (Phase 2).
        """
        # Verify scenario exists
        scenario = self.scenario_repo.find_by_id(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

        # Convert status filter
        status_enum = None
        if extraction_status:
            try:
                status_enum = ExtractionStatus(extraction_status)
            except ValueError:
                pass

        builds_data, total = (
            self.enrichment_build_repo.find_by_scenario_with_feature_counts(
                scenario_id=scenario_id,
                extraction_status=status_enum,
                skip=skip,
                limit=limit,
            )
        )

        from app.tasks.pipeline.constants import DEFAULT_FEATURES

        # Get expected feature count from scenario
        current_features = (
            set(scenario.feature_config.dag_features)
            if scenario.feature_config
            else set()
        )
        expected_features = len(current_features.union(DEFAULT_FEATURES))

        items = []
        for build in builds_data:
            items.append(
                TrainingEnrichmentBuildResponse(
                    id=str(
                        build["id"]
                    ),  # Aggregation returns _id but we projected id=_id
                    # wait, pymongo returns _id as ObjectId usually.
                    # My projection: "id": "$_id" makes an `id` field.
                    raw_build_run_id=(
                        str(build["raw_build_run_id"])
                        if build.get("raw_build_run_id")
                        else ""
                    ),
                    ci_run_id=build.get("ci_run_id", ""),
                    commit_sha=build.get("commit_sha", ""),
                    repo_full_name=build.get("repo_full_name", ""),
                    extraction_status=build.get("extraction_status", "pending"),
                    extraction_error=build.get("extraction_error"),
                    feature_count=build.get(
                        "feature_count", 0
                    ),  # From FeatureVector join
                    expected_feature_count=expected_features,
                    created_at=(
                        build["created_at"].isoformat()
                        if build.get("created_at")
                        else None
                    ),
                    enriched_at=(
                        build["enriched_at"].isoformat()
                        if build.get("enriched_at")
                        else None
                    ),
                )
            )

        return TrainingEnrichmentBuildListResponse(
            items=items,
            total=total,
            page=(skip // limit) + 1 if limit > 0 else 1,
            size=limit,
        )

    def get_enrichment_build_detail(
        self,
        scenario_id: str,
        build_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Get detailed view of an enrichment build.
        Returns combined data: build info, features, and audit log.
        """
        # Verify scenario exists
        scenario = self.scenario_repo.find_by_id(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

        build = self.enrichment_build_repo.find_by_id(build_id)
        if not build:
            raise HTTPException(status_code=404, detail="Enrichment build not found")

        # Get raw build
        raw_build = None
        if build.raw_build_run_id:
            raw_build = self.raw_build_run_repo.find_by_id(build.raw_build_run_id)

        # Get features from FeatureVector if available
        features = {}
        feature_count = 0
        missing_resources = []
        skipped_features = []

        if build.feature_vector_id:
            from app.repositories.feature_vector import FeatureVectorRepository

            feature_vector_repo = FeatureVectorRepository(self.db)
            fv = feature_vector_repo.find_by_id(build.feature_vector_id)
            if fv:
                features = fv.features
                feature_count = fv.feature_count
                missing_resources = fv.missing_resources
                skipped_features = fv.skipped_features

        # Get audit log
        audit_log = self.audit_log_repo.find_by_enrichment_build(build_id)

        return {
            "enrichment_build": {
                "id": str(build.id),
                "raw_build_run_id": (
                    str(build.raw_build_run_id) if build.raw_build_run_id else ""
                ),
                "ci_run_id": build.ci_run_id or "",
                "commit_sha": build.commit_sha or "",
                "repo_full_name": build.repo_full_name or "",
                "extraction_status": (
                    build.extraction_status.value
                    if hasattr(build.extraction_status, "value")
                    else build.extraction_status
                ),
                "extraction_error": build.extraction_error,
                "feature_count": feature_count,
                "expected_feature_count": (
                    len(scenario.feature_config.dag_features)
                    if scenario and scenario.feature_config
                    else 0
                ),
                "created_at": (
                    build.created_at.isoformat() if build.created_at else None
                ),
                "enriched_at": (
                    build.enriched_at.isoformat() if build.enriched_at else None
                ),
                "features": features,
                "missing_resources": missing_resources,
                "skipped_features": skipped_features,
            },
            "raw_build_run": (
                {
                    "id": str(raw_build.id),
                    "repo_name": raw_build.repo_name,
                    "branch": raw_build.branch,
                    "commit_sha": raw_build.commit_sha,
                    "ci_run_id": raw_build.ci_run_id,
                    "provider": raw_build.provider,
                    "web_url": raw_build.web_url,
                    "conclusion": (
                        raw_build.conclusion.value
                        if hasattr(raw_build.conclusion, "value")
                        else raw_build.conclusion
                    ),
                    "run_started_at": (
                        raw_build.run_started_at.isoformat()
                        if raw_build.run_started_at
                        else None
                    ),
                }
                if raw_build
                else {}
            ),
            "audit_log": (
                {
                    "id": str(audit_log.id),
                    "duration_ms": audit_log.duration_ms,
                    "nodes_succeeded": audit_log.nodes_succeeded,
                    "nodes_failed": audit_log.nodes_failed,
                    "nodes_skipped": audit_log.nodes_skipped,
                    "errors": audit_log.errors,
                    "warnings": audit_log.warnings,
                    "node_results": [
                        {
                            "node_name": n.node_name,
                            "status": n.status,
                            "duration_ms": n.duration_ms,
                            "features_extracted": n.features_extracted,
                            "resources_used": n.resources_used,
                            "error": n.error,
                            "warning": n.warning,
                            "skip_reason": n.skip_reason,
                            "retry_count": n.retry_count,
                        }
                        for n in audit_log.node_results
                    ],
                }
                if audit_log
                else None
            ),
        }
