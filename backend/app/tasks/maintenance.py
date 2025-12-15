"""
Maintenance Tasks - Scheduled cleanup and housekeeping jobs.

These tasks are designed to run periodically via Celery Beat.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from celery import shared_task

from app.database.mongo import get_database
from app.repositories.pipeline_run import PipelineRunRepository

logger = logging.getLogger(__name__)


@shared_task(
    name="app.tasks.maintenance.cleanup_pipeline_runs",
    bind=True,
    queue="processing",
)
def cleanup_pipeline_runs(self, days: int = 30) -> Dict[str, Any]:
    """
    Clean up old pipeline runs to free up storage.

    This task is designed to run daily via Celery Beat.
    It deletes pipeline run records older than the specified number of days.

    Args:
        days: Number of days to keep. Runs older than this will be deleted.

    Returns:
        Dict with deleted count and timestamp.
    """
    db = get_database()
    repo = PipelineRunRepository(db)

    try:
        deleted_count = repo.cleanup_old_runs(days=days)

        logger.info(
            f"Pipeline runs cleanup completed: deleted {deleted_count} runs older than {days} days"
        )

        return {
            "status": "success",
            "deleted_count": deleted_count,
            "days_threshold": days,
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Pipeline runs cleanup failed: {e}", exc_info=True)
        return {
            "status": "failed",
            "error": str(e),
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }
