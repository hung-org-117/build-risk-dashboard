"""
Git Commit Info Node.

Extracts commit-related features:
- All commits included in this build
- Previous built commit
- Resolution status
"""

import logging
from typing import Any, Dict, List, Optional

from app.pipeline.extract_nodes import FeatureNode
from app.pipeline.core.registry import register_feature, OutputFormat
from app.pipeline.core.context import ExecutionContext
from app.pipeline.resources import ResourceNames
from app.pipeline.resources.git_history import GitHistoryHandle
from app.pipeline.utils.git_utils import iter_commit_history
from app.pipeline.feature_metadata.git import COMMIT_INFO

logger = logging.getLogger(__name__)


@register_feature(
    name="git_commit_info",
    requires_resources={
        ResourceNames.GIT_HISTORY,
        ResourceNames.REPO_ENTITY,
        ResourceNames.WORKFLOW_RUN,
    },
    provides={
        "git_all_built_commits",
        "git_num_all_built_commits",
        "git_prev_built_commit",
        "git_prev_commit_resolution_status",
        "tr_prev_build",
    },
    group="git",
    description="Commit history and previous build resolution",
    priority=10,
    output_formats={
        "git_all_built_commits": OutputFormat.HASH_SEPARATED,
    },
    feature_metadata=COMMIT_INFO,
)
class GitCommitInfoNode(FeatureNode):
    """
    Determines which commits are part of this build.
    """

    def extract(self, context: ExecutionContext) -> Dict[str, Any]:
        git_handle: GitHistoryHandle = context.get_resource(ResourceNames.GIT_HISTORY)

        if not git_handle.is_commit_available:
            return {
                "git_all_built_commits": [],
                "git_num_all_built_commits": 0,
                "git_prev_built_commit": None,
                "git_prev_commit_resolution_status": "commit_not_found",
                "tr_prev_build": None,
            }

        effective_sha = git_handle.effective_sha
        repo_path = git_handle.path

        if not effective_sha:
            return self._empty_result()

        build_stats = self._calculate_build_stats(context, repo_path, effective_sha)

        return build_stats

    def _calculate_build_stats(
        self, context: ExecutionContext, repo_path, commit_sha: str
    ) -> Dict[str, Any]:
        """Calculate build stats using subprocess git commands."""
        commits_hex: List[str] = [commit_sha]
        status = "no_previous_build"
        last_commit_sha: Optional[str] = None
        prev_build_id = None

        repo_id = context.get_resource(ResourceNames.REPO_ENTITY).id

        first = True
        for commit_info in iter_commit_history(repo_path, commit_sha, max_count=1000):
            hexsha = commit_info["hexsha"]
            parents = commit_info["parents"]

            if first:
                if len(parents) > 1:
                    status = "merge_found"
                    break
                first = False
                continue

            last_commit_sha = hexsha

            workflow_run_resource = context.get_resource(ResourceNames.WORKFLOW_RUN)
            existing_build = (
                workflow_run_resource.find_one({"head_sha": hexsha, "repo_id": repo_id})
                if hasattr(workflow_run_resource, "find_one")
                else None
            )

            if existing_build:
                status = "build_found"
                prev_build_id = existing_build.get("workflow_run_id")
                break

            commits_hex.append(hexsha)

            if len(parents) > 1:
                status = "merge_found"
                break

        return {
            "git_prev_commit_resolution_status": status,
            "git_prev_built_commit": last_commit_sha,
            "tr_prev_build": prev_build_id,
            "git_all_built_commits": commits_hex,
            "git_num_all_built_commits": len(commits_hex),
        }

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "git_all_built_commits": [],
            "git_num_all_built_commits": 0,
            "git_prev_built_commit": None,
            "git_prev_commit_resolution_status": "commit_not_found",
            "tr_prev_build": None,
        }
