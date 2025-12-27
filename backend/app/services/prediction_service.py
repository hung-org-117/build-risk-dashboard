"""
Prediction Service for ML-based build risk prediction.

This service handles:
- Feature normalization
- Calling external ML prediction API (or mock for development)
- Storing prediction results
"""

import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo.database import Database

from app.config import settings
from app.dtos.prediction import PredictionResult
from app.repositories.model_training_build import ModelTrainingBuildRepository

logger = logging.getLogger(__name__)

# Features used for prediction (configurable)
PREDICTION_FEATURES: List[str] = [
    "git_diff_src_churn",
    "git_diff_test_churn",
    "gh_team_size",
    "gh_num_commits_on_files_touched",
    "tr_log_num_jobs",
    "tr_duration",
    "gh_sloc",
    "gh_test_lines_per_kloc",
    "gh_diff_files_modified",
    "gh_diff_src_files",
]


class PredictionService:
    """Service for ML-based build risk prediction."""

    def __init__(self, db: Database):
        self.db = db
        self.training_build_repo = ModelTrainingBuildRepository(db)
        self.ml_api_url = getattr(settings, "ML_PREDICTION_API_URL", None)
        self.use_mock = self.ml_api_url is None

    def predict_build_risk(self, build_id: str) -> Optional[PredictionResult]:
        """
        Predict risk level for a build.

        Args:
            build_id: The ModelTrainingBuild ID

        Returns:
            PredictionResult with risk level and uncertainty
        """
        # Get the build
        build = self.training_build_repo.find_by_id(ObjectId(build_id))
        if not build:
            logger.warning(f"Build not found: {build_id}")
            return None

        # Check if features are available
        if not build.features:
            logger.warning(f"Build {build_id} has no features")
            return None

        # Normalize features
        normalized_features = self._normalize_features(build.features)

        # Get prediction (mock or real API)
        if self.use_mock:
            result = self._mock_prediction(normalized_features)
        else:
            result = self._call_ml_api(normalized_features, build_id)

        if result:
            # Store prediction in database
            self._store_prediction(build_id, result)

        return result

    def _normalize_features(self, features: Dict[str, Any]) -> Dict[str, float]:
        """
        Normalize features for ML model input.

        Uses min-max normalization with predefined ranges.
        Missing features are filled with 0.0.
        """
        normalized: Dict[str, float] = {}

        # Feature ranges for normalization (approximate ranges based on typical values)
        feature_ranges = {
            "git_diff_src_churn": (0, 10000),
            "git_diff_test_churn": (0, 5000),
            "gh_team_size": (1, 50),
            "gh_num_commits_on_files_touched": (0, 1000),
            "tr_log_num_jobs": (0, 100),
            "tr_duration": (0, 7200),  # 2 hours max
            "gh_sloc": (0, 500000),
            "gh_test_lines_per_kloc": (0, 500),
            "gh_diff_files_modified": (0, 100),
            "gh_diff_src_files": (0, 50),
        }

        for feature_name in PREDICTION_FEATURES:
            value = features.get(feature_name)

            if value is None:
                normalized[feature_name] = 0.0
                continue

            try:
                float_value = float(value)
                min_val, max_val = feature_ranges.get(feature_name, (0, 1))

                # Min-max normalization
                if max_val > min_val:
                    norm_value = (float_value - min_val) / (max_val - min_val)
                    # Clamp to [0, 1]
                    norm_value = max(0.0, min(1.0, norm_value))
                else:
                    norm_value = 0.0

                normalized[feature_name] = round(norm_value, 4)
            except (ValueError, TypeError):
                normalized[feature_name] = 0.0

        return normalized

    def _mock_prediction(self, features: Dict[str, float]) -> PredictionResult:
        """
        Generate mock prediction for development/testing.

        Uses random values but weighted by feature values to simulate
        realistic behavior.
        """
        # Calculate a simple "risk score" from features
        feature_sum = sum(features.values())
        avg_feature = feature_sum / len(features) if features else 0.5

        # Add some randomness
        noise = random.uniform(-0.2, 0.2)
        risk_score = max(0.0, min(1.0, avg_feature + noise))

        # Generate probabilities based on risk score
        if risk_score < 0.33:
            probs = {
                "LOW": round(random.uniform(0.5, 0.7), 2),
                "MEDIUM": round(random.uniform(0.2, 0.35), 2),
                "HIGH": 0.0,
            }
            probs["HIGH"] = round(1.0 - probs["LOW"] - probs["MEDIUM"], 2)
            risk_level = "LOW"
        elif risk_score < 0.66:
            probs = {
                "LOW": round(random.uniform(0.15, 0.3), 2),
                "MEDIUM": round(random.uniform(0.45, 0.6), 2),
                "HIGH": 0.0,
            }
            probs["HIGH"] = round(1.0 - probs["LOW"] - probs["MEDIUM"], 2)
            risk_level = "MEDIUM"
        else:
            probs = {
                "LOW": round(random.uniform(0.05, 0.15), 2),
                "MEDIUM": round(random.uniform(0.2, 0.35), 2),
                "HIGH": 0.0,
            }
            probs["HIGH"] = round(1.0 - probs["LOW"] - probs["MEDIUM"], 2)
            risk_level = "HIGH"

        # Uncertainty (Bayesian model would provide this)
        uncertainty = round(random.uniform(0.1, 0.5), 2)

        return PredictionResult(
            risk_level=risk_level,
            risk_probabilities=probs,
            uncertainty=uncertainty,
            model_version="mock-v1.0",
        )

    def _call_ml_api(
        self,
        features: Dict[str, float],
        build_id: str,
    ) -> Optional[PredictionResult]:
        """
        Call external ML prediction API.

        TODO: Implement when API is available.
        """
        # Placeholder for real API call
        # import httpx
        # response = httpx.post(
        #     self.ml_api_url,
        #     json=PredictionFeatures(features=features, build_id=build_id).model_dump(),
        #     timeout=30.0,
        # )
        # return PredictionResult(**response.json())

        logger.warning("Real ML API not configured, using mock")
        return self._mock_prediction(features)

    def _store_prediction(
        self,
        build_id: str,
        result: PredictionResult,
    ) -> None:
        """Store prediction result in the database."""
        now = datetime.now(timezone.utc)

        # Calculate confidence as 1 - uncertainty
        confidence = round(1.0 - result.uncertainty, 2)

        update_data = {
            "has_prediction": True,
            "risk_level": result.risk_level,
            "risk_probabilities": result.risk_probabilities,
            "uncertainty_score": result.uncertainty,
            "prediction_confidence": confidence,
            "predicted_label": result.risk_level,
            "prediction_model_version": result.model_version,
            "predicted_at": now,
        }

        self.training_build_repo.update(ObjectId(build_id), update_data)
        logger.info(
            f"Stored prediction for build {build_id}: "
            f"{result.risk_level} (uncertainty: {result.uncertainty})"
        )
