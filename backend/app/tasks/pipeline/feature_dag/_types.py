"""
Core feature types - FeatureDefinition dataclass and related enums.

This file exists to break circular imports between _feature_definitions.py and registry/.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.tasks.pipeline.feature_dag._metadata import (
    FeatureCategory,
    FeatureDataType,
    OutputFormat,
)
from app.tasks.pipeline.shared.resources import FeatureResource


@dataclass
class FeatureDefinition:
    """Definition of a single feature's metadata."""

    name: str
    display_name: str
    description: str
    category: FeatureCategory
    data_type: FeatureDataType
    extractor_node: str
    required_resources: List[FeatureResource] = field(default_factory=list)
    nullable: bool = True
    unit: Optional[str] = None
    output_format: Optional[OutputFormat] = None
    valid_range: Optional[Tuple[float, float]] = None
    valid_values: Optional[List[str]] = None
    example_value: Optional[str] = None


# Re-export for convenience
__all__ = [
    "FeatureDefinition",
    "FeatureCategory",
    "FeatureDataType",
    "FeatureResource",
    "OutputFormat",
]
