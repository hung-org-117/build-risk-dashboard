"""
File Touch History Node.

Extracts file-level history metrics:
- gh_num_commits_on_files_touched: Total commits on files modified by this build
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Set

from app.pipeline.extract_nodes import FeatureNode
from app.pipeline.core.registry import register_feature
from app.pipeline.core.context import ExecutionContext
from app.pipeline.resources import ResourceNames
from app.pipeline.resources.git_history import GitHistoryHandle
from app.pipeline.utils.git_utils import (
    get_committed_date,
    get_commit_parents,
    get_diff_files,
    git_log_files,
)
from app.pipeline.feature_metadata.git import FILE_TOUCH_HISTORY

logger = logging.getLogger(__name__)


@register_feature(
    name="file_touch_history",
    requires_resources={ResourceNames.GIT_HISTORY, ResourceNames.WORKFLOW_RUN},
    requires_features={"git_all_built_commits"},
    provides={
        "gh_num_commits_on_files_touched",
    },
    group="git",
    description="File modification history",
    priority=3,
    feature_metadata=FILE_TOUCH_HISTORY,
)
class FileTouchHistoryNode(FeatureNode):
    LOOKBACK_DAYS = 90
    CHUNK_SIZE = 50

    def extract(self, context: ExecutionContext) -> Dict[str, Any]:
        git_handle: GitHistoryHandle = context.get_resource(ResourceNames.GIT_HISTORY)

        if not git_handle.is_commit_available:
            return {"gh_num_commits_on_files_touched": 0}

        repo_path = git_handle.path
        effective_sha = git_handle.effective_sha
        built_commits = context.get_feature("git_all_built_commits", [])

        if not built_commits:
            return {"gh_num_commits_on_files_touched": 0}

        workflow_run = context.get_resource(ResourceNames.WORKFLOW_RUN)
        ref_date = getattr(workflow_run, "created_at", None) if workflow_run else None
        if not ref_date:
            committed_date = get_committed_date(repo_path, effective_sha)
            if committed_date:
                ref_date = datetime.fromtimestamp(committed_date, tz=timezone.utc)
            else:
                return {"gh_num_commits_on_files_touched": 0}

        if ref_date.tzinfo is None:
            ref_date = ref_date.replace(tzinfo=timezone.utc)

        start_date = ref_date - timedelta(days=self.LOOKBACK_DAYS)

        num_commits = self._calculate_file_history(
            context, repo_path, built_commits, effective_sha, start_date
        )

        return {"gh_num_commits_on_files_touched": num_commits}

    def _calculate_file_history(
        self,
        context,
        repo_path,
        built_commits: List[str],
        head_sha: str,
        start_date: datetime,
    ) -> int:
        """Calculate number of commits touching files modified in this build."""
        # Collect files touched by this build
        files_touched: Set[str] = set()

        for sha in built_commits:
            parents = get_commit_parents(repo_path, sha)
            if parents:
                diff_files = get_diff_files(repo_path, parents[0], sha)
                for f in diff_files:
                    if f.get("b_path"):
                        files_touched.add(f["b_path"])
                    if f.get("a_path"):
                        files_touched.add(f["a_path"])

        if not files_touched:
            return 0

        # Count commits on these files
        paths = list(files_touched)
        start_iso = start_date.isoformat()
        trigger_sha = built_commits[0] if built_commits else head_sha

        try:
            all_shas = git_log_files(
                repo_path, trigger_sha, start_iso, paths, self.CHUNK_SIZE
            )

            # Exclude commits that are part of this build
            for sha in built_commits:
                all_shas.discard(sha)

            return len(all_shas)
        except Exception as e:
            logger.warning(f"Failed to count commits on files: {e}")
            context.add_warning(f"Failed to count commits on files: {e}")
            return 0
