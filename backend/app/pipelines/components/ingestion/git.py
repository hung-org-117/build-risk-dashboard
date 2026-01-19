import logging
import subprocess
from pathlib import Path
from typing import List

from app.core.redis import RedisLock
from app.paths import get_repo_path, get_worktrees_path
from app.pipelines.core.base import PipelineContext, PipelineStep

logger = logging.getLogger(__name__)


class GitIngestionStep(PipelineStep):
    """
    Step to clone/update git repository and create worktrees.
    """

    def __init__(self, raw_repo_id: str, github_repo_id: int, full_name: str):
        self.raw_repo_id = raw_repo_id
        self.github_repo_id = github_repo_id
        self.full_name = full_name

    def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Clones valid repo and optionally creates worktrees.
        """
        # 1. Clone/Update Repo
        repo_path = self._ensure_repo_cloned(context)
        context.resources["git_path"] = repo_path

        # 2. Create Worktrees if needed
        # Check context config to see if worktrees are required and for which commits
        commits = context.config.get("commit_shas", [])
        if commits:
            self._create_worktrees(repo_path, commits, context)

        return context

    def _ensure_repo_cloned(self, context: PipelineContext) -> Path:
        repo_path = get_repo_path(self.github_repo_id)

        # Use Redis lock to prevent concurrent clones of same repo
        # We need access to redis, which should be available via global get_redis_client or similar
        # For now, assuming standard redis connection availability
        # Or better, inject redis client via context but context is generic.
        # Let's use the pattern from existing tasks: app.core.redis.RedisLock with app.celery_app.redis or similar?
        # SafeTask constructs redis.PipelineTask constructs redis.
        # We should probably pass services/clients in context or use singletons.

        # For this refactor, let's assume we can get redis.
        import redis

        from app.config import settings

        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

        with RedisLock(f"clone:{self.github_repo_id}", redis_client=redis_client):
            # Reuse logic from ingestion_tasks.clone_repo
            self._execute_git_clone_or_fetch(repo_path)

        return repo_path

    def _execute_git_clone_or_fetch(self, repo_path: Path):
        # ... logic ported from ingestion_tasks.py ...
        from app.config import settings
        from app.services.model_repository_service import is_org_repo

        use_installation_token = is_org_repo(self.full_name) and settings.GITHUB_INSTALLATION_ID

        if repo_path.exists():
            logger.info(f"Updating existing clone at {repo_path}")
            if use_installation_token:
                from app.services.github.github_app import get_installation_token

                token = get_installation_token()
                auth_url = f"https://x-access-token:{token}@github.com/{self.full_name}.git"
                subprocess.run(
                    ["git", "remote", "set-url", "origin", auth_url],
                    cwd=str(repo_path),
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
            subprocess.run(
                ["git", "fetch", "--all", "--prune"],
                cwd=str(repo_path),
                check=True,
                capture_output=True,
                timeout=300,
            )
        else:
            logger.info(f"Cloning to {repo_path}")
            clone_url = f"https://github.com/{self.full_name}.git"
            if use_installation_token:
                from app.services.github.github_app import get_installation_token

                token = get_installation_token()
                clone_url = f"https://x-access-token:{token}@github.com/{self.full_name}.git"

            subprocess.run(
                ["git", "clone", "--bare", clone_url, str(repo_path)],
                check=True,
                capture_output=True,
                timeout=600,
            )

    def _create_worktrees(self, repo_path: Path, commits: List[str], context: PipelineContext):
        worktrees_dir = get_worktrees_path(self.github_repo_id)
        worktrees_dir.mkdir(parents=True, exist_ok=True)

        # ... logic for worktrees ...
        for sha in commits:
            worktree_path = worktrees_dir / sha[:12]
            if not worktree_path.exists():
                try:
                    subprocess.run(
                        ["git", "worktree", "add", "--detach", str(worktree_path), sha],
                        cwd=str(repo_path),
                        check=True,
                        capture_output=True,
                        timeout=60,
                    )
                except Exception as e:
                    logger.warning(f"Failed to create worktree for {sha}: {e}")
                    # In a real pipeline, we might want to record this failure in context.errors
                    context.errors.append({"step": "GitIngestion", "item": sha, "error": str(e)})

        context.resources["worktrees_dir"] = worktrees_dir
