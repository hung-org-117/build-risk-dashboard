"""
Centralized Feature Definitions Registry.

Usage:
    from app.tasks.pipeline.feature_dag._feature_definitions import (
        get_feature_definition,
        FEATURE_REGISTRY,
    )
"""

from typing import Dict, List, Optional

# Import types from _types.py (the source of truth for FeatureDefinition)
from app.tasks.pipeline.feature_dag._types import (
    FeatureCategory,
    FeatureDataType,
    FeatureDefinition,
    FeatureResource,
    OutputFormat,
)

# Import FEATURE_REGISTRY from registry package
from app.tasks.pipeline.feature_dag.registry import FEATURE_REGISTRY

# Re-export everything for backwards compatibility
__all__ = [
    "FeatureCategory",
    "FeatureDataType",
    "FeatureDefinition",
    "FeatureResource",
    "OutputFormat",
    "FEATURE_REGISTRY",
    "get_feature_definition",
    "get_feature_data_type",
    "get_all_features_for_api",
]


def get_feature_definition(name: str) -> Optional[FeatureDefinition]:
    """Get feature definition by name."""
    return FEATURE_REGISTRY.get(name)


def get_feature_data_type(name: str) -> str:
    """Get data type string for a feature."""
    defn = get_feature_definition(name)
    return defn.data_type.value if defn else "unknown"


def get_all_features_for_api() -> List[Dict]:
    """Get all features in API-ready format."""
    return [
        {
            "name": name,
            "display_name": defn.display_name,
            "description": defn.description,
            "extractor_node": defn.extractor_node,
            "data_type": defn.data_type.value,
            "nullable": defn.nullable,
            "example_value": defn.example_value,
            "unit": defn.unit,
            "depends_on": [],
        }
        for name, defn in FEATURE_REGISTRY.items()
    ]
