"""
Shared preprocessing types - Single source of truth.

These enums are used by:
- Feature DAG registry (FeatureDefinition)
- Integration tools (MetricDefinition for SonarQube/Trivy)
- PreprocessingService
"""

from enum import Enum


class PreprocessingType(str, Enum):
    """How to handle this feature/metric in preprocessing.

    Determines fill strategy and scaling behavior:
    - IDENTIFIER: Skip all preprocessing, fill=NULL (IDs, SHAs, commit hashes)
    - BINARY: fill=ZERO, no scaling (0/1 boolean features)
    - COUNT: fill=ZERO, optional scaling (non-negative integers)
    - RATIO: fill=ZERO, no scaling (bounded 0-1 or percentage)
    - CONTINUOUS: fill=MEAN/MEDIAN (user choice), scale (unbounded floats)
    - CATEGORICAL: fill=UNKNOWN, no scaling (string/enum features)
    """

    IDENTIFIER = "identifier"
    BINARY = "binary"
    COUNT = "count"
    RATIO = "ratio"
    CONTINUOUS = "continuous"
    CATEGORICAL = "categorical"


class MissingValueStrategy(str, Enum):
    """How to fill missing values for a feature/metric.

    Used in FeatureDefinition and MetricDefinition to specify
    per-column fill behavior (overrides global strategy).
    """

    ZERO = "zero"  # Fill with 0 (default for COUNT, BINARY, RATIO)
    MEAN = "mean"  # Fill with column mean (CONTINUOUS)
    MEDIAN = "median"  # Fill with column median (CONTINUOUS)
    NULL = "null"  # Keep as null/NaN - DEFAULT for IDENTIFIER
    UNKNOWN = "unknown"  # Fill with "unknown" string - DEFAULT for CATEGORICAL
