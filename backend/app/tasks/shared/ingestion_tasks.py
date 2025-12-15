"""
Shared Ingestion Tasks - Generic tasks for both model and dataset pipelines.

These tasks are shared between model_ingestion.py and dataset_ingestion.py
to avoid code duplication. They work with any repository/build type.

Features:
- Clone/update git repositories (with installation token support)
- Create git worktrees (with fork commit replay support)
- Download build logs from CI providers
- Optional status publishing for UI updates
"""

import logging
import subprocess
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from celery import chain, group

from app.celery_app import celery_app
from app.config import settings
from app.tasks.base import PipelineTask
from app.repositories.raw_build_run import RawBuildRunRepository
from app.repositories.raw_repository import RawRepositoryRepository
from app.ci_providers import CIProvider, get_provider_config, get_ci_provider
from app.services.github.exceptions import GithubRateLimitError
from app.paths import REPOS_DIR, WORKTREES_DIR, LOGS_DIR

logger = logging.getLogger(__name__)


def _publish_status(repo_id: str, status: str, message: str = ""):
    """Publish status update to Redis for real-time UI updates."""
    try:
        import redis
        import json

        redis_client = redis.from_url(settings.REDIS_URL)
        redis_client.publish(
            "events",
            json.dumps(
                {
                    "type": "REPO_UPDATE",
                    "payload": {
                        "repo_id": repo_id,
                        "status": status,
                        "message": message,
                    },
                }
            ),
        )
    except Exception as e:
        logger.error(f"Failed to publish status update: {e}")


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.shared.clone_repo",
    queue="ingestion",
    autoretry_for=(subprocess.CalledProcessError,),
    retry_kwargs={"max_retries": 3, "countdown": 360},
)
def clone_repo(
    self: PipelineTask,
    prev_result: Any = None,  # Allow chaining from previous task
    repo_id: str = "",
    full_name: str = "",
    installation_id: Optional[str] = None,
    publish_status: bool = False,
) -> Dict[str, Any]:
    """
    Clone or update git repository.

    Works for both model and dataset pipelines.
    Supports installation token for private repos.
    """
    if publish_status and repo_id:
        _publish_status(repo_id, "importing", "Cloning repository...")

    repo_path = REPOS_DIR / repo_id

    try:
        if repo_path.exists():
            logger.info(f"Updating existing clone for {full_name}")
            subprocess.run(
                ["git", "fetch", "--all", "--prune"],
                cwd=str(repo_path),
                check=True,
                capture_output=True,
                timeout=300,
            )
        else:
            logger.info(f"Cloning {full_name} to {repo_path}")
            clone_url = f"https://github.com/{full_name}.git"

            # For private repos, use installation token
            if installation_id:
                from app.services.github.github_app import get_installation_token

                token = get_installation_token(installation_id, self.db)
                clone_url = f"https://x-access-token:{token}@github.com/{full_name}.git"

            subprocess.run(
                ["git", "clone", "--bare", clone_url, str(repo_path)],
                check=True,
                capture_output=True,
                timeout=600,
            )

        if publish_status and repo_id:
            _publish_status(repo_id, "importing", "Repository cloned successfully")

        result = {"repo_id": repo_id, "status": "cloned", "path": str(repo_path)}

        # Preserve previous result data for chaining
        if isinstance(prev_result, dict):
            return {**prev_result, **result}
        return result

    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed for {full_name}: {e.stderr}")
        raise


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.shared.create_worktrees_batch",
    queue="ingestion",
)
def create_worktrees_batch(
    self: PipelineTask,
    prev_result: Dict[str, Any] = None,
    repo_id: str = "",
    commit_shas: Optional[List[str]] = None,
    enable_fork_replay: bool = True,
    publish_status: bool = False,
) -> Dict[str, Any]:
    """
    Create git worktrees for multiple commits.

    If commit_shas is not provided, extracts from prev_result["build_ids"]
    by looking up RawBuildRun records.

    Args:
        prev_result: Result from previous task in chain
        repo_id: Repository ID
        commit_shas: Optional list of commit SHAs to create worktrees for
        enable_fork_replay: If True, attempt to replay fork commits that are missing
        publish_status: If True, publish status updates to Redis for UI
    """
    prev_result = prev_result or {}
    build_ids = prev_result.get("build_ids", [])

    if publish_status and repo_id and build_ids:
        _publish_status(
            repo_id, "importing", f"Creating worktrees for {len(build_ids)} builds..."
        )

    build_run_repo = RawBuildRunRepository(self.db)
    raw_repo_repo = RawRepositoryRepository(self.db)
    raw_repo = raw_repo_repo.find_by_id(repo_id)

    # Get commit SHAs from build_ids if not provided
    if not commit_shas and build_ids:
        commit_shas = []
        for build_id in build_ids:
            build_run = build_run_repo.find_by_repo_and_build_id(repo_id, str(build_id))
            if build_run and build_run.commit_sha:
                # Use effective_sha if available (for fork commits)
                sha = build_run.effective_sha or build_run.commit_sha
                commit_shas.append(sha)

    if not commit_shas:
        return {**prev_result, "worktrees_created": 0, "worktrees_skipped": 0}

    repo_path = REPOS_DIR / repo_id
    worktrees_dir = WORKTREES_DIR / repo_id
    worktrees_dir.mkdir(parents=True, exist_ok=True)

    if not repo_path.exists():
        return {**prev_result, "worktrees_created": 0, "error": "Repo not cloned"}

    # Get GitHub client for fork commit replay if enabled
    github_client = None
    if enable_fork_replay:
        try:
            from app.services.github.github_client import get_public_github_client

            github_client = get_public_github_client()
        except Exception as e:
            logger.warning(f"Failed to get GitHub client for fork replay: {e}")

    # Prune stale worktrees first
    try:
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=str(repo_path),
            capture_output=True,
            check=False,
            timeout=60,
        )
    except Exception as e:
        logger.warning(f"Failed to prune worktrees: {e}")

    worktrees_created = 0
    worktrees_skipped = 0
    worktrees_failed = 0
    fork_commits_replayed = 0
    seen_shas = set()

    for i, sha in enumerate(commit_shas):
        if sha in seen_shas:
            worktrees_skipped += 1
            continue
        seen_shas.add(sha)

        # Get the build_run to check for effective_sha
        original_sha = sha
        build_run = None
        if build_ids and i < len(build_ids):
            build_run = build_run_repo.find_by_repo_and_build_id(
                repo_id, str(build_ids[i])
            )
            if build_run and build_run.effective_sha:
                sha = build_run.effective_sha

        worktree_path = worktrees_dir / sha[:12]
        if worktree_path.exists():
            worktrees_skipped += 1
            continue

        try:
            # Check if commit exists
            result = subprocess.run(
                ["git", "cat-file", "-e", sha],
                cwd=str(repo_path),
                capture_output=True,
                timeout=10,
            )

            if result.returncode != 0:
                # Commit not available - attempt fork replay if enabled
                if enable_fork_replay and github_client and raw_repo and build_run:
                    try:
                        from app.services.commit_replay import ensure_commit_exists

                        synthetic_sha = ensure_commit_exists(
                            repo_path=repo_path,
                            commit_sha=original_sha,
                            repo_slug=raw_repo.full_name,
                            github_client=github_client,
                        )
                        if synthetic_sha:
                            # Save effective_sha to DB
                            build_run_repo.update_effective_sha(
                                build_run.id, synthetic_sha
                            )
                            sha = synthetic_sha
                            fork_commits_replayed += 1
                            logger.info(
                                f"Replayed fork commit {original_sha[:8]} -> {synthetic_sha[:8]}"
                            )
                        else:
                            worktrees_skipped += 1
                            continue
                    except Exception as e:
                        logger.warning(
                            f"Failed to replay fork commit {original_sha[:8]}: {e}"
                        )
                        worktrees_skipped += 1
                        continue
                else:
                    worktrees_skipped += 1
                    continue

            # Create worktree
            worktree_path = worktrees_dir / sha[:12]
            subprocess.run(
                ["git", "worktree", "add", "--detach", str(worktree_path), sha],
                cwd=str(repo_path),
                check=True,
                capture_output=True,
                timeout=60,
            )
            worktrees_created += 1

        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to create worktree for {sha[:8]}: {e}")
            worktrees_failed += 1
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout creating worktree for {sha[:8]}")
            worktrees_failed += 1

        # Progress update every 50 builds
        if publish_status and repo_id and (i + 1) % 50 == 0:
            _publish_status(
                repo_id,
                "importing",
                f"Worktrees: {worktrees_created} created, {worktrees_skipped} skipped",
            )

    if publish_status and repo_id:
        _publish_status(
            repo_id,
            "importing",
            f"Worktrees: {worktrees_created} created, {fork_commits_replayed} replayed, {worktrees_failed} failed",
        )

    return {
        **prev_result,
        "worktrees_created": worktrees_created,
        "worktrees_skipped": worktrees_skipped,
        "worktrees_failed": worktrees_failed,
        "fork_commits_replayed": fork_commits_replayed,
    }


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.shared.download_build_logs",
    queue="ingestion",
    autoretry_for=(GithubRateLimitError,),
    retry_kwargs={"max_retries": 3},
)
def download_build_logs(
    self: PipelineTask,
    prev_result: Dict[str, Any] = None,
    repo_id: str = "",
    full_name: str = "",
    build_ids: Optional[List[str]] = None,
    ci_provider: str = CIProvider.GITHUB_ACTIONS.value,
    installation_id: Optional[str] = None,
    max_consecutive_expired: int = 10,
    publish_status: bool = False,
) -> Dict[str, Any]:
    """
    Download build job logs from CI provider.

    If build_ids is not provided, extracts from prev_result["build_ids"].
    Stops early if max_consecutive_expired builds have expired logs.
    """
    from app.services.github.exceptions import GithubLogsUnavailableError

    prev_result = prev_result or {}
    build_ids = build_ids or prev_result.get("build_ids", [])

    if not build_ids:
        return {**prev_result, "logs_downloaded": 0, "logs_expired": 0}

    if publish_status and repo_id:
        _publish_status(
            repo_id, "importing", f"Downloading logs for {len(build_ids)} builds..."
        )

    build_run_repo = RawBuildRunRepository(self.db)

    ci_provider_enum = CIProvider(ci_provider)
    provider_config = get_provider_config(ci_provider_enum)
    ci_instance = get_ci_provider(ci_provider_enum, provider_config, db=self.db)

    logs_downloaded = 0
    logs_expired = 0
    logs_skipped = 0
    max_log_size = settings.MAX_LOG_SIZE_MB * 1024 * 1024
    batch_size = getattr(settings, "DOWNLOAD_LOGS_BATCH_SIZE", 50)

    async def download_logs_for_build(build_id: str) -> str:
        nonlocal logs_downloaded, logs_expired, logs_skipped

        build_run = build_run_repo.find_by_repo_and_build_id(repo_id, build_id)
        if build_run and build_run.logs_available:
            logs_skipped += 1
            return "skipped"

        try:
            build_logs_dir = LOGS_DIR / repo_id / build_id
            build_logs_dir.mkdir(parents=True, exist_ok=True)

            composite_id = f"{full_name}:{build_id}"
            fetch_kwargs = {"build_id": composite_id}
            if ci_provider_enum == CIProvider.GITHUB_ACTIONS and installation_id:
                fetch_kwargs["installation_id"] = installation_id

            log_files = await ci_instance.fetch_build_logs(**fetch_kwargs)

            if not log_files:
                if build_run:
                    build_run_repo.update_one(
                        str(build_run.id),
                        {"logs_available": False, "logs_expired": True},
                    )
                logs_expired += 1
                return "expired"

            saved_files = []
            for log_file in log_files:
                if log_file.size_bytes > max_log_size:
                    continue

                log_path = build_logs_dir / f"{log_file.job_name}.log"
                log_path.write_text(log_file.content)
                saved_files.append(str(log_path))

            if saved_files:
                if build_run:
                    build_run_repo.update_one(
                        str(build_run.id),
                        {"logs_path": str(build_logs_dir), "logs_available": True},
                    )
                logs_downloaded += 1
                return "downloaded"
            else:
                logs_expired += 1
                return "expired"

        except GithubLogsUnavailableError:
            if build_run:
                build_run_repo.update_one(
                    str(build_run.id),
                    {"logs_available": False, "logs_expired": True},
                )
            logs_expired += 1
            return "expired"
        except Exception as e:
            logger.warning(f"Failed to download logs for build {build_id}: {e}")
            return "failed"

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        consecutive_expired = 0

        for i, build_id in enumerate(build_ids):
            result = loop.run_until_complete(download_logs_for_build(build_id))

            if result == "expired":
                consecutive_expired += 1
                if consecutive_expired >= max_consecutive_expired:
                    logger.info(
                        f"Stopping log download: {consecutive_expired} consecutive expired logs"
                    )
                    break
            else:
                consecutive_expired = 0

            # Progress update every batch_size builds
            if publish_status and repo_id and (i + 1) % batch_size == 0:
                _publish_status(
                    repo_id,
                    "importing",
                    f"Downloaded logs: {logs_downloaded}/{i+1} ({logs_expired} expired)",
                )
    finally:
        loop.close()

    if publish_status and repo_id:
        _publish_status(
            repo_id,
            "importing",
            f"Logs: {logs_downloaded} downloaded, {logs_expired} expired, {logs_skipped} skipped",
        )

    return {
        **prev_result,
        "logs_downloaded": logs_downloaded,
        "logs_expired": logs_expired,
        "logs_skipped": logs_skipped,
    }
