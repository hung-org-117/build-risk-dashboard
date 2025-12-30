"""
DatasetEnrichmentBuild Entity - Build for dataset enrichment.

This entity tracks builds in the dataset enrichment flow.
Features are stored in FeatureVector (referenced by feature_vector_id).

Key design principles:
- References FeatureVector for feature storage (single source of truth)
- Tracks CSV origin and dataset version
- Stores scan metrics separately (SonarQube, Trivy)
"""

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.entities.base import BaseEntity, PyObjectId
from app.entities.enums import ExtractionStatus


class DatasetEnrichmentBuild(BaseEntity):
    """
    Build tracking for dataset enrichment flow.

    Features are stored in FeatureVector entity, referenced by feature_vector_id.
    """

    class Config:
        collection = "dataset_enrichment_builds"
        use_enum_values = True

    # References to raw data
    raw_repo_id: PyObjectId = Field(
        ...,
        description="Reference to raw_repositories table",
    )
    raw_build_run_id: PyObjectId = Field(
        ...,
        description="Reference to raw_build_run table",
    )

    # Dataset references
    dataset_id: PyObjectId = Field(
        ...,
        description="Reference to datasets table",
    )
    dataset_version_id: PyObjectId = Field(
        None,
        description="Reference to dataset_versions table (if versioned enrichment)",
    )
    dataset_build_id: PyObjectId = Field(
        None,
        description="Reference to dataset_builds table",
    )

    # ** FEATURE VECTOR REFERENCE (single source of truth) **
    feature_vector_id: Optional[PyObjectId] = Field(
        None,
        description="Reference to feature_vectors table (stores extracted features)",
    )

    # Extraction status (mirrors FeatureVector.extraction_status for quick queries)
    extraction_status: ExtractionStatus = Field(
        default=ExtractionStatus.PENDING,
        description="Feature extraction status",
    )
    extraction_error: Optional[str] = Field(
        None,
        description="Error message if extraction failed",
    )

    enriched_at: Optional[datetime] = Field(
        None,
        description="Timestamp when features were extracted",
    )
