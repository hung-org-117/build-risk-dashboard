"""Feature definitions for Collaboration domain (collaboration.py extractor)."""

from typing import Dict

from app.tasks.pipeline.feature_dag._types import (
    FeatureCategory,
    FeatureDataType,
    FeatureDefinition,
    FeatureResource,
)

COLLABORATION_FEATURES: Dict[str, FeatureDefinition] = {
    # === Build History (from prev_build_history_features) ===
    "history_prev_failed": FeatureDefinition(
        name="history_prev_failed",
        display_name="Previous Build Failed",
        description="Whether the previous build failed",
        category=FeatureCategory.BUILD_HISTORY,
        data_type=FeatureDataType.BOOLEAN,
        extractor_node="collaboration",
        required_resources=[FeatureResource.RAW_BUILD_RUNS, FeatureResource.BUILD_RUN],
        nullable=True,
    ),
    "history_fail_streak": FeatureDefinition(
        name="history_fail_streak",
        display_name="Fail Streak",
        description="Number of consecutive failed builds before this one",
        category=FeatureCategory.BUILD_HISTORY,
        data_type=FeatureDataType.INTEGER,
        extractor_node="collaboration",
        required_resources=[FeatureResource.RAW_BUILD_RUNS, FeatureResource.BUILD_RUN],
    ),
    "history_fail_rate_10": FeatureDefinition(
        name="history_fail_rate_10",
        display_name="Fail Rate Last 10",
        description="Failure rate in last 10 builds",
        category=FeatureCategory.BUILD_HISTORY,
        data_type=FeatureDataType.FLOAT,
        extractor_node="collaboration",
        required_resources=[FeatureResource.RAW_BUILD_RUNS, FeatureResource.BUILD_RUN],
        valid_range=(0.0, 1.0),
    ),
    "history_avg_churn_5": FeatureDefinition(
        name="history_avg_churn_5",
        display_name="Avg Churn Last 5",
        description="Average source code churn in last 5 builds",
        category=FeatureCategory.BUILD_HISTORY,
        data_type=FeatureDataType.FLOAT,
        extractor_node="collaboration",
        required_resources=[FeatureResource.RAW_BUILD_RUNS, FeatureResource.BUILD_RUN],
    ),
    # === Git Entropy/Ratio (from change_entropy_features) ===
    "git_change_entropy": FeatureDefinition(
        name="git_change_entropy",
        display_name="Change Entropy",
        description="Entropy of file changes in the build",
        category=FeatureCategory.GIT_DIFF,
        data_type=FeatureDataType.FLOAT,
        extractor_node="collaboration",
        required_resources=[FeatureResource.GIT_HISTORY],
        valid_range=(0.0, None),
    ),
    "git_files_modified_ratio": FeatureDefinition(
        name="git_files_modified_ratio",
        display_name="Files Modified Ratio",
        description="Ratio of modified files to total changed files",
        category=FeatureCategory.GIT_DIFF,
        data_type=FeatureDataType.FLOAT,
        extractor_node="collaboration",
        required_resources=[FeatureResource.GIT_HISTORY],
        valid_range=(0.0, 1.0),
    ),
    # === Git Churn vs Avg (from git_churn_vs_avg) ===
    "git_churn_vs_avg": FeatureDefinition(
        name="git_churn_vs_avg",
        display_name="Churn vs Average",
        description="Current churn relative to project average",
        category=FeatureCategory.GIT_DIFF,
        data_type=FeatureDataType.FLOAT,
        extractor_node="collaboration",
        required_resources=[
            FeatureResource.GIT_HISTORY,
            FeatureResource.RAW_BUILD_RUNS,
        ],
    ),
    # === Author Experience (from author_experience_features) ===
    "author_is_new": FeatureDefinition(
        name="author_is_new",
        display_name="New Contributor",
        description="Whether author has fewer than 5 builds in this project",
        category=FeatureCategory.COMMITTER,
        data_type=FeatureDataType.BOOLEAN,
        extractor_node="collaboration",
        required_resources=[FeatureResource.RAW_BUILD_RUNS, FeatureResource.BUILD_RUN],
    ),
    "author_ownership": FeatureDefinition(
        name="author_ownership",
        display_name="Author Ownership",
        description="Percentage of project commits by this author",
        category=FeatureCategory.COMMITTER,
        data_type=FeatureDataType.FLOAT,
        extractor_node="collaboration",
        required_resources=[FeatureResource.RAW_BUILD_RUNS, FeatureResource.BUILD_RUN],
        valid_range=(0.0, 1.0),
    ),
    "author_days_since_commit": FeatureDefinition(
        name="author_days_since_commit",
        display_name="Days Since Author's Last Commit",
        description="Days since this author's previous build",
        category=FeatureCategory.COMMITTER,
        data_type=FeatureDataType.FLOAT,
        extractor_node="collaboration",
        required_resources=[FeatureResource.RAW_BUILD_RUNS, FeatureResource.BUILD_RUN],
        unit="days",
        nullable=True,
    ),
}
