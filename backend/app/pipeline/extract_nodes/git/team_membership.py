import logging
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Set

from app.pipeline.extract_nodes import FeatureNode
from app.pipeline.core.registry import register_feature
from app.pipeline.core.context import ExecutionContext
from app.pipeline.resources import ResourceNames
from app.pipeline.resources.git_history import GitHistoryHandle
from app.pipeline.utils.git_utils import (
    get_commit_info,
    get_author_name,
    get_committer_name,
)
from app.pipeline.feature_metadata.git import TEAM_MEMBERSHIP

logger = logging.getLogger(__name__)


@register_feature(
    name="team_membership",
    requires_resources={
        ResourceNames.GIT_HISTORY,
        ResourceNames.REPO_ENTITY,
        ResourceNames.WORKFLOW_RUN,
    },
    provides={
        "gh_team_size",
        "gh_by_core_team_member",
    },
    group="git",
    description="Team size and core contributor info",
    priority=5,
    feature_metadata=TEAM_MEMBERSHIP,
)
class TeamMembershipNode(FeatureNode):
    LOOKBACK_DAYS = 90

    def extract(self, context: ExecutionContext) -> Dict[str, Any]:
        git_handle: GitHistoryHandle = context.get_resource(ResourceNames.GIT_HISTORY)

        if not git_handle.is_commit_available:
            return {"gh_team_size": 0, "gh_by_core_team_member": False}

        repo_path = git_handle.path
        effective_sha = git_handle.effective_sha

        if not effective_sha:
            return self._empty_result()

        committed_date: Optional[int] = None
        commit_info = get_commit_info(repo_path, effective_sha)
        committed_date = commit_info.get("committed_date")

        if not committed_date:
            return {"gh_team_size": 0, "gh_by_core_team_member": False}

        workflow_run = context.get_resource(ResourceNames.WORKFLOW_RUN)
        ref_date = getattr(workflow_run, "created_at", None) if workflow_run else None
        if not ref_date:
            ref_date = datetime.fromtimestamp(committed_date, tz=timezone.utc)
        if ref_date.tzinfo is None:
            ref_date = ref_date.replace(tzinfo=timezone.utc)

        start_date = ref_date - timedelta(days=self.LOOKBACK_DAYS)

        # 1. Direct committers (excluding PR merges)
        committer_names = self._get_direct_committers(repo_path, start_date, ref_date)

        # 2. PR mergers
        repo = context.get_resource(ResourceNames.REPO_ENTITY)
        merger_logins = self._get_pr_mergers(
            context, str(repo.id), start_date, ref_date
        )

        core_team = committer_names | merger_logins
        gh_team_size = len(core_team)

        # Check if build author is in core team
        is_core_member = False
        author_name = get_author_name(repo_path, effective_sha)
        committer_name = get_committer_name(repo_path, effective_sha)

        if author_name and author_name in core_team:
            is_core_member = True
        elif committer_name and committer_name in core_team:
            is_core_member = True

        return {
            "gh_team_size": gh_team_size,
            "gh_by_core_team_member": is_core_member,
        }

    def _get_direct_committers(
        self, repo_path: Path, start_date: datetime, end_date: datetime
    ) -> Set[str]:
        """Get names of users who pushed directly (not via PR)."""
        pr_pattern = re.compile(r"\s\(#\d+\)")

        try:
            cmd = [
                "git",
                "log",
                "--first-parent",
                "--no-merges",
                f"--since={start_date.isoformat()}",
                f"--until={end_date.isoformat()}",
                "--format=%H|%an|%s",
            ]
            result = subprocess.run(
                cmd, cwd=str(repo_path), capture_output=True, text=True, check=True
            )
            output = result.stdout.strip()
        except subprocess.CalledProcessError:
            return set()

        direct_committers = set()
        for line in output.splitlines():
            if not line.strip():
                continue
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            name, message = parts[1], parts[2]
            if pr_pattern.search(message) or "Merge pull request" in message:
                continue
            direct_committers.add(name)

        return direct_committers

    def _get_pr_mergers(
        self,
        context: ExecutionContext,
        repo_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Set[str]:
        """Get logins of users who triggered PR workflow runs."""
        mergers = set()
        try:
            workflow_run = context.get_resource(ResourceNames.WORKFLOW_RUN)
            if workflow_run and hasattr(workflow_run, "find"):
                cursor = workflow_run.find(
                    {
                        "repo_id": repo_id,
                        "created_at": {"$gte": start_date, "$lte": end_date},
                    }
                )
            else:
                cursor = []

            for doc in cursor:
                payload = doc.get("raw_payload", {})
                pull_requests = payload.get("pull_requests", [])
                is_pr = len(pull_requests) > 0 or payload.get("event") == "pull_request"
                if is_pr:
                    actor = payload.get("triggering_actor", {})
                    login = actor.get("login")
                    if login:
                        mergers.add(login)
        except Exception as e:
            logger.warning(f"Failed to get workflow run actors: {e}")
            context.add_warning(f"Failed to get PR mergers: {e}")

        return mergers

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "gh_team_size": 0,
            "gh_by_core_team_member": False,
        }
