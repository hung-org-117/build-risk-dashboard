"""
Training Ingestion - Re-ingestion Tasks.

Contains:
- reingest_failed_builds: Retry FAILED ingestion builds
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List

from bson import ObjectId
from celery import chord, group

from app.celery_app import celery_app
from app.entities.training_ingestion_build import IngestionStatus
from app.entities.training_scenario import ScenarioStatus
from app.repositories.raw_repository import RawRepositoryRepository
from app.repositories.training_ingestion_build import TrainingIngestionBuildRepository
from app.repositories.training_scenario import TrainingScenarioRepository
from app.tasks.base import SafeTask, TaskState
from app.tasks.shared.events import publish_scenario_updated
from app.tasks.training.ingestion.common import create_scenario_failure_handler

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.training_ingestion.reingest_failed_builds",
    queue="scenario_ingestion",
    soft_time_limit=300,
    time_limit=360,
)
def reingest_failed_builds(
    self: SafeTask,
    scenario_id: str,
) -> Dict[str, Any]:
    """
    Re-ingest only FAILED ingestion builds for a scenario.

    Only retries builds with status=FAILED (actual errors like timeout, network failure).
    Does NOT retry MISSING_RESOURCE builds (expected - logs expired, commit not found).

    This function:
    1. Resets FAILED builds to PENDING
    2. Builds ingestion chains directly from those PENDING builds
    3. Dispatches the ingestion workflow (without re-creating TrainingIngestionBuild records)
    """
    # Import here to avoid circular imports
    from app.tasks.training.ingestion.aggregate import aggregate_scenario_ingestion

    def mark_failed(e: Exception):
        handler = create_scenario_failure_handler(self.redis, scenario_id, self.db)
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        from app.tasks.pipeline.resource_dag import get_ingestion_tasks_by_level
        from app.tasks.shared import (
            TrainingPipelineContext,
            build_workflow_with_context,
        )

        correlation_id = str(uuid.uuid4())
        corr_prefix = f"[corr={correlation_id[:8]}]"

        scenario_repo = TrainingScenarioRepository(self.db)
        ingestion_build_repo = TrainingIngestionBuildRepository(self.db)
        raw_repo_repo = RawRepositoryRepository(self.db)

        # Validate scenario exists
        scenario = scenario_repo.find_by_id(scenario_id)
        if not scenario:
            return {"status": "error", "message": "Scenario not found"}

        # Find FAILED builds (not MISSING_RESOURCE)
        failed_count = ingestion_build_repo.collection.count_documents(
            {
                "scenario_id": ObjectId(scenario_id),
                "status": IngestionStatus.FAILED.value,
            }
        )

        missing_count = ingestion_build_repo.collection.count_documents(
            {
                "scenario_id": ObjectId(scenario_id),
                "status": IngestionStatus.MISSING_RESOURCE.value,
            }
        )

        if failed_count == 0:
            msg = "No failed builds to retry"
            if missing_count > 0:
                msg += f" ({missing_count} builds have missing resources - not retryable)"
            return {
                "status": "no_failed_builds",
                "failed_count": 0,
                "missing_resource_count": missing_count,
                "message": msg,
            }

        # Reset FAILED builds to PENDING
        reset_result = ingestion_build_repo.collection.update_many(
            {
                "scenario_id": ObjectId(scenario_id),
                "status": IngestionStatus.FAILED.value,
            },
            {
                "$set": {
                    "status": IngestionStatus.PENDING.value,
                    "ingestion_error": None,
                    "ingested_at": None,
                    "resource_status": {},
                }
            },
        )

        if reset_result.modified_count == 0:
            return {"status": "error", "message": "Failed to reset any builds"}

        logger.info(f"{corr_prefix} Reset {reset_result.modified_count} failed builds to PENDING")

        # Update scenario status to INGESTING
        scenario_repo.update_one(
            scenario_id,
            {
                "status": ScenarioStatus.INGESTING.value,
                "ingestion_started_at": datetime.utcnow(),
                "error_message": None,
            },
        )

        # Query the PENDING builds we just reset
        pending_builds = list(
            ingestion_build_repo.collection.find(
                {
                    "scenario_id": ObjectId(scenario_id),
                    "status": IngestionStatus.PENDING.value,
                }
            )
        )

        if not pending_builds:
            logger.warning(f"{corr_prefix} No PENDING builds found after reset")
            return {"status": "error", "message": "No PENDING builds found after reset"}

        # Group pending builds by repo
        builds_by_repo: Dict[str, List[Dict[str, Any]]] = {}
        for build_doc in pending_builds:
            repo_id = str(build_doc["raw_repo_id"])
            build_info = {
                "ingestion_build_id": str(build_doc["_id"]),
                "ci_run_id": build_doc.get("ci_run_id", ""),
                "commit_sha": build_doc.get("commit_sha", ""),
            }
            if repo_id not in builds_by_repo:
                builds_by_repo[repo_id] = []
            builds_by_repo[repo_id].append(build_info)

        # Build ingestion chains (same logic as start_scenario_ingestion)
        required_resources = ["git_history", "git_worktree", "build_logs"]
        tasks_by_level = get_ingestion_tasks_by_level(required_resources)

        ingestion_chains = []
        for raw_repo_id, repo_builds in builds_by_repo.items():
            raw_repo = raw_repo_repo.find_by_id(raw_repo_id)
            if not raw_repo:
                logger.warning(f"{corr_prefix} Repo {raw_repo_id} not found, skipping")
                continue

            build_ids = [b["ci_run_id"] for b in repo_builds if b.get("ci_run_id")]
            commit_shas = list({b["commit_sha"] for b in repo_builds if b.get("commit_sha")})

            if not build_ids:
                continue

            ctx = TrainingPipelineContext(
                scenario_id=scenario_id,
                correlation_id=correlation_id,
                _raw_repo_id=raw_repo_id,
                _github_repo_id=raw_repo.github_repo_id,
                _full_name=raw_repo.full_name,
            )

            repo_chain = build_workflow_with_context(
                tasks_by_level=tasks_by_level,
                ctx=ctx,
                raw_repo_id=raw_repo_id,
                github_repo_id=raw_repo.github_repo_id,
                full_name=raw_repo.full_name,
                build_ids=build_ids,
                commit_shas=commit_shas,
                ci_provider="github_actions",
            )

            if repo_chain:
                ingestion_chains.append(repo_chain)

        if not ingestion_chains:
            logger.warning(f"{corr_prefix} No ingestion chains created")
            scenario_repo.update_one(
                scenario_id,
                {"status": ScenarioStatus.INGESTED.value},
            )
            return {"status": "completed", "message": "No ingestion work needed"}

        # Dispatch chord: group of ingestion chains -> aggregate callback
        workflow = chord(
            group(*ingestion_chains),
            aggregate_scenario_ingestion.s(
                scenario_id=scenario_id,
                correlation_id=correlation_id,
            ),
        )
        workflow.apply_async()

        logger.info(
            f"{corr_prefix} Dispatched re-ingestion for {len(pending_builds)} builds "
            f"across {len(ingestion_chains)} repos"
        )

        # Publish scenario update - frontend will refetch builds
        scenario = scenario_repo.find_by_id(scenario_id)
        if scenario:
            publish_scenario_updated(scenario)

        return {
            "status": "queued",
            "builds_reset": reset_result.modified_count,
            "total_failed": failed_count,
            "repos_to_process": len(ingestion_chains),
            "correlation_id": correlation_id,
        }

    return self.run_safe(
        job_id=scenario_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )
