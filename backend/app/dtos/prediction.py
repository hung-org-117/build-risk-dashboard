"""
Prediction DTOs for ML risk prediction.
"""

from typing import Dict, Optional

from pydantic import BaseModel, Field


class PredictionFeatures(BaseModel):
    """Features to send to ML prediction service."""

    features: Dict[str, float] = Field(
        ...,
        description="Normalized feature values keyed by feature name",
    )
    build_id: Optional[str] = Field(
        None,
        description="Build ID for tracking purposes",
    )


class PredictionResult(BaseModel):
    """Result from ML prediction service."""

    risk_level: str = Field(
        ...,
        description="Risk level: LOW, MEDIUM, or HIGH",
    )
    risk_probabilities: Dict[str, float] = Field(
        ...,
        description="Probability distribution for each risk level",
    )
    uncertainty: float = Field(
        ...,
        description="Uncertainty score (0-1, higher = more uncertain)",
    )
    model_version: str = Field(
        ...,
        description="Version of the ML model that made the prediction",
    )


class BuildPredictionResponse(BaseModel):
    """API response for build prediction."""

    build_id: str
    risk_level: str
    risk_probabilities: Dict[str, float]
    uncertainty_score: float
    prediction_confidence: float
    model_version: str
    predicted_at: str
    has_prediction: bool = True
