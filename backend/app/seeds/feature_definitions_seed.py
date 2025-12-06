"""
Feature Definitions Seed Data.

Usage:
    python -m app.seeds.feature_definitions_seed
"""

from typing import List

from app.models.entities.dataset import DatasetMapping
from app.models.entities.dataset_template import DatasetTemplate
from app.models.entities.feature_definition import (
    FeatureDefinition,
    FeatureSource,
    FeatureDataType,
    FeatureCategory,
)
from app.repositories.dataset_template_repository import DatasetTemplateRepository
from app.repositories.feature_definition import FeatureDefinitionRepository


def get_feature_definitions() -> List[FeatureDefinition]:
    """Return all feature definitions."""
    return [
        FeatureDefinition(
            _id=None,
            name="tr_jobs",
            display_name="Job IDs",
            description="List of job IDs in this workflow run",
            category=FeatureCategory.BUILD_LOG,
            source=FeatureSource.BUILD_LOG,
            extractor_node="build_log_features",
            depends_on_resources=["log_storage", "workflow_run"],
            data_type=FeatureDataType.LIST_INTEGER,
            example_value="[12345, 12346, 12347]",
        ),
        FeatureDefinition(
            _id=None,
            name="tr_build_id",
            display_name="Build ID",
            description="GitHub workflow run ID",
            category=FeatureCategory.BUILD_LOG,
            source=FeatureSource.WORKFLOW_RUN,
            extractor_node="build_log_features",
            depends_on_resources=["workflow_run"],
            data_type=FeatureDataType.INTEGER,
            example_value="1234567890",
        ),
        FeatureDefinition(
            _id=None,
            name="tr_build_number",
            display_name="Build Number",
            description="Sequential build number in the repository",
            category=FeatureCategory.BUILD_LOG,
            source=FeatureSource.WORKFLOW_RUN,
            extractor_node="build_log_features",
            depends_on_resources=["workflow_run"],
            data_type=FeatureDataType.INTEGER,
            example_value="42",
        ),
        FeatureDefinition(
            _id=None,
            name="tr_original_commit",
            display_name="Trigger Commit SHA",
            description="Git commit SHA that triggered this build",
            category=FeatureCategory.BUILD_LOG,
            source=FeatureSource.WORKFLOW_RUN,
            extractor_node="build_log_features",
            depends_on_resources=["workflow_run"],
            data_type=FeatureDataType.STRING,
            example_value="abc123def456",
        ),
        FeatureDefinition(
            _id=None,
            name="tr_log_lan_all",
            display_name="Source Languages",
            description="Programming languages detected in the repository",
            category=FeatureCategory.BUILD_LOG,
            source=FeatureSource.METADATA,
            extractor_node="build_log_features",
            data_type=FeatureDataType.LIST_STRING,
            example_value='["java", "python"]',
        ),
        FeatureDefinition(
            _id=None,
            name="tr_log_frameworks_all",
            display_name="Test Frameworks",
            description="Test frameworks detected in build logs",
            category=FeatureCategory.BUILD_LOG,
            source=FeatureSource.BUILD_LOG,
            extractor_node="build_log_features",
            depends_on_resources=["log_storage"],
            data_type=FeatureDataType.LIST_STRING,
            example_value='["junit", "pytest"]',
        ),
        FeatureDefinition(
            _id=None,
            name="tr_log_num_jobs",
            display_name="Number of Jobs",
            description="Total number of CI jobs in the workflow run",
            category=FeatureCategory.BUILD_LOG,
            source=FeatureSource.BUILD_LOG,
            extractor_node="build_log_features",
            depends_on_resources=["log_storage"],
            data_type=FeatureDataType.INTEGER,
            example_value="3",
        ),
        FeatureDefinition(
            _id=None,
            name="tr_log_tests_run_sum",
            display_name="Tests Run",
            description="Total number of tests executed across all jobs",
            category=FeatureCategory.BUILD_LOG,
            source=FeatureSource.BUILD_LOG,
            extractor_node="build_log_features",
            depends_on_resources=["log_storage"],
            data_type=FeatureDataType.INTEGER,
            example_value="150",
        ),
        FeatureDefinition(
            _id=None,
            name="tr_log_tests_failed_sum",
            display_name="Tests Failed",
            description="Total number of failed tests across all jobs",
            category=FeatureCategory.BUILD_LOG,
            source=FeatureSource.BUILD_LOG,
            extractor_node="build_log_features",
            depends_on_resources=["log_storage"],
            data_type=FeatureDataType.INTEGER,
            example_value="2",
        ),
        FeatureDefinition(
            _id=None,
            name="tr_log_tests_skipped_sum",
            display_name="Tests Skipped",
            description="Total number of skipped tests across all jobs",
            category=FeatureCategory.BUILD_LOG,
            source=FeatureSource.BUILD_LOG,
            extractor_node="build_log_features",
            depends_on_resources=["log_storage"],
            data_type=FeatureDataType.INTEGER,
            example_value="5",
        ),
        FeatureDefinition(
            _id=None,
            name="tr_log_tests_ok_sum",
            display_name="Tests Passed",
            description="Total number of passed tests across all jobs",
            category=FeatureCategory.BUILD_LOG,
            source=FeatureSource.BUILD_LOG,
            extractor_node="build_log_features",
            depends_on_resources=["log_storage"],
            data_type=FeatureDataType.INTEGER,
            example_value="143",
        ),
        FeatureDefinition(
            _id=None,
            name="tr_log_tests_fail_rate",
            display_name="Test Failure Rate",
            description="Ratio of failed tests to total tests run",
            category=FeatureCategory.BUILD_LOG,
            source=FeatureSource.DERIVED,
            extractor_node="build_log_features",
            depends_on_features=["tr_log_tests_run_sum", "tr_log_tests_failed_sum"],
            data_type=FeatureDataType.FLOAT,
            example_value="0.013",
            unit="ratio",
        ),
        FeatureDefinition(
            _id=None,
            name="tr_log_testduration_sum",
            display_name="Test Duration",
            description="Total test execution time across all jobs",
            category=FeatureCategory.BUILD_LOG,
            source=FeatureSource.BUILD_LOG,
            extractor_node="build_log_features",
            depends_on_resources=["log_storage"],
            data_type=FeatureDataType.FLOAT,
            example_value="45.5",
            unit="seconds",
        ),
        FeatureDefinition(
            _id=None,
            name="tr_status",
            display_name="Build Status",
            description="Final status of the build (passed, failed, cancelled)",
            category=FeatureCategory.BUILD_LOG,
            source=FeatureSource.WORKFLOW_RUN,
            extractor_node="build_log_features",
            depends_on_resources=["workflow_run"],
            data_type=FeatureDataType.STRING,
            example_value="passed",
        ),
        FeatureDefinition(
            _id=None,
            name="tr_duration",
            display_name="Build Duration",
            description="Total build duration from start to finish",
            category=FeatureCategory.BUILD_LOG,
            source=FeatureSource.WORKFLOW_RUN,
            extractor_node="build_log_features",
            depends_on_resources=["workflow_run"],
            data_type=FeatureDataType.FLOAT,
            example_value="120.5",
            unit="seconds",
        ),
        # ========================================================================
        # GIT COMMIT INFO FEATURES (git_*)
        # Extracted from: git_commit_info node
        # Source: Git repository
        # ========================================================================
        FeatureDefinition(
            _id=None,
            name="git_all_built_commits",
            display_name="All Built Commits",
            description="List of all commit SHAs included in this build",
            category=FeatureCategory.GIT_HISTORY,
            source=FeatureSource.GIT_REPO,
            extractor_node="git_commit_info",
            depends_on_resources=["git_repo"],
            data_type=FeatureDataType.LIST_STRING,
            example_value='["abc123", "def456"]',
        ),
        FeatureDefinition(
            _id=None,
            name="git_num_all_built_commits",
            display_name="Number of Commits",
            description="Number of commits included in this build",
            category=FeatureCategory.GIT_HISTORY,
            source=FeatureSource.DERIVED,
            extractor_node="git_commit_info",
            depends_on_features=["git_all_built_commits"],
            data_type=FeatureDataType.INTEGER,
            example_value="3",
        ),
        FeatureDefinition(
            _id=None,
            name="git_prev_built_commit",
            display_name="Previous Built Commit",
            description="SHA of the previous successfully built commit",
            category=FeatureCategory.GIT_HISTORY,
            source=FeatureSource.GIT_REPO,
            extractor_node="git_commit_info",
            depends_on_resources=["git_repo"],
            data_type=FeatureDataType.STRING,
            example_value="abc123def456",
        ),
        FeatureDefinition(
            _id=None,
            name="git_prev_commit_resolution_status",
            display_name="Previous Commit Resolution",
            description="Status of finding previous build (found, first_build, not_in_lineage, commit_not_found)",
            category=FeatureCategory.GIT_HISTORY,
            source=FeatureSource.GIT_REPO,
            extractor_node="git_commit_info",
            depends_on_resources=["git_repo"],
            data_type=FeatureDataType.STRING,
            example_value="found",
        ),
        FeatureDefinition(
            _id=None,
            name="tr_prev_build",
            display_name="Previous Build ID",
            description="Workflow run ID of the previous build",
            category=FeatureCategory.GIT_HISTORY,
            source=FeatureSource.GIT_REPO,
            extractor_node="git_commit_info",
            depends_on_resources=["git_repo"],
            data_type=FeatureDataType.INTEGER,
            example_value="1234567889",
        ),
        # ========================================================================
        # GIT DIFF FEATURES (git_diff_*, gh_diff_*)
        # Extracted from: git_diff_features node
        # Source: Git repository diffs
        # ========================================================================
        FeatureDefinition(
            _id=None,
            name="git_diff_src_churn",
            display_name="Source Code Churn",
            description="Total lines added + deleted in source files",
            category=FeatureCategory.GIT_DIFF,
            source=FeatureSource.GIT_REPO,
            extractor_node="git_diff_features",
            depends_on_resources=["git_repo"],
            depends_on_features=["git_all_built_commits", "git_prev_built_commit"],
            data_type=FeatureDataType.INTEGER,
            example_value="150",
            unit="lines",
        ),
        FeatureDefinition(
            _id=None,
            name="git_diff_test_churn",
            display_name="Test Code Churn",
            description="Total lines added + deleted in test files",
            category=FeatureCategory.GIT_DIFF,
            source=FeatureSource.GIT_REPO,
            extractor_node="git_diff_features",
            depends_on_resources=["git_repo"],
            depends_on_features=["git_all_built_commits"],
            data_type=FeatureDataType.INTEGER,
            example_value="50",
            unit="lines",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_diff_files_added",
            display_name="Files Added",
            description="Number of new files added",
            category=FeatureCategory.GIT_DIFF,
            source=FeatureSource.GIT_REPO,
            extractor_node="git_diff_features",
            depends_on_resources=["git_repo"],
            depends_on_features=["git_all_built_commits"],
            data_type=FeatureDataType.INTEGER,
            example_value="2",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_diff_files_deleted",
            display_name="Files Deleted",
            description="Number of files deleted",
            category=FeatureCategory.GIT_DIFF,
            source=FeatureSource.GIT_REPO,
            extractor_node="git_diff_features",
            depends_on_resources=["git_repo"],
            depends_on_features=["git_all_built_commits"],
            data_type=FeatureDataType.INTEGER,
            example_value="1",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_diff_files_modified",
            display_name="Files Modified",
            description="Number of files modified",
            category=FeatureCategory.GIT_DIFF,
            source=FeatureSource.GIT_REPO,
            extractor_node="git_diff_features",
            depends_on_resources=["git_repo"],
            depends_on_features=["git_all_built_commits"],
            data_type=FeatureDataType.INTEGER,
            example_value="5",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_diff_tests_added",
            display_name="Test Cases Added",
            description="Number of new test cases added",
            category=FeatureCategory.GIT_DIFF,
            source=FeatureSource.GIT_REPO,
            extractor_node="git_diff_features",
            depends_on_resources=["git_repo"],
            depends_on_features=["git_prev_built_commit"],
            data_type=FeatureDataType.INTEGER,
            example_value="3",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_diff_tests_deleted",
            display_name="Test Cases Deleted",
            description="Number of test cases deleted",
            category=FeatureCategory.GIT_DIFF,
            source=FeatureSource.GIT_REPO,
            extractor_node="git_diff_features",
            depends_on_resources=["git_repo"],
            depends_on_features=["git_prev_built_commit"],
            data_type=FeatureDataType.INTEGER,
            example_value="0",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_diff_src_files",
            display_name="Source Files Changed",
            description="Number of source/programming files changed",
            category=FeatureCategory.GIT_DIFF,
            source=FeatureSource.GIT_REPO,
            extractor_node="git_diff_features",
            depends_on_resources=["git_repo"],
            depends_on_features=["git_all_built_commits"],
            data_type=FeatureDataType.INTEGER,
            example_value="4",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_diff_doc_files",
            display_name="Doc Files Changed",
            description="Number of documentation files changed",
            category=FeatureCategory.GIT_DIFF,
            source=FeatureSource.GIT_REPO,
            extractor_node="git_diff_features",
            depends_on_resources=["git_repo"],
            depends_on_features=["git_all_built_commits"],
            data_type=FeatureDataType.INTEGER,
            example_value="1",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_diff_other_files",
            display_name="Other Files Changed",
            description="Number of other files changed (config, assets, etc.)",
            category=FeatureCategory.GIT_DIFF,
            source=FeatureSource.GIT_REPO,
            extractor_node="git_diff_features",
            depends_on_resources=["git_repo"],
            depends_on_features=["git_all_built_commits"],
            data_type=FeatureDataType.INTEGER,
            example_value="2",
        ),
        # ========================================================================
        # TEAM STATS FEATURES (gh_team_*, gh_by_core_*)
        # Extracted from: team_stats_features node
        # Source: Git repository commit history
        # ========================================================================
        FeatureDefinition(
            _id=None,
            name="gh_team_size",
            display_name="Team Size",
            description="Number of unique contributors in last 90 days",
            category=FeatureCategory.TEAM,
            source=FeatureSource.GIT_REPO,
            extractor_node="team_stats_features",
            depends_on_resources=["git_repo"],
            depends_on_features=["git_all_built_commits"],
            data_type=FeatureDataType.INTEGER,
            example_value="5",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_by_core_team_member",
            display_name="By Core Team Member",
            description="Whether the commit author is a core team member (≥5% of commits)",
            category=FeatureCategory.TEAM,
            source=FeatureSource.GIT_REPO,
            extractor_node="team_stats_features",
            depends_on_resources=["git_repo"],
            data_type=FeatureDataType.BOOLEAN,
            example_value="true",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_num_commits_on_files_touched",
            display_name="File History Commits",
            description="Total commits historically made on files touched by this build",
            category=FeatureCategory.TEAM,
            source=FeatureSource.GIT_REPO,
            extractor_node="team_stats_features",
            depends_on_resources=["git_repo"],
            depends_on_features=["git_all_built_commits"],
            data_type=FeatureDataType.INTEGER,
            example_value="42",
        ),
        # ========================================================================
        # REPO SNAPSHOT FEATURES (gh_repo_*, gh_sloc_*)
        # Extracted from: repo_snapshot_features node
        # Source: Git repository at specific commit
        # ========================================================================
        FeatureDefinition(
            _id=None,
            name="gh_repo_age",
            display_name="Repository Age",
            description="Age of repository in days since first commit",
            category=FeatureCategory.REPO_SNAPSHOT,
            source=FeatureSource.GIT_REPO,
            extractor_node="repo_snapshot_features",
            depends_on_resources=["git_repo"],
            data_type=FeatureDataType.FLOAT,
            example_value="365.5",
            unit="days",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_repo_num_commits",
            display_name="Total Commits",
            description="Total number of commits in repository history",
            category=FeatureCategory.REPO_SNAPSHOT,
            source=FeatureSource.GIT_REPO,
            extractor_node="repo_snapshot_features",
            depends_on_resources=["git_repo"],
            data_type=FeatureDataType.INTEGER,
            example_value="500",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_sloc",
            display_name="Source Lines of Code",
            description="Total source lines of code in repository",
            category=FeatureCategory.REPO_SNAPSHOT,
            source=FeatureSource.GIT_REPO,
            extractor_node="repo_snapshot_features",
            depends_on_resources=["git_repo"],
            data_type=FeatureDataType.INTEGER,
            example_value="15000",
            unit="lines",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_test_lines_per_kloc",
            display_name="Test Lines per KLOC",
            description="Test code lines per 1000 source lines",
            category=FeatureCategory.REPO_SNAPSHOT,
            source=FeatureSource.DERIVED,
            extractor_node="repo_snapshot_features",
            depends_on_features=["gh_sloc"],
            data_type=FeatureDataType.FLOAT,
            example_value="250.5",
            unit="lines/KLOC",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_test_cases_per_kloc",
            display_name="Test Cases per KLOC",
            description="Number of test cases per 1000 source lines",
            category=FeatureCategory.REPO_SNAPSHOT,
            source=FeatureSource.DERIVED,
            extractor_node="repo_snapshot_features",
            depends_on_features=["gh_sloc"],
            data_type=FeatureDataType.FLOAT,
            example_value="15.2",
            unit="tests/KLOC",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_asserts_case_per_kloc",
            display_name="Assertions per KLOC",
            description="Number of assertions per 1000 source lines",
            category=FeatureCategory.REPO_SNAPSHOT,
            source=FeatureSource.DERIVED,
            extractor_node="repo_snapshot_features",
            depends_on_features=["gh_sloc"],
            data_type=FeatureDataType.FLOAT,
            example_value="45.7",
            unit="asserts/KLOC",
        ),
        # ========================================================================
        # METADATA FEATURES
        # Extracted from: repo_snapshot_features node
        # Source: Repository and workflow run metadata
        # ========================================================================
        FeatureDefinition(
            _id=None,
            name="gh_project_name",
            display_name="Project Name",
            description="Full name of the repository (owner/repo)",
            category=FeatureCategory.METADATA,
            source=FeatureSource.METADATA,
            extractor_node="repo_snapshot_features",
            data_type=FeatureDataType.STRING,
            example_value="owner/repo-name",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_is_pr",
            display_name="Is Pull Request",
            description="Whether this build was triggered by a pull request",
            category=FeatureCategory.PR_INFO,
            source=FeatureSource.WORKFLOW_RUN,
            extractor_node="repo_snapshot_features",
            depends_on_resources=["workflow_run"],
            data_type=FeatureDataType.BOOLEAN,
            example_value="true",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_pr_created_at",
            display_name="PR Created At",
            description="Timestamp when the pull request was created",
            category=FeatureCategory.PR_INFO,
            source=FeatureSource.WORKFLOW_RUN,
            extractor_node="repo_snapshot_features",
            depends_on_resources=["workflow_run"],
            data_type=FeatureDataType.STRING,
            example_value="2024-01-15T10:30:00Z",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_pull_req_num",
            display_name="PR Number",
            description="Pull request number",
            category=FeatureCategory.PR_INFO,
            source=FeatureSource.WORKFLOW_RUN,
            extractor_node="repo_snapshot_features",
            depends_on_resources=["workflow_run"],
            data_type=FeatureDataType.INTEGER,
            example_value="42",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_lang",
            display_name="Primary Language",
            description="Primary programming language of the repository",
            category=FeatureCategory.METADATA,
            source=FeatureSource.METADATA,
            extractor_node="repo_snapshot_features",
            data_type=FeatureDataType.STRING,
            example_value="Python",
        ),
        FeatureDefinition(
            _id=None,
            name="git_branch",
            display_name="Branch Name",
            description="Git branch that triggered the build",
            category=FeatureCategory.METADATA,
            source=FeatureSource.WORKFLOW_RUN,
            extractor_node="repo_snapshot_features",
            depends_on_resources=["workflow_run"],
            data_type=FeatureDataType.STRING,
            example_value="feature/new-feature",
        ),
        FeatureDefinition(
            _id=None,
            name="git_trigger_commit",
            display_name="Trigger Commit",
            description="Git commit SHA that triggered this build",
            category=FeatureCategory.METADATA,
            source=FeatureSource.WORKFLOW_RUN,
            extractor_node="repo_snapshot_features",
            depends_on_resources=["workflow_run"],
            data_type=FeatureDataType.STRING,
            example_value="abc123def456",
        ),
        FeatureDefinition(
            _id=None,
            name="ci_provider",
            display_name="CI Provider",
            description="Continuous Integration provider (github_actions, etc.)",
            category=FeatureCategory.METADATA,
            source=FeatureSource.METADATA,
            extractor_node="repo_snapshot_features",
            data_type=FeatureDataType.STRING,
            example_value="github_actions",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_build_started_at",
            display_name="Build Started At",
            description="Timestamp when the build started",
            category=FeatureCategory.METADATA,
            source=FeatureSource.WORKFLOW_RUN,
            extractor_node="repo_snapshot_features",
            depends_on_resources=["workflow_run"],
            data_type=FeatureDataType.DATETIME,
            example_value="2024-01-15T10:30:00Z",
        ),
        # ========================================================================
        # GITHUB DISCUSSION FEATURES (gh_num_*_comments)
        # Extracted from: github_discussion_features node
        # Source: GitHub API
        # ========================================================================
        FeatureDefinition(
            _id=None,
            name="gh_num_issue_comments",
            display_name="Issue Comments",
            description="Number of issue comments in 24h window before build",
            category=FeatureCategory.DISCUSSION,
            source=FeatureSource.GITHUB_API,
            extractor_node="github_discussion_features",
            depends_on_resources=["github_client", "workflow_run"],
            depends_on_features=["git_all_built_commits"],
            data_type=FeatureDataType.INTEGER,
            example_value="5",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_num_commit_comments",
            display_name="Commit Comments",
            description="Number of comments on commits in this build",
            category=FeatureCategory.DISCUSSION,
            source=FeatureSource.GITHUB_API,
            extractor_node="github_discussion_features",
            depends_on_resources=["github_client"],
            depends_on_features=["git_all_built_commits"],
            data_type=FeatureDataType.INTEGER,
            example_value="2",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_num_pr_comments",
            display_name="PR Comments",
            description="Number of pull request review comments",
            category=FeatureCategory.DISCUSSION,
            source=FeatureSource.GITHUB_API,
            extractor_node="github_discussion_features",
            depends_on_resources=["github_client"],
            data_type=FeatureDataType.INTEGER,
            example_value="8",
        ),
        FeatureDefinition(
            _id=None,
            name="gh_description_complexity",
            display_name="PR Description Complexity",
            description="Word count of PR title + body",
            category=FeatureCategory.DISCUSSION,
            source=FeatureSource.GITHUB_API,
            extractor_node="github_discussion_features",
            depends_on_resources=["github_client", "workflow_run"],
            data_type=FeatureDataType.INTEGER,
            example_value="150",
            unit="words",
        ),
    ]


def _seed_feature_definitions(db) -> tuple[int, List[FeatureDefinition]]:
    """Seed or update all feature definitions, returning count and list."""
    repo = FeatureDefinitionRepository(db)
    features = get_feature_definitions()
    count = repo.bulk_upsert(features)
    return count, features


def _seed_dataset_template_travistorrent(
    db, features: List[FeatureDefinition]
) -> DatasetTemplate:
    """
    Ensure a dataset template named 'travistorrent' exists containing all feature names.
    Upserts the dataset template document.
    """
    dataset_template_repo = DatasetTemplateRepository(db)
    feature_names = [f.name for f in features]

    dataset_template = DatasetTemplate(
        _id=None,
        name="travistorrent",
        description="TravisTorrent dataset",
        file_name="travistorrent.csv",
        source="seed",
        rows=0,
        size_mb=0.0,
        columns=feature_names,
        mapped_fields=DatasetMapping(
            build_id="tr_build_id",
            commit_sha="tr_original_commit",
            repo_name="gh_project_name",
            timestamp=None,
        ),
        tags=["travistorrent"],
        selected_template="all_features",
        selected_features=feature_names,
        preview=[],
    )

    existing = dataset_template_repo.find_one({"name": "travistorrent"})
    if existing and existing.id:
        dataset_template_repo.update_one(
            existing.id, dataset_template.model_dump(by_alias=True, exclude_none=True)
        )
        return dataset_template_repo.find_by_id(existing.id)
    return dataset_template_repo.insert_one(dataset_template)


def seed_up(db) -> dict:
    """Run the seed (features + dataset template)."""
    feature_count, features = _seed_feature_definitions(db)
    dataset_template = _seed_dataset_template_travistorrent(db, features)
    return {
        "features_seeded": feature_count,
        "dataset_template_id": str(dataset_template.id)
        if dataset_template and dataset_template.id
        else None,
        "dataset_template_name": dataset_template.name if dataset_template else None,
    }


def seed_down(db) -> dict:
    """Rollback seed: remove travistorrent dataset template and all feature definitions."""
    feat_repo = FeatureDefinitionRepository(db)
    dataset_template_repo = DatasetTemplateRepository(db)

    features_deleted = feat_repo.delete_many({})
    dataset_templates_deleted = dataset_template_repo.delete_many(
        {"name": "travistorrent"}
    )

    return {
        "features_deleted": features_deleted,
        "dataset_templates_deleted": dataset_templates_deleted,
    }


def seed_features(db) -> int:
    """
    Backward-compatible seeding for API callers: seeds everything, returns feature count.
    """
    result = seed_up(db)
    return result["features_seeded"]


if __name__ == "__main__":
    """Run this script directly to seed features and dataset template."""
    import sys
    from app.database.mongo import get_database

    print("Seeding feature definitions and travistorrent dataset template...")

    try:
        db = get_database()
        result = seed_up(db)
        print(
            "Seeded "
            f"{result['features_seeded']} feature definitions and ensured dataset template "
            f"'{result['dataset_template_name']}'."
        )
    except Exception as e:
        print(f"Error seeding features: {e}", file=sys.stderr)
        sys.exit(1)
