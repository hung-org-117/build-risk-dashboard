"""
Training Ingestion - Orchestrator Tasks.

Contains:
- start_scenario_ingestion: Main entry point for ingestion
- filter_builds_for_scenario: Helper to filter builds
- process_ingestion_builds: Helper to create ingestion records
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List

from bson import ObjectId
from celery import chord, group

from app.celery_app import celery_app
from app.config import settings
from app.entities.training_ingestion_build import IngestionStatus
from app.entities.training_scenario import ScenarioStatus
from app.repositories.raw_build_run import RawBuildRunRepository
from app.repositories.raw_repository import RawRepositoryRepository
from app.repositories.training_ingestion_build import TrainingIngestionBuildRepository
from app.repositories.training_scenario import TrainingScenarioRepository
from app.tasks.base import SafeTask, TaskState
from app.tasks.shared.events import publish_scenario_updated
from app.tasks.training.ingestion.common import (
    create_scenario_failure_handler,
    find_matching_repos,
    resolve_filter_config,
)

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.training_ingestion.start_scenario_ingestion",
    queue="scenario_ingestion",
    soft_time_limit=120,
    time_limit=180,
)
def start_scenario_ingestion(
    self: SafeTask,
    scenario_id: str,
) -> Dict[str, Any]:
    """
    Orchestrator: Start training scenario ingestion phase.

    Flow:
        start_scenario_ingestion
            └── filter_scenario_builds
                └── chord(
                        group(ingestion_chain_1, ingestion_chain_2, ...),
                        aggregate_scenario_ingestion
                    )

    After ingestion completes, scenario is marked as INGESTED.
    User triggers processing (Phase 2) manually via start_scenario_processing.
    """
    # Import here to avoid circular imports
    from app.tasks.training.ingestion.aggregate import (
        aggregate_scenario_ingestion,
        handle_scenario_chord_error,
    )

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
        logger.info(
            f"[start_scenario_ingestion] Starting scenario {scenario_id}, corr={correlation_id[:8]}"
        )

        scenario_repo = TrainingScenarioRepository(self.db)
        raw_repo_repo = RawRepositoryRepository(self.db)

        # Load scenario
        scenario = scenario_repo.find_by_id(scenario_id)
        if not scenario:
            logger.error(f"Scenario {scenario_id} not found")
            return {"status": "error", "error": "Scenario not found"}

        # Step 1: Filter builds from RawRepository + RawBuildRun
        filter_result = filter_builds_for_scenario(
            db=self.db,
            scenario=scenario,
            scenario_id=scenario_id,
            correlation_id=correlation_id,
        )

        if filter_result["status"] == "error":
            scenario_repo.update_one(
                scenario_id,
                {
                    "status": ScenarioStatus.FAILED.value,
                    "error_message": filter_result["error"],
                },
            )
            return filter_result

        builds_total = filter_result["builds_total"]

        # Update status to INGESTING and publish
        scenario = scenario_repo.find_one_and_update(
            {"_id": ObjectId(scenario_id)},
            {
                "$set": {
                    "status": ScenarioStatus.INGESTING.value,
                    "filtering_started_at": datetime.utcnow(),
                    "ingestion_started_at": datetime.utcnow(),
                    "builds_total": builds_total,
                    "current_task_id": self.request.id,
                    "error_message": None,
                }
            },
            return_updated=True,
        )

        # Publish SSE event for UI update
        if scenario:
            publish_scenario_updated(scenario)

        # Check if we have any work to do by querying the DB
        ingestion_build_repo = TrainingIngestionBuildRepository(self.db)

        if builds_total == 0:
            if builds_total > 0:
                ingestion_build_repo.collection.update_many(
                    {
                        "scenario_id": ObjectId(scenario_id),
                        "status": IngestionStatus.PENDING.value,
                    },
                    {
                        "$set": {
                            "status": IngestionStatus.INGESTED.value,
                            "ingested_at": datetime.utcnow(),
                        }
                    },
                )

            scenario = scenario_repo.find_one_and_update(
                {"_id": ObjectId(scenario_id)},
                {
                    "$set": {
                        "status": ScenarioStatus.INGESTED.value,
                        "builds_ingested": builds_total,
                        "ingestion_completed_at": datetime.utcnow(),
                    }
                },
                return_updated=True,
            )
            if scenario:
                publish_scenario_updated(scenario)
            return {
                "status": "completed",
                "message": "Ingestion complete. Start processing when ready.",
            }

        # Step 2: Build ingestion chains
        required_resources = ["git_history", "git_worktree", "build_logs"]
        tasks_by_level = get_ingestion_tasks_by_level(required_resources)

        ingestion_chains = []
        repo_metadata = []

        # New flow: Query DB for repos involved in this scenario
        ingestion_build_repo = TrainingIngestionBuildRepository(self.db)

        # Find distinct raw_repo_ids for this scenario
        distinct_repo_oids = ingestion_build_repo.collection.distinct(
            "raw_repo_id", {"scenario_id": ObjectId(scenario_id)}
        )

        # Convert to strings for consistent handling
        repos_to_process = [str(oid) for oid in distinct_repo_oids]

        logger.info(
            f"[start_scenario_ingestion] Found {len(repos_to_process)} repos with builds to ingest"
        )

        for raw_repo_id_str in repos_to_process:
            raw_repo = raw_repo_repo.find_by_id(raw_repo_id_str)
            if not raw_repo:
                logger.warning(
                    f"[start_scenario_ingestion] Repo {raw_repo_id_str} not found, skipping"
                )
                continue

            # Get build IDs and commit SHAs
            # Query from DB for this repo and scenario
            cursor = ingestion_build_repo.collection.find(
                {
                    "scenario_id": ObjectId(scenario_id),
                    "raw_repo_id": ObjectId(raw_repo_id_str),
                    "status": IngestionStatus.PENDING.value,
                },
                {"ci_run_id": 1, "commit_sha": 1},
            )

            build_ids = []
            commit_shas = set()
            for doc in cursor:
                if doc.get("ci_run_id"):
                    build_ids.append(doc["ci_run_id"])
                if doc.get("commit_sha"):
                    commit_shas.add(doc["commit_sha"])
            commit_shas = list(commit_shas)

            if not build_ids:
                continue

            # Create context for this repo
            ctx = TrainingPipelineContext(
                scenario_id=scenario_id,
                correlation_id=correlation_id,
                _raw_repo_id=str(raw_repo.id),
                _github_repo_id=raw_repo.github_repo_id,
                _full_name=raw_repo.full_name,
            )

            # Build ingestion chain for this repo
            repo_chain = build_workflow_with_context(
                tasks_by_level=tasks_by_level,
                ctx=ctx,
                raw_repo_id=str(raw_repo.id),
                github_repo_id=raw_repo.github_repo_id,
                full_name=raw_repo.full_name,
                build_ids=build_ids,
                commit_shas=commit_shas,
                ci_provider="github_actions",
            )

            if repo_chain:
                ingestion_chains.append(repo_chain)
                repo_metadata.append(
                    {
                        "raw_repo_id": str(raw_repo.id),
                        "full_name": raw_repo.full_name,
                        "builds": len(build_ids),
                        "commits": len(commit_shas),
                    }
                )

        if not ingestion_chains:
            # Mark all as INGESTED
            ingestion_build_repo.collection.update_many(
                {
                    "scenario_id": ObjectId(scenario_id),
                    "status": IngestionStatus.PENDING.value,
                },
                {
                    "$set": {
                        "status": IngestionStatus.INGESTED.value,
                        "ingested_at": datetime.utcnow(),
                    }
                },
            )

            scenario_repo.update_one(
                scenario_id,
                {
                    "status": ScenarioStatus.INGESTED.value,
                    "builds_ingested": builds_total,
                    "ingestion_completed_at": datetime.utcnow(),
                },
            )
            return {
                "status": "completed",
                "message": "Ingestion complete. Start processing when ready.",
            }

        # Step 3: Initialize resource status
        ingestion_build_repo = TrainingIngestionBuildRepository(self.db)
        ingestion_build_repo.collection.update_many(
            {
                "scenario_id": ObjectId(scenario_id),
                "status": IngestionStatus.PENDING.value,
            },
            {"$set": {"status": IngestionStatus.INGESTING.value}},
        )

        # Step 4: Dispatch chord
        callback = aggregate_scenario_ingestion.s(
            scenario_id=scenario_id,
            correlation_id=correlation_id,
        )

        error_callback = handle_scenario_chord_error.s(
            scenario_id=scenario_id,
            correlation_id=correlation_id,
        )

        callback_with_error = callback.on_error(error_callback)
        chord(group(ingestion_chains), callback_with_error).apply_async()

        logger.info(
            f"[start_scenario_ingestion] Dispatched {len(ingestion_chains)} ingestion chains"
        )

        return {
            "status": "dispatched",
            "builds_total": builds_total,
            "ingestion_chains": len(ingestion_chains),
            "repo_metadata": repo_metadata,
        }

    return self.run_safe(
        job_id=scenario_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )


def process_ingestion_builds(
    db, scenario_id: str, repos: List[Any], filters: Dict[str, Any], corr_prefix: str
) -> int:
    """Query builds and create ingestion records."""
    ingestion_build_repo = TrainingIngestionBuildRepository(db)
    raw_build_run_repo = RawBuildRunRepository(db)

    repo_ids = [str(r.id) for r in repos]
    repo_cache = {str(r.id): r for r in repos}

    # Use optimized repository method
    batch_size = settings.INGESTION_IMPORT_BUILDS_PER_CHUNK
    cursor = raw_build_run_repo.find_builds_for_ingestion(
        raw_repo_ids=[ObjectId(rid) for rid in repo_ids],
        build_source_ids=filters.get("build_source_ids"),
        date_start=filters.get("date_start"),
        date_end=filters.get("date_end"),
        conclusions=filters.get("conclusions"),
        ci_providers=filters.get("ci_providers"),
        batch_size=batch_size,
    )

    ingestion_builds_buffer = []
    total_inserted = 0
    required_resources = ["git_history", "git_worktree", "build_logs"]

    for build_doc in cursor:
        raw_repo_id = build_doc.get("raw_repo_id")
        repo = repo_cache.get(str(raw_repo_id))

        ingestion_build_dict = {
            "scenario_id": ObjectId(scenario_id),
            "raw_repo_id": raw_repo_id,
            "raw_build_run_id": build_doc.get("_id"),
            "ci_run_id": build_doc.get("ci_run_id") or "",
            "commit_sha": build_doc.get("commit_sha") or "",
            "repo_full_name": repo.full_name if repo else "",
            "github_repo_id": repo.github_repo_id if repo else None,
            "status": IngestionStatus.PENDING.value,
            "required_resources": required_resources,
            "resource_status": {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        ingestion_builds_buffer.append(ingestion_build_dict)

        if len(ingestion_builds_buffer) >= batch_size:
            ingestion_build_repo.collection.insert_many(ingestion_builds_buffer)
            total_inserted += len(ingestion_builds_buffer)
            ingestion_builds_buffer = []

    if ingestion_builds_buffer:
        ingestion_build_repo.collection.insert_many(ingestion_builds_buffer)
        total_inserted += len(ingestion_builds_buffer)

    return total_inserted


def filter_builds_for_scenario(
    db,
    scenario,
    scenario_id: str,
    correlation_id: str,
) -> Dict[str, Any]:
    """
    Filter and create IngestionBuild records from RawRepository + RawBuildRun.

    Returns dict with:
        - status: "completed" or "error"
        - builds_total: number of builds found
    """
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

    # 1. Resolve configuration
    filters = resolve_filter_config(scenario)

    # 2. Find matching repositories
    repos = find_matching_repos(db, filters["languages"], filters.get("build_source_ids"))

    if not repos:
        logger.warning(f"{corr_prefix} [filter] No repos match filter criteria")
        return {"status": "error", "error": "No repositories match filter criteria"}

    logger.info(f"{corr_prefix} [filter] Found {len(repos)} matching repos")

    # 3. Process builds
    total_inserted = process_ingestion_builds(db, scenario_id, repos, filters, corr_prefix)

    if total_inserted == 0:
        logger.warning(f"{corr_prefix} [filter] No builds match filter criteria")
        return {"status": "error", "error": "No builds match filter criteria"}

    logger.info(
        f"{corr_prefix} [filter] Found and created {total_inserted} ingestion build records"
    )

    return {
        "status": "completed",
        "builds_total": total_inserted,
    }
