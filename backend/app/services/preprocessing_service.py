import logging
from typing import Dict, List, Optional

import numpy as np
from pymongo.database import Database
from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler

from app.dtos.preprocessing import (
    FeaturePreview,
    NormalizationPreviewResponse,
)
from app.repositories.dataset_enrichment_build import DatasetEnrichmentBuildRepository
from app.repositories.dataset_version import DatasetVersionRepository
from app.tasks.pipeline.feature_dag._feature_definitions import get_feature_data_type

logger = logging.getLogger(__name__)


class PreprocessingService:
    """Service for preprocessing operations on dataset versions."""

    def __init__(self, db: Database):
        self.db = db
        self.version_repo = DatasetVersionRepository(db)
        self.build_repo = DatasetEnrichmentBuildRepository(db)

    def preview_normalization(
        self,
        dataset_id: str,
        version_id: str,
        method: str = "minmax",
        features: Optional[List[str]] = None,
        sample_size: int = 10,
    ) -> NormalizationPreviewResponse:
        """
        Preview normalization transformation on selected features.

        Args:
            dataset_id: Dataset ID
            version_id: Version ID
            method: Normalization method (none, minmax, zscore, robust, log)
            features: Features to preview. If None, all numeric features.
            sample_size: Number of sample values to return.

        Returns:
            NormalizationPreviewResponse with before/after samples and stats.
        """
        # Get version
        version = self.version_repo.find_by_id(version_id)
        if not version:
            return NormalizationPreviewResponse(
                method=method,
                version_id=version_id,
                features={},
                total_rows=0,
                message="Version not found",
            )

        # Get all builds
        builds = self.build_repo.find_by_version(version_id)
        if not builds:
            return NormalizationPreviewResponse(
                method=method,
                version_id=version_id,
                features={},
                total_rows=0,
                message="No builds found",
            )

        # Determine which features to process
        selected_features = version.selected_features or []
        if features:
            target_features = [f for f in features if f in selected_features]
        else:
            # Filter to numeric features only
            target_features = [
                f for f in selected_features if get_feature_data_type(f) in ("integer", "float")
            ]

        if not target_features:
            return NormalizationPreviewResponse(
                method=method,
                version_id=version_id,
                features={},
                total_rows=len(builds),
                message="No numeric features found",
            )

        # Extract feature values
        feature_values: Dict[str, List[float]] = {f: [] for f in target_features}

        for build in builds:
            if not build.features:
                continue
            for feature in target_features:
                if feature in build.features:
                    value = build.features[feature]
                    if value is not None:
                        try:
                            feature_values[feature].append(float(value))
                        except (ValueError, TypeError):
                            pass

        # Apply normalization and build response
        result_features: Dict[str, FeaturePreview] = {}

        for feature in target_features:
            values = feature_values[feature]
            if not values:
                continue

            # Get original stats and sample
            original_array = np.array(values)
            original_sample = values[:sample_size]
            original_stats = self._calculate_stats(original_array)

            # Apply transformation
            if method == "none":
                transformed_array = original_array.copy()
            else:
                transformed_array = self._apply_normalization(original_array, method)

            transformed_sample = transformed_array[:sample_size].tolist()
            transformed_stats = self._calculate_stats(transformed_array)

            # Round samples for readability
            original_sample = [round(v, 4) for v in original_sample]
            transformed_sample = [round(v, 4) for v in transformed_sample]

            result_features[feature] = FeaturePreview(
                data_type=get_feature_data_type(feature),
                original={
                    "sample": original_sample,
                    "stats": original_stats,
                },
                transformed={
                    "sample": transformed_sample,
                    "stats": transformed_stats,
                },
            )

        return NormalizationPreviewResponse(
            method=method,
            version_id=version_id,
            features=result_features,
            total_rows=len(builds),
        )

    def _apply_normalization(self, values: np.ndarray, method: str) -> np.ndarray:
        """Apply normalization to values array."""
        # Reshape for sklearn
        values_2d = values.reshape(-1, 1)

        if method == "minmax":
            scaler = MinMaxScaler()
            result = scaler.fit_transform(values_2d)
        elif method == "zscore":
            scaler = StandardScaler()
            result = scaler.fit_transform(values_2d)
        elif method == "robust":
            scaler = RobustScaler()
            result = scaler.fit_transform(values_2d)
        elif method == "log":
            # Log transform: log(x + 1) to handle zeros
            result = np.log1p(np.maximum(values_2d, 0))
        else:
            result = values_2d

        return result.flatten()

    def _calculate_stats(self, values: np.ndarray) -> Dict[str, float]:
        """Calculate statistics for an array."""
        if len(values) == 0:
            return {"min": 0, "max": 0, "mean": 0, "std": 0}

        return {
            "min": round(float(np.min(values)), 4),
            "max": round(float(np.max(values)), 4),
            "mean": round(float(np.mean(values)), 4),
            "std": round(float(np.std(values)), 4),
        }
