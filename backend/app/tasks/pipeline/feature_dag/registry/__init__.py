"""Feature definitions registry package.

All feature definitions are stored here, split by domain.
FEATURE_REGISTRY combines all of them for global access.
"""

from typing import Dict

from app.tasks.pipeline.feature_dag._types import FeatureDefinition

from .build import BUILD_FEATURES
from .ci import CI_FEATURES
from .code import CODE_FEATURES
from .repository import REPOSITORY_FEATURES
from .temporal import TEMPORAL_FEATURES

# Combined registry - single source of truth
FEATURE_REGISTRY: Dict[str, FeatureDefinition] = {
    **BUILD_FEATURES,
    **CI_FEATURES,
    **CODE_FEATURES,
    **REPOSITORY_FEATURES,
    **TEMPORAL_FEATURES,
}

__all__ = [
    "FEATURE_REGISTRY",
    "BUILD_FEATURES",
    "CI_FEATURES",
    "CODE_FEATURES",
    "REPOSITORY_FEATURES",
    "TEMPORAL_FEATURES",
]
