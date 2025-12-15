"""
Git Utilities using subprocess.

Provides git operations using subprocess commands for reliable behavior
across different repository configurations including submodules and complex histories.
"""

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)


def run_git(
    repo_path: Path,
    args: List[str],
    timeout: int = 60,
) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git"] + args,
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, ["git"] + args, result.stdout, result.stderr
        )
    return result.stdout.strip()


def get_commit_info(repo_path: Path, sha: str) -> Dict[str, Any]:
    """
    Get commit info using subprocess.

    Returns dict with: hexsha, parents (list of parent shas), committed_date
    """
    try:
        # Format: sha|parent1 parent2|timestamp
        output = run_git(
            repo_path,
            ["log", "-1", "--format=%H|%P|%ct", sha],
        )
        parts = output.split("|")
        if len(parts) >= 3:
            parents = parts[1].split() if parts[1] else []
            return {
                "hexsha": parts[0],
                "parents": parents,
                "committed_date": int(parts[2]) if parts[2] else 0,
            }
    except Exception as e:
        logger.warning(f"Failed to get commit info for {sha}: {e}")

    return {"hexsha": sha, "parents": [], "committed_date": 0}


def get_commit_parents(repo_path: Path, sha: str) -> List[str]:
    """Get parent commit SHAs using subprocess."""
    try:
        output = run_git(repo_path, ["log", "-1", "--format=%P", sha])
        return output.split() if output else []
    except Exception as e:
        logger.warning(f"Failed to get parents for {sha}: {e}")
        return []


def get_diff_files(repo_path: Path, sha1: str, sha2: str) -> List[Dict[str, str]]:
    """
    Get list of files changed between two commits using subprocess.

    Returns list of dicts with: a_path, b_path (old/new paths)
    """
    try:
        # --name-status: shows status (A/D/M/R) and file paths
        output = run_git(
            repo_path,
            ["diff-tree", "-r", "--name-status", "--no-commit-id", sha1, sha2],
        )

        files = []
        for line in output.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                status = parts[0][0]  # First char: A, D, M, R, C
                if status == "R" or status == "C":
                    # Rename/Copy: status\told_path\tnew_path
                    a_path = parts[1] if len(parts) > 1 else None
                    b_path = parts[2] if len(parts) > 2 else parts[1]
                elif status == "D":
                    # Delete: only old path
                    a_path = parts[1]
                    b_path = None
                elif status == "A":
                    # Add: only new path
                    a_path = None
                    b_path = parts[1]
                else:
                    # Modify: same path
                    a_path = parts[1]
                    b_path = parts[1]

                files.append({"a_path": a_path, "b_path": b_path})

        return files
    except Exception as e:
        logger.warning(f"Failed to get diff files between {sha1} and {sha2}: {e}")
        return []


def iter_commit_history(
    repo_path: Path,
    start_sha: str,
    max_count: int = 1000,
) -> Generator[Dict[str, Any], None, None]:
    """
    Iterate through commit history using subprocess.

    Yields dicts with: hexsha, parents (list)
    """
    try:
        # Format: sha|parent1 parent2
        output = run_git(
            repo_path,
            ["log", f"--max-count={max_count}", "--format=%H|%P", start_sha],
        )

        for line in output.splitlines():
            if not line.strip():
                continue
            parts = line.split("|")
            if parts:
                hexsha = parts[0]
                parents = parts[1].split() if len(parts) > 1 and parts[1] else []
                yield {"hexsha": hexsha, "parents": parents}
    except Exception as e:
        logger.warning(f"Failed to iterate commits from {start_sha}: {e}")
        return


def get_author_email(repo_path: Path, sha: str) -> Optional[str]:
    """Get author email for a commit."""
    try:
        return run_git(repo_path, ["log", "-1", "--format=%ae", sha])
    except Exception:
        return None


def get_committer_email(repo_path: Path, sha: str) -> Optional[str]:
    """Get committer email for a commit."""
    try:
        return run_git(repo_path, ["log", "-1", "--format=%ce", sha])
    except Exception:
        return None


def get_committed_date(repo_path: Path, sha: str) -> Optional[int]:
    """Get committed date (unix timestamp) for a commit."""
    try:
        ts = run_git(repo_path, ["log", "-1", "--format=%ct", sha])
        return int(ts) if ts else None
    except Exception:
        return None


def get_author_name(repo_path: Path, sha: str) -> Optional[str]:
    """Get author name for a commit."""
    try:
        return run_git(repo_path, ["log", "-1", "--format=%an", sha])
    except Exception:
        return None


def get_committer_name(repo_path: Path, sha: str) -> Optional[str]:
    """Get committer name for a commit."""
    try:
        return run_git(repo_path, ["log", "-1", "--format=%cn", sha])
    except Exception:
        return None


def git_log_files(
    repo_path: Path,
    sha: str,
    since_iso: str,
    file_paths: List[str],
    chunk_size: int = 50,
) -> set:
    """
    Get commit SHAs that touched the given files since a date.

    Args:
        repo_path: Path to the git repository
        sha: Starting commit SHA
        since_iso: ISO format date string for --since
        file_paths: List of file paths to check
        chunk_size: Process files in chunks to avoid arg limits

    Returns:
        Set of commit SHAs that modified the given files
    """
    all_shas: set = set()

    for i in range(0, len(file_paths), chunk_size):
        chunk = file_paths[i : i + chunk_size]
        try:
            output = run_git(
                repo_path,
                ["log", sha, "--since", since_iso, "--format=%H", "--"] + chunk,
            )
            if output:
                all_shas.update(output.splitlines())
        except Exception:
            continue

    return all_shas
