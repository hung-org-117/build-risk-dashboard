"""
Preprocessing DTOs - Request/Response models for preprocessing operations.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class NormalizationPreviewRequest(BaseModel):
    """Request for normalization preview."""

    method: Literal["none", "minmax", "zscore", "robust", "log"] = Field(
        default="minmax", description="Normalization method to apply"
    )
    features: Optional[List[str]] = Field(
        default=None, description="Features to preview. If None, all numeric features will be used"
    )
    sample_size: int = Field(
        default=10, ge=1, le=100, description="Number of sample values to return"
    )


class FeatureStats(BaseModel):
    """Statistics for a feature."""

    min: float
    max: float
    mean: float
    std: float


class FeaturePreview(BaseModel):
    """Preview data for a single feature."""

    data_type: str
    original: Dict[str, Any] = Field(description="Original values: {sample: [...], stats: {...}}")
    transformed: Dict[str, Any] = Field(
        description="Transformed values: {sample: [...], stats: {...}}"
    )


class NormalizationPreviewResponse(BaseModel):
    """Response for normalization preview."""

    method: str
    version_id: str
    features: Dict[str, FeaturePreview]
    total_rows: int
    message: Optional[str] = None
