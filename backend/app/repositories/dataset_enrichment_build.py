"""Repository for DatasetEnrichmentBuild entities (builds for dataset enrichment)."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Iterator

from bson import ObjectId

from app.entities.dataset_enrichment_build import DatasetEnrichmentBuild
from app.entities.enums import ExtractionStatus
from app.repositories.base import BaseRepository


class DatasetEnrichmentBuildRepository(BaseRepository[DatasetEnrichmentBuild]):
    """Repository for DatasetEnrichmentBuild entities (Dataset enrichment flow)."""

    def __init__(self, db) -> None:
        super().__init__(db, "dataset_enrichment_builds", DatasetEnrichmentBuild)

    def find_by_dataset_build_id(
        self,
        dataset_id: ObjectId,
        dataset_build_id: ObjectId,
    ) -> Optional[DatasetEnrichmentBuild]:
        """Find build by dataset and dataset build ID."""
        doc = self.collection.find_one(
            {
                "dataset_id": dataset_id,
                "dataset_build_id": dataset_build_id,
            }
        )
        return DatasetEnrichmentBuild(**doc) if doc else None

    def find_by_workflow_run(
        self,
        dataset_id: ObjectId,
        raw_workflow_run_id: ObjectId,
    ) -> Optional[DatasetEnrichmentBuild]:
        """Find build by dataset and workflow run."""
        doc = self.collection.find_one(
            {
                "dataset_id": dataset_id,
                "raw_workflow_run_id": raw_workflow_run_id,
            }
        )
        return DatasetEnrichmentBuild(**doc) if doc else None

    def list_by_dataset(
        self,
        dataset_id: ObjectId,
        skip: int = 0,
        limit: int = 100,
        status: Optional[ExtractionStatus] = None,
    ) -> tuple[List[DatasetEnrichmentBuild], int]:
        """List builds for a dataset with pagination."""
        query: Dict[str, Any] = {"dataset_id": dataset_id}
        if status:
            query["extraction_status"] = (
                status.value if hasattr(status, "value") else status
            )

        total = self.collection.count_documents(query)
        cursor = self.collection.find(query).sort("_id", 1).skip(skip).limit(limit)
        items = [DatasetEnrichmentBuild(**doc) for doc in cursor]
        return items, total

    def list_by_version(
        self,
        dataset_version_id: ObjectId,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[List[DatasetEnrichmentBuild], int]:
        """List builds for a dataset version with pagination."""
        query = {"dataset_version_id": dataset_version_id}
        total = self.collection.count_documents(query)
        cursor = self.collection.find(query).sort("_id", 1).skip(skip).limit(limit)
        items = [DatasetEnrichmentBuild(**doc) for doc in cursor]
        return items, total

    def update_extraction_status(
        self,
        build_id: ObjectId,
        status: ExtractionStatus,
        error: Optional[str] = None,
        is_missing_commit: bool = False,
    ) -> None:
        """Update extraction status for a build."""
        update: Dict[str, Any] = {
            "extraction_status": status.value if hasattr(status, "value") else status,
            "updated_at": datetime.utcnow(),
        }
        if error:
            update["extraction_error"] = error
        if is_missing_commit:
            update["is_missing_commit"] = True

        self.collection.update_one({"_id": build_id}, {"$set": update})

    def save_features(
        self,
        build_id: ObjectId,
        features: Dict[str, Any],
    ) -> None:
        """Save extracted features to a build."""
        self.collection.update_one(
            {"_id": build_id},
            {
                "$set": {
                    "features": features,
                    "feature_count": len(features),
                    "extraction_status": ExtractionStatus.COMPLETED.value,
                    "enriched_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    def count_by_dataset(
        self,
        dataset_id: ObjectId,
        status: Optional[ExtractionStatus] = None,
    ) -> int:
        """Count builds for a dataset, optionally filtered by status."""
        query: Dict[str, Any] = {"dataset_id": dataset_id}
        if status:
            query["extraction_status"] = (
                status.value if hasattr(status, "value") else status
            )
        return self.collection.count_documents(query)

    def get_enriched_for_export(
        self,
        dataset_id: ObjectId,
        version_id: Optional[ObjectId] = None,
        limit: Optional[int] = None,
    ) -> Iterator[DatasetEnrichmentBuild]:
        """Get all enriched builds for export, sorted by CSV row index. Yields results."""
        query: Dict[str, Any] = {
            "dataset_id": dataset_id,
            "extraction_status": ExtractionStatus.COMPLETED.value,
        }
        if version_id:
            query["dataset_version_id"] = version_id

        cursor = self.collection.find(query).sort("_id", 1).limit(limit)
        for doc in cursor:
            yield DatasetEnrichmentBuild(**doc)

    def delete_by_dataset(self, dataset_id: ObjectId) -> int:
        """Delete all builds for a dataset."""
        result = self.collection.delete_many({"dataset_id": dataset_id})
        return result.deleted_count

    def delete_by_version(self, version_id: str) -> int:
        """Delete all builds for a version."""
        result = self.collection.delete_many(
            {"dataset_version_id": ObjectId(version_id)}
        )
        return result.deleted_count

    def get_feature_stats(
        self,
        dataset_id: ObjectId,
        version_id: ObjectId,
        features: List[str],
    ) -> Dict[str, Any]:
        """
        Calculate statistics for features
        """
        if not features:
            return {}

        query = {
            "dataset_id": dataset_id,
            "dataset_version_id": version_id,
        }

        # 1. Get total count
        total_docs = self.collection.count_documents(query)
        if total_docs == 0:
            return {}

        # 2. Calculate min, max, avg, and count
        group_fields = {"_id": None}
        for feature in features:
            field_path = f"$features.{feature}"

            # Numeric stat
            group_fields[f"{feature}__min"] = {"$min": field_path}
            group_fields[f"{feature}__max"] = {"$max": field_path}
            group_fields[f"{feature}__avg"] = {"$avg": field_path}

            # Count non-null values
            # $cond with $ne: [val, None] correctly counts 1 for any value (including False/0) except null/missing
            group_fields[f"{feature}__non_null"] = {
                "$sum": {"$cond": [{"$ne": [field_path, None]}, 1, 0]}
            }

        pipeline = [{"$match": query}, {"$group": group_fields}]

        try:
            agg_results = list(self.collection.aggregate(pipeline, allowDiskUse=True))
        except Exception:
            return {}

        result_doc = agg_results[0] if agg_results else {}

        # 3. Type Inference (via sampling)
        sample_docs = list(self.collection.find(query, {"features": 1}).limit(5))

        stats = {}
        for feature in features:
            # Determine type from samples
            value_type = "unknown"
            for doc in sample_docs:
                val = doc.get("features", {}).get(feature)
                if val is not None:
                    if isinstance(val, bool):
                        value_type = "boolean"
                    elif isinstance(val, (int, float)):
                        value_type = "numeric"
                    elif isinstance(val, str):
                        value_type = "string"
                    elif isinstance(val, list):
                        value_type = "array"
                    break  # Found a type

            # Retrieve stats from aggregation result
            non_null = result_doc.get(f"{feature}__non_null", 0)
            missing = total_docs - non_null
            missing_rate = (missing / total_docs * 100) if total_docs else 0

            feat_stat = {
                "non_null": non_null,
                "missing": missing,
                "missing_rate": round(missing_rate, 1),
                "type": value_type,
            }

            # Add numeric stats if applicable
            # Note: $avg returns null if no numeric values existed
            avg_val = result_doc.get(f"{feature}__avg")
            if avg_val is not None:
                feat_stat["min"] = result_doc.get(f"{feature}__min")
                feat_stat["max"] = result_doc.get(f"{feature}__max")
                feat_stat["avg"] = round(avg_val, 2)
                if value_type == "unknown":
                    value_type = "numeric"

            feat_stat["type"] = value_type
            stats[feature] = feat_stat

        return stats
