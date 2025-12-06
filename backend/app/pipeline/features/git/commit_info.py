"""
Git Commit Info Node.

Extracts commit-related features:
- All commits included in this build
- Previous built commit
- Resolution status
"""

import logging
from typing import Any, Dict, List, Optional

from app.pipeline.features import FeatureNode
from app.pipeline.core.registry import register_feature
from app.pipeline.core.context import ExecutionContext
from app.pipeline.resources import ResourceNames
from app.pipeline.resources.git_repo import GitRepoHandle
from app.repositories.build_sample import BuildSampleRepository

logger = logging.getLogger(__name__)


@register_feature(
    name="git_commit_info",
    requires_resources={ResourceNames.GIT_REPO},
    provides={
        "git_all_built_commits",
        "git_num_all_built_commits",
        "git_prev_built_commit",
        "git_prev_commit_resolution_status",
        "tr_prev_build",
    },
    group="git",
    priority=10,  # Run early as other git features depend on this
)
class GitCommitInfoNode(FeatureNode):
    """
    Determines which commits are part of this build.
    
    A build may include multiple commits if:
    - Multiple commits pushed before CI triggered
    - Force push with new commits
    - Merge commits
    """
    
    
    def extract(self, context: ExecutionContext) -> Dict[str, Any]:
        git_handle: GitRepoHandle = context.get_resource(ResourceNames.GIT_REPO)
        build_sample = context.build_sample
        db = context.db

        if not git_handle.is_commit_available:
            return {
                "git_all_built_commits": [],
                "git_num_all_built_commits": 0,
                "git_prev_built_commit": None,
                "git_prev_commit_resolution_status": "commit_not_found",
                "tr_prev_build": None,
            }

        effective_sha = git_handle.effective_sha
        repo = git_handle.repo
        
        # We need to find the previous *built* commit in the history of THIS commit
        # This requires walking back from effective_sha until we find a commit that constitutes a completed build
        
        build_stats = self._calculate_build_stats(
            db, build_sample, repo, effective_sha
        )
        
        return build_stats

    def _calculate_build_stats(
        self, db, build_sample, repo, commit_sha: str
    ) -> Dict[str, Any]:
        try:
            build_commit = repo.commit(commit_sha)
        except Exception:
             return {
                "git_all_built_commits": [],
                "git_num_all_built_commits": 0,
                "git_prev_built_commit": None,
                "git_prev_commit_resolution_status": "commit_not_found",
                "tr_prev_build": None,
            }

        prev_commits_objs: List[Any] = [build_commit]
        status = "no_previous_build"
        last_commit = None
        prev_build_id = None
        
        build_coll = db["build_samples"]

        # Ensure repo_id is ObjectId for query
        from bson import ObjectId
        repo_id_query = build_sample.repo_id
        try:
            if isinstance(repo_id_query, str):
                repo_id_query = ObjectId(repo_id_query)
        except Exception:
            pass

        # Limit to avoid infinite loops in weird histories
        walker = repo.iter_commits(commit_sha, max_count=1000)
        first = True

        for commit in walker:
            if first:
                if len(commit.parents) > 1:
                    status = "merge_found"
                    break
                first = False
                continue

            last_commit = commit

            # Check if this commit triggered a build
            existing_build = build_coll.find_one(
                {
                    "repo_id": repo_id_query,
                    "tr_original_commit": commit.hexsha, 
                    "status": "completed",
                    "workflow_run_id": {"$ne": build_sample.workflow_run_id},
                }
            )

            if existing_build:
                status = "build_found"
                prev_build_id = existing_build.get("workflow_run_id")
                break

            prev_commits_objs.append(commit)

            if len(commit.parents) > 1:
                status = "merge_found"
                break

        commits_hex = [c.hexsha for c in prev_commits_objs]
        
        return {
            "git_prev_commit_resolution_status": status,
            "git_prev_built_commit": last_commit.hexsha if last_commit else None,
            "tr_prev_build": prev_build_id,
            "git_all_built_commits": commits_hex,
            "git_num_all_built_commits": len(commits_hex),
        }

