"""
PipelineContext - Unified context for scan and enrichment pipelines.

Provides a single abstraction to work with either:
- Dataset Enrichment pipeline (DatasetVersion)
- ML Scenario pipeline (MLScenario)

Auto-detection determines the correct pipeline type from context_id.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.database import Database

logger = logging.getLogger(__name__)


class PipelineType(str, Enum):
    """Supported pipeline types."""

    DATASET_ENRICHMENT = "dataset_enrichment"
    ML_SCENARIO = "ml_scenario"


@dataclass
class PipelineContext:
    """
    Unified context for pipeline operations.

    Provides common interface for operations that work across
    Dataset Enrichment and ML Scenario pipelines.
    """

    pipeline_type: PipelineType
    context_id: str  # version_id for enrichment, scenario_id for ML
    db: Database

    @classmethod
    def detect(cls, db: Database, context_id: str) -> Optional["PipelineContext"]:
        """
        Auto-detect pipeline type from context_id.

        Checks MongoDB collections to determine if the ID belongs to
        a DatasetVersion or MLScenario.

        Args:
            db: MongoDB database instance
            context_id: The ID to detect (version_id or scenario_id)

        Returns:
            PipelineContext if found, None if context_id not found in either collection.
        """
        try:
            oid = ObjectId(context_id)
        except InvalidId:
            logger.warning(f"Invalid ObjectId for context detection: {context_id}")
            return None

        # Check DatasetVersion collection first
        version_doc = db.dataset_versions.find_one({"_id": oid}, {"_id": 1})
        if version_doc:
            return cls(
                pipeline_type=PipelineType.DATASET_ENRICHMENT,
                context_id=context_id,
                db=db,
            )

        # Check MLScenario collection
        scenario_doc = db.ml_scenarios.find_one({"_id": oid}, {"_id": 1})
        if scenario_doc:
            return cls(
                pipeline_type=PipelineType.ML_SCENARIO,
                context_id=context_id,
                db=db,
            )

        logger.warning(
            f"Context {context_id} not found in DatasetVersion or MLScenario"
        )
        return None

    def get_enrichment_build_repo(self):
        """
        Get the appropriate enrichment build repository for this pipeline.

        Returns:
            DatasetEnrichmentBuildRepository or MLScenarioEnrichmentBuildRepository
        """
        if self.pipeline_type == PipelineType.DATASET_ENRICHMENT:
            from app.repositories.dataset_enrichment_build import (
                DatasetEnrichmentBuildRepository,
            )

            return DatasetEnrichmentBuildRepository(self.db)
        else:
            from app.repositories.ml_scenario_enrichment_build import (
                MLScenarioEnrichmentBuildRepository,
            )

            return MLScenarioEnrichmentBuildRepository(self.db)

    def backfill_scan_metrics_by_commit(
        self,
        commit_sha: str,
        scan_features: Dict[str, Any],
        prefix: str = "trivy_",
    ) -> int:
        """
        Backfill scan metrics to FeatureVectors for all builds matching commit.

        Delegates to the appropriate repository method based on pipeline type.

        Args:
            commit_sha: Git commit SHA to match
            scan_features: Dict of metrics to add (e.g., {"vuln_total": 5})
            prefix: Feature prefix ('trivy_' or 'sonar_')

        Returns:
            Number of FeatureVector documents updated.
        """
        enrichment_build_repo = self.get_enrichment_build_repo()

        if self.pipeline_type == PipelineType.DATASET_ENRICHMENT:
            return enrichment_build_repo.backfill_by_commit_in_version(
                version_id=ObjectId(self.context_id),
                commit_sha=commit_sha,
                scan_features=scan_features,
                prefix=prefix,
            )
        else:
            # ML Scenario uses same pattern but different method
            return enrichment_build_repo.backfill_by_commit_in_scenario(
                scenario_id=ObjectId(self.context_id),
                commit_sha=commit_sha,
                scan_features=scan_features,
                prefix=prefix,
            )

    def increment_scans_completed(self) -> bool:
        """Increment scans_completed counter for this context."""
        from app.tasks.shared.scan_context_helpers import increment_scan_completed

        return increment_scan_completed(self.db, self.context_id)

    def increment_scans_failed(self) -> bool:
        """Increment scans_failed counter for this context."""
        from app.tasks.shared.scan_context_helpers import increment_scan_failed

        return increment_scan_failed(self.db, self.context_id)

    def check_and_mark_scans_completed(self) -> bool:
        """
        Check if all scans are complete and mark scan_extraction_completed.

        Returns:
            True if all scans now complete, False if still pending.
        """
        from app.tasks.shared.scan_context_helpers import check_and_mark_scans_completed

        return check_and_mark_scans_completed(self.db, self.context_id)

    def check_and_notify_completed(self) -> bool:
        """
        Check if processing is fully complete and send notification if needed.

        For DatasetVersion: checks features + scans complete, sends email notification.
        For MLScenario: checks features + scans complete, logs completion.

        Returns:
            True if notification was sent/logged, False if still pending.
        """
        if self.pipeline_type == PipelineType.DATASET_ENRICHMENT:
            from app.services.notification_service import (
                check_and_notify_enrichment_completed,
            )

            return check_and_notify_enrichment_completed(
                db=self.db, version_id=self.context_id
            )
        else:
            from app.services.notification_service import (
                check_and_notify_scenario_completed,
            )

            return check_and_notify_scenario_completed(
                db=self.db, scenario_id=self.context_id
            )
