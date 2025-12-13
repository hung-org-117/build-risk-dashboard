"""
Git History Resource Provider.

Provides access to git commit history operations:
- Walking commit history
- Getting commit parents
- Blame information
- Does NOT include worktree (filesystem operations)

Uses subprocess-based git commands for reliable behavior.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.pipeline.resources import ResourceProvider, ResourceNames
from app.utils.locking import repo_lock
from app.services.commit_replay import ensure_commit_exists
from app.pipeline.core.context import ExecutionContext

logger = logging.getLogger(__name__)

REPOS_DIR = Path("../repo-data/repos")
REPOS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class GitHistoryHandle:
    """Handle to git repository for history operations only."""

    path: Path
    effective_sha: Optional[str]
    original_sha: str
    is_missing_commit: bool = False

    @property
    def is_commit_available(self) -> bool:
        return self.effective_sha is not None


class GitHistoryProvider(ResourceProvider):
    """
    Provides access to git history operations.

    Handles:
    - Cloning if needed
    - Fetching latest
    - Ensuring the target commit exists (handles fork PRs)
    - Commit history queries

    Does NOT create worktree (lighter weight).
    """

    @property
    def name(self) -> str:
        return ResourceNames.GIT_HISTORY

    def initialize(self, context: ExecutionContext) -> GitHistoryHandle:
        repo = context._init_repo
        workflow_run = context._init_workflow_run

        commit_sha = workflow_run.head_sha if workflow_run else None
        if not commit_sha:
            raise ValueError("No commit SHA available in workflow run")

        repo_path = REPOS_DIR / str(repo.id)

        with repo_lock(str(repo.id)):
            if not repo_path.exists():
                self._clone_repo(repo, repo_path)

            self._run_git(repo_path, ["fetch", "origin"])

            github_client = self._get_github_client(repo, context)

            effective_sha = ensure_commit_exists(
                repo_path=repo_path,
                commit_sha=commit_sha,
                repo_slug=repo.full_name,
                github_client=github_client,
            )

            is_missing_commit = effective_sha is None
            if is_missing_commit:
                logger.warning(
                    f"Commit {commit_sha} not found and could not be replayed "
                    f"(likely a fork commit that exceeded max traversal depth)"
                )

        return GitHistoryHandle(
            path=repo_path,
            effective_sha=effective_sha,
            original_sha=commit_sha,
            is_missing_commit=is_missing_commit,
        )

    def _clone_repo(self, repo, repo_path: Path, max_retries: int = 2) -> None:
        """Clone the repository using partial clone."""
        clone_url = f"https://github.com/{repo.full_name}.git"

        # For private repos, use token
        if repo.is_private and repo.installation_id:
            from app.services.github.github_app import get_installation_token

            token = get_installation_token(repo.installation_id)
            clone_url = (
                f"https://x-access-token:{token}@github.com/{repo.full_name}.git"
            )

        for attempt in range(max_retries + 1):
            try:
                logger.info(
                    f"Cloning {repo.full_name} to {repo_path} (attempt {attempt + 1})"
                )

                clone_cmd = [
                    "git",
                    "clone",
                    "--bare",
                    "--filter=blob:none",
                    clone_url,
                    str(repo_path),
                ]

                subprocess.run(
                    clone_cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )

                logger.info(f"Successfully cloned {repo.full_name}")
                return

            except subprocess.TimeoutExpired as e:
                logger.warning(
                    f"Clone attempt {attempt + 1} timed out for {repo.full_name}"
                )
                if repo_path.exists():
                    import shutil

                    shutil.rmtree(repo_path, ignore_errors=True)

                if attempt == max_retries:
                    raise RuntimeError(
                        f"Clone timed out after {max_retries + 1} attempts"
                    ) from e

            except subprocess.CalledProcessError as e:
                logger.error(
                    f"Clone failed for {repo.full_name}: {e.stderr or e.stdout}"
                )
                if repo_path.exists():
                    import shutil

                    shutil.rmtree(repo_path, ignore_errors=True)

                if attempt == max_retries:
                    raise

    def _run_git(self, cwd: Path, args: list, timeout: int = 120) -> str:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
        return result.stdout.strip()

    def _get_github_client(self, repo, context: ExecutionContext):
        from app.services.github.github_client import (
            get_app_github_client,
            get_public_github_client,
        )

        if repo.installation_id:
            logger.debug(f"Using App GitHub client for repo {repo.full_name}")
            return get_app_github_client(context._init_db, str(repo.installation_id))
        else:
            logger.debug(f"Using Public GitHub client for repo {repo.full_name}")
            return get_public_github_client()
