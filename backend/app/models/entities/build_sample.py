from typing import List

from .base import BaseEntity, PyObjectId


class BuildSample(BaseEntity):
    repo_id: PyObjectId
    workflow_run_id: int
    status: str = "pending"  # pending, completed, failed
    error_message: str | None = None

    # Log features
    tr_build_number: int | None = None
    tr_original_commit: str | None = None
    tr_job_ids: List[int] = []
    tr_log_frameworks_all: List[str] = []
    tr_log_num_jobs: int | None = None
    tr_log_tests_run_sum: int | None = None
    tr_log_tests_failed_sum: int | None = None
    tr_log_tests_skipped_sum: int | None = None
    tr_log_tests_ok_sum: int | None = None
    tr_log_tests_fail_rate: float | None = None
    tr_log_testduration_sum: float | None = None
    tr_status: str | None = None
    tr_duration: float | None = None

    # Git Diff features
    git_diff_src_churn: int | None = None
    git_diff_test_churn: int | None = None
    gh_diff_files_added: int | None = None
    gh_diff_files_deleted: int | None = None
    gh_diff_files_modified: int | None = None
    gh_diff_tests_added: int | None = None
    gh_diff_tests_deleted: int | None = None
    gh_diff_src_files: int | None = None
    gh_diff_doc_files: int | None = None
    gh_diff_other_files: int | None = None

    # Repo Snapshot features
    gh_repo_age: float | None = None
    gh_repo_num_commits: int | None = None
    gh_sloc: int | None = None
    gh_test_lines: int | None = None
    gh_test_cases: int | None = None
    gh_asserts: int | None = None

    # GitHub Discussion features
    gh_num_issue_comments: int | None = None
    gh_num_commit_comments: int | None = None
    gh_num_pr_comments: int | None = None
