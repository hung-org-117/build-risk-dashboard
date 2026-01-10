"""
Repository for MLScenarioEnrichmentBuild entity.

Tracks builds through processing and split assignment.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo.database import Database

from app.entities.ml_scenario_enrichment_build import MLScenarioEnrichmentBuild
from app.entities.enums import ExtractionStatus

from .base import BaseRepository


class MLScenarioEnrichmentBuildRepository(BaseRepository[MLScenarioEnrichmentBuild]):
    """MongoDB repository for ML scenario enrichment builds."""

    def __init__(self, db: Database):
        super().__init__(db, "ml_scenario_enrichment_builds", MLScenarioEnrichmentBuild)

    def find_by_scenario(
        self,
        scenario_id: str,
        extraction_status: Optional[ExtractionStatus] = None,
        split_assignment: Optional[str] = None,
        skip: int = 0,
        limit: int = 0,
    ) -> tuple[list[MLScenarioEnrichmentBuild], int]:
        """
        Find enrichment builds for a scenario with filters.

        Args:
            scenario_id: Scenario ID
            extraction_status: Filter by extraction status
            split_assignment: Filter by split (train/validation/test)
            skip: Pagination offset
            limit: Max results

        Returns:
            Tuple of (enrichment_builds, total_count)
        """
        query: Dict[str, Any] = {
            "scenario_id": self._to_object_id(scenario_id),
        }
        if extraction_status:
            query["extraction_status"] = extraction_status.value
        if split_assignment:
            query["split_assignment"] = split_assignment

        return self.paginate(
            query,
            sort=[("created_at", 1)],
            skip=skip,
            limit=limit,
        )

    def find_pending_for_processing(
        self,
        scenario_id: str,
        batch_size: int = 50,
    ) -> List[MLScenarioEnrichmentBuild]:
        """Get enrichment builds ready for feature extraction."""
        return self.find_many(
            {
                "scenario_id": self._to_object_id(scenario_id),
                "extraction_status": ExtractionStatus.PENDING.value,
            },
            sort=[("created_at", 1)],
            limit=batch_size,
        )

    def bulk_create_from_import_builds(
        self,
        scenario_id: str,
        import_build_data: List[Dict[str, Any]],
    ) -> int:
        """
        Bulk create enrichment builds from ingested import builds.

        Args:
            scenario_id: Scenario ID
            import_build_data: List of dicts with import build info

        Returns:
            Number of enrichment builds created
        """
        if not import_build_data:
            return 0

        scenario_oid = self._to_object_id(scenario_id)
        documents = []

        for data in import_build_data:
            doc = MLScenarioEnrichmentBuild(
                scenario_id=scenario_oid,
                scenario_import_build_id=data["scenario_import_build_id"],
                raw_repo_id=data["raw_repo_id"],
                raw_build_run_id=data["raw_build_run_id"],
                ci_run_id=data.get("ci_run_id", ""),
                commit_sha=data.get("commit_sha", ""),
                repo_full_name=data.get("repo_full_name", ""),
                outcome=data.get("outcome"),
                group_value=data.get("group_value"),
                extraction_status=ExtractionStatus.PENDING,
            )
            documents.append(doc)

        inserted = self.insert_many(documents)
        return len(inserted)

    def upsert_for_import_build(
        self,
        scenario_id: str,
        scenario_import_build_id: str,
        raw_repo_id: str,
        raw_build_run_id: str,
        ci_run_id: str = "",
        commit_sha: str = "",
        repo_full_name: str = "",
        outcome: Optional[int] = None,
        build_started_at: Optional[datetime] = None,
    ) -> MLScenarioEnrichmentBuild:
        """
        Create or get existing enrichment build for an import build.

        Returns existing enrichment build if already created.
        """
        existing = self.find_one(
            {
                "scenario_id": self._to_object_id(scenario_id),
                "scenario_import_build_id": self._to_object_id(
                    scenario_import_build_id
                ),
            }
        )
        if existing:
            return existing

        doc = MLScenarioEnrichmentBuild(
            scenario_id=self._to_object_id(scenario_id),
            scenario_import_build_id=self._to_object_id(scenario_import_build_id),
            raw_repo_id=self._to_object_id(raw_repo_id),
            raw_build_run_id=self._to_object_id(raw_build_run_id),
            ci_run_id=ci_run_id,
            commit_sha=commit_sha,
            repo_full_name=repo_full_name,
            outcome=outcome,
            build_started_at=build_started_at,
            extraction_status=ExtractionStatus.PENDING,
        )
        return self.insert_one(doc)

    def aggregate_stats_by_scenario(self, scenario_id: str) -> Dict[str, int]:
        """
        Aggregate extraction status stats for a scenario.

        Returns:
            Dict with keys: completed, partial, failed, pending
        """
        status_counts = self.count_by_extraction_status(scenario_id)
        return {
            "completed": status_counts.get(ExtractionStatus.COMPLETED.value, 0),
            "partial": status_counts.get(ExtractionStatus.PARTIAL.value, 0),
            "failed": status_counts.get(ExtractionStatus.FAILED.value, 0),
            "pending": status_counts.get(ExtractionStatus.PENDING.value, 0),
        }

    def update_extraction_status(
        self,
        enrichment_build_id: str,
        extraction_status: ExtractionStatus,
        feature_vector_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[MLScenarioEnrichmentBuild]:
        """Update extraction status and optionally link feature vector."""
        updates: Dict[str, Any] = {"extraction_status": extraction_status.value}

        if extraction_status == ExtractionStatus.COMPLETED:
            updates["enriched_at"] = datetime.utcnow()

        if feature_vector_id:
            updates["feature_vector_id"] = self._to_object_id(feature_vector_id)

        if error_message:
            updates["extraction_error"] = error_message

        return self.update_one(enrichment_build_id, updates)

    def assign_splits(
        self,
        scenario_id: str,
        assignments: Dict[str, List[str]],
    ) -> int:
        """
        Bulk assign splits to enrichment builds.

        Args:
            scenario_id: Scenario ID
            assignments: Dict mapping split type to list of enrichment_build_ids
                        e.g., {"train": [id1, id2], "validation": [id3]}

        Returns:
            Total number of builds updated
        """
        total_updated = 0

        for split_type, enrichment_build_ids in assignments.items():
            if not enrichment_build_ids:
                continue

            object_ids = [self._to_object_id(bid) for bid in enrichment_build_ids]
            result = self.collection.update_many(
                {"_id": {"$in": object_ids}},
                {"$set": {"split_assignment": split_type}},
            )
            total_updated += result.modified_count

        return total_updated

    def get_completed_with_features(
        self,
        scenario_id: str,
    ) -> List[MLScenarioEnrichmentBuild]:
        """Get all completed enrichment builds that have feature vectors."""
        return self.find_many(
            {
                "scenario_id": self._to_object_id(scenario_id),
                "extraction_status": ExtractionStatus.COMPLETED.value,
                "feature_vector_id": {"$ne": None},
            },
            sort=[("created_at", 1)],
        )

    def count_by_extraction_status(self, scenario_id: str) -> Dict[str, int]:
        """Get count of builds by extraction status."""
        pipeline = [
            {"$match": {"scenario_id": self._to_object_id(scenario_id)}},
            {"$group": {"_id": "$extraction_status", "count": {"$sum": 1}}},
        ]
        results = self.aggregate(pipeline)
        return {r["_id"]: r["count"] for r in results}

    def count_by_split(self, scenario_id: str) -> Dict[str, int]:
        """Get count of builds by split assignment."""
        pipeline = [
            {
                "$match": {
                    "scenario_id": self._to_object_id(scenario_id),
                    "split_assignment": {"$ne": None},
                }
            },
            {"$group": {"_id": "$split_assignment", "count": {"$sum": 1}}},
        ]
        results = self.aggregate(pipeline)
        return {r["_id"]: r["count"] for r in results}

    def delete_by_scenario(self, scenario_id: str) -> int:
        """Delete all enrichment builds for a scenario."""
        return self.delete_many({"scenario_id": self._to_object_id(scenario_id)})

    def backfill_by_commit_in_scenario(
        self,
        scenario_id: ObjectId,
        commit_sha: str,
        scan_features: Dict[str, Any],
        prefix: str = "trivy_",
    ) -> int:
        """
        Backfill scan metrics to FeatureVector for ALL builds in a scenario matching commit_sha.

        This is called when a scan completes to update FeatureVector.scan_metrics
        for all enrichment builds in the same scenario that share the same commit.

        Args:
            scenario_id: MLScenario ID
            commit_sha: Git commit SHA
            scan_features: Filtered metrics to add
            prefix: Feature prefix ('sonar_' or 'trivy_')

        Returns:
            Number of FeatureVector documents updated.
        """
        from app.entities.enums import FeatureVectorScope

        # Find all enrichment builds in this scenario with matching commit
        # and get their feature_vector_id
        pipeline = [
            {"$match": {"scenario_id": scenario_id, "commit_sha": commit_sha}},
            {"$match": {"feature_vector_id": {"$ne": None}}},
            # Verify feature vector is in ML_SCENARIO scope
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
                "$match": {
                    "fv.scope": FeatureVectorScope.ML_SCENARIO.value,
                    "fv.config_id": scenario_id,
                }
            },
            {"$project": {"feature_vector_id": 1}},
        ]

        matching_docs = list(self.collection.aggregate(pipeline))
        feature_vector_ids = [
            doc["feature_vector_id"]
            for doc in matching_docs
            if doc.get("feature_vector_id")
        ]

        if not feature_vector_ids:
            return 0

        # Write to FeatureVector.scan_metrics with prefix
        set_ops = {f"scan_metrics.{prefix}{k}": v for k, v in scan_features.items()}
        set_ops["updated_at"] = datetime.utcnow()

        feature_vectors_collection = self.db["feature_vectors"]
        result = feature_vectors_collection.update_many(
            {"_id": {"$in": feature_vector_ids}},
            {"$set": set_ops},
        )

        return result.modified_count
