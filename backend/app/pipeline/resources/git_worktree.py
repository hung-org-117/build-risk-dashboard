"""
Git Worktree Resource Provider.

Provides access to filesystem operations on a specific commit:
- SLOC analysis
- File inspection
- Test metrics
- Code metrics

Requires GIT_HISTORY to be initialized first.
Creates a lightweight worktree for snapshot analysis.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.pipeline.resources import ResourceProvider, ResourceNames
from app.pipeline.core.context import ExecutionContext

logger = logging.getLogger(__name__)

WORKTREES_BASE = Path("../repo-data/worktrees")
WORKTREES_BASE.mkdir(parents=True, exist_ok=True)


@dataclass
class GitWorktreeHandle:
    """Handle to a git worktree for filesystem operations."""

    worktree_path: Optional[Path]
    effective_sha: Optional[str]

    @property
    def exists(self) -> bool:
        return self.worktree_path is not None and self.worktree_path.exists()

    @property
    def is_ready(self) -> bool:
        return (
            self.worktree_path is not None
            and self.exists
            and (self.worktree_path / ".git").exists()
        )


class GitWorktreeProvider(ResourceProvider):
    """
    Provides a git worktree for filesystem snapshot analysis.

    Depends on: GIT_HISTORY (must be initialized first)

    Handles:
    - Creating worktree at specific commit
    - Reusing existing worktrees
    - Cleanup on errors
    """

    @property
    def name(self) -> str:
        return ResourceNames.GIT_WORKTREE

    def initialize(self, context: ExecutionContext) -> GitWorktreeHandle:
        # Get the git history resource first
        from app.pipeline.resources.git_history import GitHistoryHandle

        git_history: GitHistoryHandle = context.get_resource(ResourceNames.GIT_HISTORY)

        if not git_history.is_commit_available:
            logger.warning("Commit not available, skipping worktree creation")
            return GitWorktreeHandle(worktree_path=None, effective_sha=None)

        repo_path = git_history.path
        commit_sha = git_history.effective_sha

        if commit_sha is None:
            logger.warning("Commit SHA is None, skipping worktree creation")
            return GitWorktreeHandle(worktree_path=None, effective_sha=None)

        # Pre-fetch blobs before creating worktree
        self._prefetch_commit_blobs(repo_path, commit_sha)

        # Create shared worktree
        worktree_path = self._create_shared_worktree(repo_path, commit_sha)

        return GitWorktreeHandle(
            worktree_path=worktree_path,
            effective_sha=commit_sha,
        )

    def cleanup(self, context: ExecutionContext) -> None:
        """Cleanup worktree resources."""
        try:
            worktree = context.get_resource(ResourceNames.GIT_WORKTREE)
            if worktree and worktree.exists:
                logger.debug(f"Cleaning up worktree at {worktree.worktree_path}")
                # Worktrees are kept for reuse, not deleted
        except Exception as e:
            logger.warning(f"Error during worktree cleanup: {e}")

    def _prefetch_commit_blobs(self, repo_path: Path, sha: str) -> None:
        """
        Pre-fetch blobs for a specific commit.

        For partial clones (--filter=blob:none), blobs are fetched lazily.
        This method pre-fetches the tree and blobs for a commit.
        """
        try:
            logger.debug(f"Pre-fetching blobs for commit {sha[:8]}...")

            subprocess.run(
                ["git", "rev-parse", "--verify", f"{sha}^{{tree}}"],
                cwd=str(repo_path),
                capture_output=True,
                check=True,
                timeout=60,
            )

            result = subprocess.run(
                [
                    "git",
                    "-c",
                    "fetch.negotiationAlgorithm=noop",
                    "fetch",
                    "origin",
                    sha,
                    "--no-tags",
                    "--depth=1",
                ],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                logger.debug(f"Pre-fetched blobs for commit {sha[:8]}")
            else:
                logger.debug(f"Blob pre-fetch returned non-zero: {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.warning("Blob pre-fetch timed out, will lazy fetch")
        except Exception as e:
            logger.debug(f"Blob pre-fetch failed: {e}")

    def _create_shared_worktree(
        self, repo_path: Path, commit_sha: str
    ) -> Optional[Path]:
        """Create a shared worktree at the commit."""
        if not commit_sha:
            return None

        worktree_base = (repo_path.parent.parent / "worktrees" / repo_path.name).resolve()
        worktree_base.mkdir(parents=True, exist_ok=True)
        worktree_path = worktree_base / commit_sha

        try:
            # If worktree already exists and is valid, reuse it
            git_marker = worktree_path / ".git"
            if worktree_path.exists() and git_marker.exists():
                logger.info(
                    f"Reusing existing worktree at {worktree_path} for commit {commit_sha[:8]}"
                )
                return worktree_path

            # Remove existing worktree from git's tracking
            subprocess.run(
                ["git", "worktree", "remove", str(worktree_path), "--force"],
                cwd=str(repo_path),
                capture_output=True,
                check=False,
                timeout=30,
            )

            # Also remove directory if it exists but has no .git marker
            if worktree_path.exists():
                import shutil

                logger.info(f"Cleaning up incomplete worktree at {worktree_path}")
                shutil.rmtree(worktree_path, ignore_errors=True)

            # Prune any remaining stale references
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=str(repo_path),
                capture_output=True,
                check=False,
                timeout=30,
            )

            # Create new worktree at the commit
            result = subprocess.run(
                ["git", "worktree", "add", "--detach", str(worktree_path), commit_sha],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=180,
            )

            if result.returncode != 0:
                logger.error(f"Failed to create shared worktree: {result.stderr}")
                return None

            logger.info(
                f"Created shared worktree at {worktree_path} for commit {commit_sha[:8]}"
            )
            return worktree_path

        except Exception as e:
            logger.error(f"Error creating shared worktree: {e}")
            return None
