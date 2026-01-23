"""
Model Ingestion Dispatch Tasks.

Tasks for dispatching and aggregating ingestion workflow:
- dispatch_ingestion: Build and dispatch ingestion workflow
- aggregate_model_ingestion_results: Chord callback after ingestion
- handle_ingestion_chord_error: Error handler for ingestion chord
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from bson import ObjectId
from celery import chord

from app.celery_app import celery_app
from app.entities.model_import_build import ModelImportBuildStatus
from app.entities.model_repo_config import ModelImportStatus
from app.repositories.model_import_build import ModelImportBuildRepository
from app.repositories.model_repo_config import ModelRepoConfigRepository
from app.tasks.base import PipelineTask, SafeTask, TaskState
from app.tasks.model.ingestion.common import create_repo_config_failure_handler
from app.tasks.model_processing import publish_status
from app.tasks.pipeline.resource_dag import get_ingestion_tasks_by_level
from app.tasks.shared import ModelPipelineContext, build_workflow_with_context
from app.tasks.shared.events import (
    publish_ingestion_progress,
    publish_model_repo_updated,
)

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="model.ingestion.dispatch",
    queue="model_ingestion",
    soft_time_limit=120,
    time_limit=180,
)
def dispatch_ingestion_batch(
    self: SafeTask,
    repo_config_id: str,
    raw_repo_id: str,
    github_repo_id: int,
    full_name: str,
    ci_provider: str,
    commit_shas: List[str],
    ci_run_ids: List[str],
    correlation_id: str = "",
) -> Dict[str, Any]:
    """Build and dispatch ingestion workflow."""

    def mark_failed(e: Exception):
        handler = create_repo_config_failure_handler(
            self.redis, repo_config_id, self.db
        )
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
        log_ctx = f"{corr_prefix}[dispatch_ingestion]"

        import_build_repo = ModelImportBuildRepository(self.db)
        import_build_repo.update_many_by_status(
            repo_config_id,
            from_status=ModelImportBuildStatus.FETCHED.value,
            updates={
                "status": ModelImportBuildStatus.INGESTING.value,
                "ingestion_started_at": datetime.utcnow(),
            },
        )

        # Update repo status to INGESTING so UI reflects progress
        repo_config_repo = ModelRepoConfigRepository(self.db)
        repo_config_repo.update_repository(
            repo_config_id,
            {"status": ModelImportStatus.INGESTING.value},
        )

        required_resources = ["git_history", "git_worktree", "build_logs"]
        tasks_by_level = get_ingestion_tasks_by_level(required_resources)

        import_build_repo.init_resource_status(repo_config_id, list(required_resources))

        from app.entities.model_import_build import ResourceStatus
        from app.tasks.pipeline.shared.resources import get_ingestion_only_resources

        ingestion_resources = get_ingestion_only_resources(set(required_resources))

        total_builds = len(commit_shas)
        for resource in ingestion_resources:
            import_build_repo.update_resource_status_batch(
                repo_config_id,
                resource,
                ResourceStatus.IN_PROGRESS,
            )

            publish_ingestion_progress(
                repo_id=repo_config_id,
                resource=resource,
                status="in_progress",
                builds_affected=total_builds,
                pipeline_type="model",
            )

        logger.info(
            f"{log_ctx} Resources={sorted(required_resources)}, tasks={tasks_by_level}"
        )

        ctx = ModelPipelineContext(
            repo_config_id=repo_config_id,
            correlation_id=correlation_id,
            _raw_repo_id=raw_repo_id,
            _github_repo_id=github_repo_id,
            _full_name=full_name,
        )

        ingestion_workflow = build_workflow_with_context(
            tasks_by_level=tasks_by_level,
            ctx=ctx,
            raw_repo_id=raw_repo_id,
            github_repo_id=github_repo_id,
            full_name=full_name,
            build_ids=ci_run_ids,
            commit_shas=commit_shas,
            ci_provider=ci_provider,
        )

        callback = handle_ingestion_completion.s(
            repo_config_id=repo_config_id,
            correlation_id=correlation_id,
        )

        if ingestion_workflow:
            logger.info(f"{log_ctx} Dispatching ingestion chord")
            error_callback = handle_ingestion_chord_error.s(
                repo_config_id=repo_config_id,
                correlation_id=correlation_id,
            )
            chord(ingestion_workflow, callback.on_error(error_callback)).apply_async()
        else:
            logger.info(f"{log_ctx} No ingestion needed, marking as complete")
            handle_ingestion_completion.delay(
                results=[],
                repo_config_id=repo_config_id,
                correlation_id=correlation_id,
            )

        return {"status": "dispatched", "resources": list(required_resources)}

    return self.run_safe(
        job_id=repo_config_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="model.ingestion.complete",
    queue="model_ingestion",
    soft_time_limit=30,
    time_limit=60,
)
def handle_ingestion_completion(
    self: SafeTask,
    results: Any,
    repo_config_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """Chord callback after ingestion workflow completes."""

    def mark_failed(e: Exception):
        handler = create_repo_config_failure_handler(
            self.redis, repo_config_id, self.db
        )
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

        import_build_repo = ModelImportBuildRepository(self.db)
        repo_config_repo = ModelRepoConfigRepository(self.db)

        now = datetime.utcnow()

        # Check if git_history failed (affects ALL builds)
        git_history_failed = import_build_repo.collection.count_documents(
            {
                "model_repo_config_id": ObjectId(repo_config_id),
                "status": ModelImportBuildStatus.INGESTING.value,
                "resource_status.git_history.status": "failed",
            }
        )

        if git_history_failed > 0:
            import_build_repo.update_many_by_status(
                repo_config_id,
                from_status=ModelImportBuildStatus.INGESTING.value,
                updates={
                    "status": ModelImportBuildStatus.FAILED.value,
                    "ingestion_error": "Clone failed",
                    "ingested_at": now,
                },
            )
        else:
            # Mark builds with failed git_worktree as FAILED
            import_build_repo.collection.update_many(
                {
                    "model_repo_config_id": ObjectId(repo_config_id),
                    "status": ModelImportBuildStatus.INGESTING.value,
                    "resource_status.git_worktree.status": "failed",
                },
                {
                    "$set": {
                        "status": ModelImportBuildStatus.FAILED.value,
                        "ingestion_error": "Worktree creation failed",
                        "ingested_at": now,
                    }
                },
            )

            # Mark builds with failed build_logs as MISSING_RESOURCE
            import_build_repo.collection.update_many(
                {
                    "model_repo_config_id": ObjectId(repo_config_id),
                    "status": ModelImportBuildStatus.INGESTING.value,
                    "resource_status.build_logs.status": "failed",
                },
                {
                    "$set": {
                        "status": ModelImportBuildStatus.MISSING_RESOURCE.value,
                        "ingestion_error": "Log download failed or expired",
                        "ingested_at": now,
                    }
                },
            )

            # Mark remaining INGESTING builds as INGESTED
            import_build_repo.update_many_by_status(
                repo_config_id,
                from_status=ModelImportBuildStatus.INGESTING.value,
                updates={
                    "status": ModelImportBuildStatus.INGESTED.value,
                    "ingested_at": now,
                },
            )

        status_counts = import_build_repo.count_by_status(repo_config_id)
        ingested = status_counts.get(ModelImportBuildStatus.INGESTED.value, 0)
        missing_resource = status_counts.get(
            ModelImportBuildStatus.MISSING_RESOURCE.value, 0
        )
        failed = status_counts.get(ModelImportBuildStatus.FAILED.value, 0)

        final_status = ModelImportStatus.INGESTED
        if failed > 0 or missing_resource > 0:
            parts = [f"{ingested} ready"]
            if failed > 0:
                parts.append(f"{failed} failed (retryable)")
            if missing_resource > 0:
                parts.append(f"{missing_resource} missing resources")
            msg = f"Ingestion done: {', '.join(parts)}. Review or start processing."
        else:
            msg = f"Ingestion complete: {ingested} builds ready. Start processing when ready."

        total_builds = ingested + missing_resource + failed
        repo_config_repo.update_repository(
            repo_config_id,
            {
                "status": final_status.value,
                "last_synced_at": now,
                "builds_fetched": total_builds,
                "builds_ingested": ingested,
                "builds_missing_resource": missing_resource,
                "builds_ingestion_failed": failed,
            },
        )

        logger.info(f"{corr_prefix}[aggregate_ingestion] {msg}")

        resource_summary = import_build_repo.get_resource_status_summary(repo_config_id)

        publish_model_repo_updated(
            repo_config_id,
            final_status.value,
            msg,
            stats={
                "builds_fetched": total_builds,
                "builds_ingested": ingested,
                "builds_missing_resource": missing_resource,
                "builds_ingestion_failed": failed,
            },
        )

        return {
            "status": "completed",
            "final_status": final_status.value,
            "builds_ingested": ingested,
            "builds_missing_resource": missing_resource,
            "builds_ingestion_failed": failed,
            "resource_status": resource_summary,
        }

    return self.run_safe(
        job_id=repo_config_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.model_ingestion.handle_ingestion_chord_error",
    queue="model_ingestion",
    soft_time_limit=60,
    time_limit=120,
)
def handle_ingestion_chord_error(
    self: PipelineTask,
    request,
    exc,
    traceback,
    repo_config_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """Error callback for ingestion chord failure."""
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
    error_msg = str(exc) if exc else "Unknown ingestion error"

    logger.error(
        f"{corr_prefix} Ingestion chord failed for {repo_config_id}: {error_msg}"
    )

    import_build_repo = ModelImportBuildRepository(self.db)
    repo_config_repo = ModelRepoConfigRepository(self.db)

    now = datetime.utcnow()

    failed_count = import_build_repo.update_many_by_status(
        repo_config_id,
        from_status=ModelImportBuildStatus.INGESTING.value,
        updates={
            "status": ModelImportBuildStatus.FAILED.value,
            "ingestion_error": f"Ingestion chord failed: {error_msg}",
            "ingested_at": now,
        },
    )

    logger.warning(f"{corr_prefix} Marked {failed_count} builds as FAILED (retryable)")

    ingested_builds = import_build_repo.find_by_repo_config(
        repo_config_id, status=ModelImportBuildStatus.INGESTED
    )

    if ingested_builds:
        logger.info(
            f"{corr_prefix} {len(ingested_builds)} builds were INGESTED before failure."
        )
        repo_config_repo.update_repository(
            repo_config_id,
            {
                "status": ModelImportStatus.INGESTED.value,
                "error_message": f"Ingestion partially failed: {error_msg}",
                "builds_ingestion_failed": failed_count,
            },
        )
        publish_status(
            repo_config_id,
            ModelImportStatus.INGESTED.value,
            f"Ingestion done: {len(ingested_builds)} ok, {failed_count} failed (retryable).",
            stats={
                "builds_ingested": len(ingested_builds),
                "builds_ingestion_failed": failed_count,
            },
        )
    else:
        repo_config_repo.update_repository(
            repo_config_id,
            {
                "status": ModelImportStatus.FAILED.value,
                "error_message": error_msg,
            },
        )
        publish_status(
            repo_config_id,
            "failed",
            f"Ingestion failed: {error_msg}. Use Retry Failed Ingestion to retry.",
        )

    return {
        "status": "handled",
        "failed_builds": failed_count,
        "ingested_builds": len(ingested_builds) if ingested_builds else 0,
        "error": error_msg,
    }
