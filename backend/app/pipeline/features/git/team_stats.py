"""
Team Stats Feature Node.

Extracts team-related metrics:
- Team size
- Core team membership
- File touch history
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

from app.pipeline.features import FeatureNode
from app.pipeline.core.registry import register_feature
from app.pipeline.core.context import ExecutionContext
from app.pipeline.resources import ResourceNames
from app.pipeline.resources.git_repo import GitRepoHandle

logger = logging.getLogger(__name__)


@register_feature(
    name="team_stats_features",
    requires_resources={ResourceNames.GIT_REPO},
    requires_features={"git_all_built_commits"},
    provides={
        "gh_team_size",
        "gh_by_core_team_member",
        "gh_num_commits_on_files_touched",
    },
    group="git",
)
class TeamStatsNode(FeatureNode):
    """
    Calculates team-related metrics.
    
    - Team size: unique contributors in last 3 months
    - Core team: author contributed ≥5% of commits in last 3 months
    - File history: total commits on files touched by this build
    """
    
    LOOKBACK_DAYS = 90
    CORE_TEAM_THRESHOLD = 0.05  # 5% of commits
    
    
    def extract(self, context: ExecutionContext) -> Dict[str, Any]:
        git_handle: GitRepoHandle = context.get_resource(ResourceNames.GIT_REPO)
        
        if not git_handle.is_commit_available:
            return self._empty_result()
        
        repo = git_handle.repo
        effective_sha = git_handle.effective_sha
        built_commits = context.get_feature("git_all_built_commits", [])
        build_sample = context.build_sample
        db = context.db

        # Get current commit for author info
        try:
            current_commit = repo.commit(effective_sha)
        except Exception:
            return self._empty_result()
        
        ref_date = build_sample.created_at # Assuming created_at exists, or fallback to commit date
        if not ref_date:
             ref_date = datetime.fromtimestamp(current_commit.committed_date, tz=timezone.utc)
        
        # Ensure ref_date is timezone aware
        if ref_date.tzinfo is None:
             ref_date = ref_date.replace(tzinfo=timezone.utc)

        start_date = ref_date - timedelta(days=self.LOOKBACK_DAYS)
        
        # 1. Committer Team: Direct pushers (excluding PR merges, squash, rebase)
        committer_names = self._get_direct_committers(
            git_handle.path, start_date, ref_date
        )

        # 2. Merger Team: People who merged PRs OR triggered workflow runs (PR/Push)
        # We need to query workflow runs. In build-risk, we might need a repository for this.
        # Assuming we can access the collection directly or via a service.
        merger_logins = self._get_pr_mergers(db, str(build_sample.repo_id), start_date, ref_date)

        core_team = committer_names | merger_logins
        gh_team_size = len(core_team)

        # Check if the build trigger author is in the core team
        is_core_member = False
        try:
            trigger_commit = repo.commit(effective_sha)
            author_name = trigger_commit.author.name
            committer_name = trigger_commit.committer.name

            if author_name in core_team or committer_name in core_team:
                is_core_member = True

        except Exception:
            pass
        
        # File touch history
        num_commits_on_files = 0
        if built_commits:
             num_commits_on_files = self._calculate_file_history_optimized(
                repo, built_commits, effective_sha, start_date
            )
        
        return {
            "gh_team_size": gh_team_size,
            "gh_by_core_team_member": is_core_member,
            "gh_num_commits_on_files_touched": num_commits_on_files,
        }

    def _get_direct_committers(
        self, repo_path: Path, start_date: datetime, end_date: datetime
    ) -> Set[str]:
        """
        Get NAMES of users who pushed directly to the main branch (not via PR).
        Filters out PR merges, Squash merges, and Rebase merges using regex.
        """
        import re
        import subprocess

        # Regex to detect Squash/Rebase PRs (e.g., "Subject (#123)")
        pr_pattern = re.compile(r"\s\(#\d+\)")

        try:
            # git log --first-parent --no-merges --since=... --format="%H|%an|%s"
            # %an = author name
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
                cmd,
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                check=True,
            )
            output = result.stdout.strip()
            
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to get direct committers: {e}")
            return set()

        direct_committers = set()
        for line in output.splitlines():
            if not line.strip():
                continue

            parts = line.split("|", 2)
            if len(parts) < 3:
                continue

            name = parts[1]
            message = parts[2]

            # Filter out Squash/Rebase PRs
            if pr_pattern.search(message):
                continue

            # Filter out standard GitHub merge messages
            if "Merge pull request" in message:
                continue

            direct_committers.add(name)

        return direct_committers

    def _get_pr_mergers(
        self, db, repo_id: str, start_date: datetime, end_date: datetime
    ) -> Set[str]:
        """
        Get logins of users who triggered PR workflow runs in the given time window.
        """
        mergers = set()

        try:
             # Query workflow_runs collection, matching the structure in WorkflowRunRepository
             from bson import ObjectId
             
             try:
                 oid = ObjectId(repo_id)
             except Exception:
                 oid = repo_id

             cursor = db["workflow_runs"].find({
                 "repo_id": oid,
                 "created_at": {"$gte": start_date, "$lte": end_date}
             })
             
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

        return mergers

    def _calculate_file_history_optimized(
        self, 
        repo, 
        built_commits: List[str],
        head_sha: str,
        start_date: datetime,
        chunk_size=50
    ) -> int:
        """Calculate total commits on files touched by this build using git log pathspecs."""
        
        # Files Touched
        files_touched: Set[str] = set()
        for sha in built_commits:
            try:
                commit = repo.commit(sha)
                if commit.parents:
                    diffs = commit.diff(commit.parents[0])
                    for d in diffs:
                        if d.b_path:
                            files_touched.add(d.b_path)
                        if d.a_path:
                            files_touched.add(d.a_path)
            except Exception:
                pass

        if not files_touched:
            return 0
            
        num_commits_on_files = 0
        try:
            all_shas = set()
            paths = list(files_touched)
            trigger_sha = built_commits[0] 

            # Start date for log
            start_iso = start_date.isoformat()

            for i in range(0, len(paths), chunk_size):
                chunk = paths[i : i + chunk_size]
                # git log --since=... --format=%H -- [paths]
                commits_on_files = repo.git.log(
                    trigger_sha,
                    "--since",
                    start_iso,
                    "--format=%H",
                    "--",
                    *chunk,
                ).splitlines()
                all_shas.update(set(commits_on_files))

            # Exclude the built commits themselves if desired? 
            # Buildguard: `for sha in built_commits: if sha in all_shas: all_shas.remove(sha)`
            for sha in built_commits:
                if sha in all_shas:
                    all_shas.remove(sha)

            num_commits_on_files = len(all_shas)
            
        except Exception as e:
            logger.warning(f"Failed to count commits on files: {e}")
            
        return num_commits_on_files
    
    def _empty_result(self) -> Dict[str, Any]:
        return {
            "gh_team_size": None,
            "gh_by_core_team_member": None,
            "gh_num_commits_on_files_touched": None,
        }

