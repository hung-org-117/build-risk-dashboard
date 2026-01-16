"""Feature definitions for Temporal/History domain (temporal.py extractor)."""

from typing import Dict

from app.tasks.pipeline.feature_dag._types import (
    FeatureCategory,
    FeatureDataType,
    FeatureDefinition,
    FeatureResource,
)

TEMPORAL_FEATURES: Dict[str, FeatureDefinition] = {
    # === Build Position (from build_position_features) ===
    "percentage_of_builds_before": FeatureDefinition(
        name="percentage_of_builds_before",
        display_name="Percentage of Builds Before",
        description="Percentage of this build's position in the project timeline (0-100)",
        category=FeatureCategory.BUILD_HISTORY,
        data_type=FeatureDataType.FLOAT,
        extractor_node="temporal",
        required_resources=[FeatureResource.RAW_BUILD_RUNS, FeatureResource.BUILD_RUN],
        valid_range=(0.0, 100.0),
    ),
    "number_of_builds_before": FeatureDefinition(
        name="number_of_builds_before",
        display_name="Number of Builds Before",
        description="Number of builds in the project before this one",
        category=FeatureCategory.BUILD_HISTORY,
        data_type=FeatureDataType.INTEGER,
        extractor_node="temporal",
        required_resources=[FeatureResource.RAW_BUILD_RUNS, FeatureResource.BUILD_RUN],
    ),
    # === Build History (from build_history_features) ===
    "history_prev_result": FeatureDefinition(
        name="history_prev_result",
        display_name="Previous Build Result",
        description="Outcome of the previous build (passed, failed, etc.)",
        category=FeatureCategory.BUILD_HISTORY,
        data_type=FeatureDataType.STRING,
        extractor_node="temporal",
        required_resources=[FeatureResource.RAW_BUILD_RUNS, FeatureResource.BUILD_RUN],
        nullable=True,
    ),
    "history_same_committer": FeatureDefinition(
        name="history_same_committer",
        display_name="Same Committer",
        description="Whether committer is same as previous build",
        category=FeatureCategory.BUILD_HISTORY,
        data_type=FeatureDataType.BOOLEAN,
        extractor_node="temporal",
        required_resources=[FeatureResource.RAW_BUILD_RUNS, FeatureResource.BUILD_RUN],
    ),
    "history_days_since_prev": FeatureDefinition(
        name="history_days_since_prev",
        display_name="Time Since Previous Build",
        description="Days since previous build completed",
        category=FeatureCategory.BUILD_HISTORY,
        data_type=FeatureDataType.FLOAT,
        extractor_node="temporal",
        required_resources=[FeatureResource.RAW_BUILD_RUNS, FeatureResource.BUILD_RUN],
        unit="days",
        nullable=True,
    ),
    # === Project Fail History (from project_fail_history_features) ===
    "history_project_fail_rate": FeatureDefinition(
        name="history_project_fail_rate",
        display_name="Project Fail Rate",
        description="Overall fail rate of the project",
        category=FeatureCategory.BUILD_HISTORY,
        data_type=FeatureDataType.FLOAT,
        extractor_node="temporal",
        required_resources=[FeatureResource.RAW_BUILD_RUNS, FeatureResource.BUILD_RUN],
        valid_range=(0.0, 1.0),
    ),
    "history_project_fail_recent": FeatureDefinition(
        name="history_project_fail_recent",
        display_name="Project Recent Fail Rate",
        description="Fail rate in last N builds of the project",
        category=FeatureCategory.BUILD_HISTORY,
        data_type=FeatureDataType.FLOAT,
        extractor_node="temporal",
        required_resources=[FeatureResource.RAW_BUILD_RUNS, FeatureResource.BUILD_RUN],
        valid_range=(0.0, 1.0),
    ),
    # === Author Fail History (from author_fail_history_features) ===
    "author_fail_rate": FeatureDefinition(
        name="author_fail_rate",
        display_name="Author Fail Rate",
        description="Overall fail rate of this committer",
        category=FeatureCategory.COMMITTER,
        data_type=FeatureDataType.FLOAT,
        extractor_node="temporal",
        required_resources=[FeatureResource.RAW_BUILD_RUNS, FeatureResource.BUILD_RUN],
        valid_range=(0.0, 1.0),
    ),
    "author_fail_rate_recent": FeatureDefinition(
        name="author_fail_rate_recent",
        display_name="Author Recent Fail Rate",
        description="Fail rate in last N builds by this committer",
        category=FeatureCategory.COMMITTER,
        data_type=FeatureDataType.FLOAT,
        extractor_node="temporal",
        required_resources=[FeatureResource.RAW_BUILD_RUNS, FeatureResource.BUILD_RUN],
        valid_range=(0.0, 1.0),
    ),
    # === Author Experience (from author_experience) ===
    "author_experience": FeatureDefinition(
        name="author_experience",
        display_name="Author Experience",
        description="Average experience of committers (builds per person)",
        category=FeatureCategory.COMMITTER,
        data_type=FeatureDataType.FLOAT,
        extractor_node="temporal",
        required_resources=[FeatureResource.RAW_BUILD_RUNS, FeatureResource.BUILD_RUN],
    ),
}
