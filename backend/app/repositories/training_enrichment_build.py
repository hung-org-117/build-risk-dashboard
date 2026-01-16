"""
Repository for EnrichmentBuild entity.

Tracks builds through processing and split assignment.
Unified from DatasetEnrichmentBuildRepository and MLScenarioEnrichmentBuildRepository.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo.database import Database

from app.entities.enums import ExtractionStatus
from app.entities.training_enrichment_build import TrainingEnrichmentBuild

from .base import BaseRepository


class TrainingEnrichmentBuildRepository(BaseRepository[TrainingEnrichmentBuild]):
    """MongoDB repository for enrichment builds."""

    def __init__(self, db: Database):
        super().__init__(db, "training_enrichment_builds", TrainingEnrichmentBuild)

    def find_by_scenario(
        self,
        scenario_id: str,
        extraction_status: Optional[ExtractionStatus] = None,
        skip: int = 0,
        limit: int = 0,
    ) -> tuple[list[TrainingEnrichmentBuild], int]:
        """
        Find enrichment builds for a scenario with filters.

        Args:
            scenario_id: Scenario ID
            extraction_status: Filter by extraction status
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
    ) -> List[TrainingEnrichmentBuild]:
        """Get enrichment builds ready for feature extraction."""
        return self.find_many(
            {
                "scenario_id": self._to_object_id(scenario_id),
                "extraction_status": ExtractionStatus.PENDING.value,
            },
            sort=[("created_at", 1)],
            limit=batch_size,
        )

    def upsert_for_ingestion_build(
        self,
        scenario_id: str,
        ingestion_build_id: str,
        raw_repo_id: str,
        raw_build_run_id: str,
        ci_run_id: str = "",
        commit_sha: str = "",
        repo_full_name: str = "",
        outcome: Optional[int] = None,
        build_started_at: Optional[datetime] = None,
    ) -> TrainingEnrichmentBuild:
        """
        Create or get existing enrichment build for an ingestion build.

        Returns existing enrichment build if already created.
        """
        existing = self.find_one(
            {
                "scenario_id": self._to_object_id(scenario_id),
                "ingestion_build_id": self._to_object_id(ingestion_build_id),
            }
        )
        if existing:
            return existing

        # Eagerly create FeatureVector (race condition fix)
        from app.entities.enums import FeatureVectorScope
        from app.repositories.feature_vector import FeatureVectorRepository

        fv_repo = FeatureVectorRepository(self.db)
        fv = fv_repo.upsert_features(
            raw_repo_id=self._to_object_id(raw_repo_id),
            raw_build_run_id=self._to_object_id(raw_build_run_id),
            features={},
            scope=FeatureVectorScope.DATASET.value,
            config_id=self._to_object_id(scenario_id),
            extraction_status=ExtractionStatus.PENDING,
        )

        doc = TrainingEnrichmentBuild(
            scenario_id=self._to_object_id(scenario_id),
            ingestion_build_id=self._to_object_id(ingestion_build_id),
            raw_repo_id=self._to_object_id(raw_repo_id),
            raw_build_run_id=self._to_object_id(raw_build_run_id),
            ci_run_id=ci_run_id,
            commit_sha=commit_sha,
            repo_full_name=repo_full_name,
            outcome=outcome,
            build_started_at=build_started_at,
            extraction_status=ExtractionStatus.PENDING,
            feature_vector_id=fv.id,  # Link immediately
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
    ) -> Optional[TrainingEnrichmentBuild]:
        """Update extraction status and optionally link feature vector."""
        updates: Dict[str, Any] = {"extraction_status": extraction_status.value}

        if extraction_status == ExtractionStatus.COMPLETED:
            updates["enriched_at"] = datetime.utcnow()

        if feature_vector_id:
            updates["feature_vector_id"] = self._to_object_id(feature_vector_id)

        if error_message:
            updates["extraction_error"] = error_message

        return self.update_one(enrichment_build_id, updates)

    def get_completed_with_features(
        self,
        scenario_id: str,
    ) -> List[TrainingEnrichmentBuild]:
        """Get all completed enrichment builds that have feature vectors."""
        return self.find_many(
            {
                "scenario_id": self._to_object_id(scenario_id),
                "extraction_status": ExtractionStatus.COMPLETED.value,
                "feature_vector_id": {"$ne": None},
            },
            sort=[("created_at", 1)],
        )

    def find_completed_by_scenario(
        self,
        scenario_id: str,
    ) -> List[TrainingEnrichmentBuild]:
        """Get all completed enrichment builds for a scenario (for group preview)."""
        return self.find_many(
            {
                "scenario_id": self._to_object_id(scenario_id),
                "extraction_status": ExtractionStatus.COMPLETED.value,
            },
            sort=[("created_at", 1)],
        )

    def find_by_scenario_with_features(
        self,
        scenario_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all enrichment builds joined with their FeatureVector data.

        Returns:
            List of dictionaries containing build data + 'features' + 'scan_metrics' from FeatureVector.
        """
        pipeline = [
            {"$match": {"scenario_id": self._to_object_id(scenario_id)}},
            # Only join if feature_vector_id exists
            {
                "$lookup": {
                    "from": "feature_vectors",
                    "localField": "feature_vector_id",
                    "foreignField": "_id",
                    "as": "fv",
                }
            },
            {"$unwind": {"path": "$fv", "preserveNullAndEmptyArrays": True}},
            {
                "$project": {
                    "_id": 1,
                    "scenario_id": 1,
                    "ingestion_build_id": 1,
                    "raw_repo_id": 1,
                    "raw_build_run_id": 1,
                    "ci_run_id": 1,
                    "commit_sha": 1,
                    "repo_full_name": 1,
                    "outcome": 1,
                    "group_value": 1,
                    "extraction_status": 1,
                    "build_started_at": 1,
                    "created_at": 1,
                    # Flatten fields from FeatureVector
                    "features": "$fv.features",
                    "scan_metrics": "$fv.scan_metrics",
                }
            },
        ]
        return list(self.collection.aggregate(pipeline))

    def find_by_scenario_with_feature_counts(
        self,
        scenario_id: str,
        extraction_status: Optional[ExtractionStatus] = None,
        skip: int = 0,
        limit: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Get enrichment builds with feature counts from FeatureVector.
        Used for list views to avoid frequent N+1 queries.
        """
        match_stage = {"scenario_id": self._to_object_id(scenario_id)}
        if extraction_status:
            match_stage["extraction_status"] = extraction_status.value

        pipeline = [
            {"$match": match_stage},
            {"$sort": {"created_at": 1}},
        ]

        # Count total before skipping
        count_pipeline = pipeline + [{"$count": "total"}]
        total_res = list(self.collection.aggregate(count_pipeline))
        total = total_res[0]["total"] if total_res else 0

        # Apply pagination
        if skip > 0:
            pipeline.append({"$skip": skip})
        if limit > 0:
            pipeline.append({"$limit": limit})

        # Lookup FeatureVector to get only feature_count
        pipeline.extend(
            [
                {
                    "$lookup": {
                        "from": "feature_vectors",
                        "localField": "feature_vector_id",
                        "foreignField": "_id",
                        "as": "fv",
                    }
                },
                {"$unwind": {"path": "$fv", "preserveNullAndEmptyArrays": True}},
                {
                    "$project": {
                        # Include all original fields
                        "id": "$_id",  # Alias _id to id for consistency
                        "scenario_id": 1,
                        "ingestion_build_id": 1,
                        "raw_repo_id": 1,
                        "raw_build_run_id": 1,
                        "feature_vector_id": 1,
                        "extraction_status": 1,
                        "extraction_error": 1,
                        "enriched_at": 1,
                        "outcome": 1,
                        "ci_run_id": 1,
                        "commit_sha": 1,
                        "repo_full_name": 1,
                        "build_started_at": 1,
                        "created_at": 1,
                        # Joined fields
                        "feature_count": {"$ifNull": ["$fv.feature_count", 0]},
                    }
                },
            ]
        )

        results = list(self.collection.aggregate(pipeline))
        return results, total

    def count_by_extraction_status(self, scenario_id: str) -> Dict[str, int]:
        """Get count of builds by extraction status."""
        pipeline = [
            {"$match": {"scenario_id": self._to_object_id(scenario_id)}},
            {"$group": {"_id": "$extraction_status", "count": {"$sum": 1}}},
        ]
        results = self.aggregate(pipeline)
        return {r["_id"]: r["count"] for r in results}

    def delete_by_scenario(self, scenario_id: str, session=None) -> int:
        """Delete all enrichment builds for a scenario."""
        return self.delete_many(
            {"scenario_id": self._to_object_id(scenario_id)}, session=session
        )

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
            scenario_id: Scenario ID
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
            # Verify feature vector is in TRAINING_SCENARIO scope
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
                    "fv.scope": FeatureVectorScope.DATASET.value,
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

    def aggregate_feature_stats(
        self,
        scenario_id: str,
        feature_name: str,
    ) -> Dict[str, Any]:
        """
        Aggregate feature statistics directly in MongoDB.

        Returns min, max, avg, stdDev, count for a single feature.
        This is much more efficient than loading all data into Python.

        Args:
            scenario_id: Scenario ID
            feature_name: Name of the feature to analyze

        Returns:
            Dict with 'stats' (min, max, avg, stdDev, count) and 'values' (sampled list)
        """
        pipeline = [
            {"$match": {"scenario_id": self._to_object_id(scenario_id)}},
            {
                "$lookup": {
                    "from": "feature_vectors",
                    "localField": "feature_vector_id",
                    "foreignField": "_id",
                    "as": "fv",
                }
            },
            {"$unwind": {"path": "$fv", "preserveNullAndEmptyArrays": False}},
            # Project the feature value, converting to double
            {
                "$project": {
                    "value": {
                        "$convert": {
                            "input": f"$fv.features.{feature_name}",
                            "to": "double",
                            "onError": None,
                            "onNull": None,
                        }
                    }
                }
            },
            # Filter out nulls
            {"$match": {"value": {"$ne": None}}},
            # Calculate stats in single pass
            {
                "$facet": {
                    "stats": [
                        {
                            "$group": {
                                "_id": None,
                                "min": {"$min": "$value"},
                                "max": {"$max": "$value"},
                                "avg": {"$avg": "$value"},
                                "stdDev": {"$stdDevPop": "$value"},
                                "count": {"$sum": 1},
                            }
                        }
                    ],
                    # Sample up to 1000 values for histogram calculation
                    "samples": [
                        {"$sample": {"size": 1000}},
                        {"$project": {"_id": 0, "value": 1}},
                    ],
                }
            },
        ]

        results = list(self.collection.aggregate(pipeline))
        if not results:
            return {"stats": None, "samples": []}

        result = results[0]
        stats = result.get("stats", [{}])[0] if result.get("stats") else None
        samples = [doc["value"] for doc in result.get("samples", [])]

        return {"stats": stats, "samples": samples}
