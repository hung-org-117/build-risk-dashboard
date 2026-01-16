"""
Shared enums for entities.

This module contains enums that are used across multiple entity files.
"""

from enum import Enum


class TestFramework(str, Enum):
    """Supported test frameworks for log parsing."""

    # Python
    PYTEST = "pytest"
    UNITTEST = "unittest"
    # Ruby

    TESTUNIT = "testunit"
    CUCUMBER = "cucumber"
    # Java
    JUNIT = "junit"
    TESTNG = "testng"
    # JavaScript/TypeScript
    JEST = "jest"
    MOCHA = "mocha"
    JASMINE = "jasmine"

    # Go
    GOTEST = "gotest"

    # C/C++
    GTEST = "gtest"
    CATCH2 = "catch2"
    CTEST = "ctest"


class ExtractionStatus(str, Enum):
    """Feature extraction status for builds."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class FeatureVectorScope(str, Enum):
    """Scope for FeatureVector entity (Model Training vs Dataset Enrichment)."""

    MODEL = "model_training"
    DATASET = "dataset_enrichment"


class SplitStrategy(str, Enum):
    """Available splitting strategies."""

    RANDOM_SPLIT = "random_split"
    TIME_SERIES_SPLIT = "time_series_split"
    STRATIFIED_SPLIT = "stratified_split"
    STRATIFIED_WITHIN_GROUP = "stratified_within_group"
    L1GO_CV = "l1go_cv"
    L2GO_CV = "l2go_cv"


class GroupByDimension(str, Enum):
    """Available dimensions for grouping data."""

    REPO_LANGUAGE = "repo_language"
    PERCENTAGE_OF_BUILDS_BEFORE = "percentage_of_builds_before"
    NUMBER_OF_BUILDS_BEFORE = "number_of_builds_before"
    TIME_OF_DAY = "time_of_day"
