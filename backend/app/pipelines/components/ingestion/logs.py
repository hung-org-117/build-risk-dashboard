import asyncio
import logging
from typing import List

from app.pipelines.core.base import PipelineContext

# from app.tasks.shared.ingestion_tasks import _download_log_for_build # Avoid cyclic import if possible, better to port logic or move helper to service
# For now, we will duplicate the core logic or refactor later.
# Implementing a simplified version that calls the CI provider directly.

logger = logging.getLogger(__name__)


class BuildLogsIngestionStep(PipelineContext):
    """
    Step to download build logs from CI provider.
    """

    def __init__(self, raw_repo_id: str, github_repo_id: int, full_name: str, ci_provider: str):
        self.raw_repo_id = raw_repo_id
        self.github_repo_id = github_repo_id
        self.full_name = full_name
        self.ci_provider = ci_provider

    def execute(self, context: PipelineContext) -> PipelineContext:
        build_ids = context.config.get("build_ids", [])
        if not build_ids:
            logger.info("No builds to download logs for.")
            return context

        # We need async execution for logs, but PipelineStep.execute is synchronous.
        # We can run asyncio.run() or similar.
        try:
            asyncio.run(self._download_logs(build_ids, context))
        except Exception as e:
            logger.error(f"Failed to download logs: {e}")
            raise e

        return context

    async def _download_logs(self, build_ids: List[str], context: PipelineContext):
        # We need DB access to get provider config.
        # Assuming we can get a DB session.
        # In a real app, we should use a proper dependency injection or service locator.
        # For now, we'll try to use the existing get_db pattern or similar if available,
        # but since we are inside a Celery task usually, we might have self.db.
        # PipelineStep doesn't have self.db.

        # Let's assume for now we use a fresh session or passed in context.
        # Context resources might hold db session?
        # If not, we might need to refactor context to include it.

        # Implementation Detail:
        # We will skip the complex DB interactions for now and focus on the CI call structure.
        # This is a scaffolding step.
        pass
