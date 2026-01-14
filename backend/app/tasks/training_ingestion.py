"""
Training Pipeline - Ingestion Tasks (Phase 1)

This module handles the ingestion phase of training scenario:
1. start_scenario_ingestion - Orchestrator: Filter + Ingest builds
2. filter_scenario_builds - Query RawRepository + RawBuildRun by config
3. aggregate_scenario_ingestion - Chord callback: aggregate ingestion results
4. handle_scenario_chord_error - Error handler for ingestion failures
5. reingest_failed_builds - Retry FAILED builds

After ingestion completes, scenario is marked as INGESTED.
User triggers Phase 2 (processing) manually via start_scenario_processing.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List

from bson import ObjectId
from celery import chord, group

from app.celery_app import celery_app
from app.entities.training_ingestion_build import IngestionStatus
from app.entities.training_scenario import ScenarioStatus, TrainingScenario
from app.repositories.raw_build_run import RawBuildRunRepository
from app.repositories.raw_repository import RawRepositoryRepository
from app.repositories.training_ingestion_build import TrainingIngestionBuildRepository
from app.repositories.training_scenario import TrainingScenarioRepository
from app.tasks.base import PipelineTask, SafeTask, TaskState
from app.tasks.shared.events import publish_scenario_update

logger = logging.getLogger(__name__)


def _create_scenario_failure_handler(scenario_id: str, db):
    """
    Create a failure handler for TrainingScenario tasks.
    Updates status to FAILED on unhandled errors.
    """

    def handler(status: str, error_message: str) -> None:
        try:
            scenario_repo = TrainingScenarioRepository(db)
            scenario_repo.update_one(
                scenario_id,
                {
                    "status": ScenarioStatus.FAILED.value,
                    "error_message": error_message,
                },
            )
            publish_scenario_update(
                scenario_id=scenario_id,
                status=ScenarioStatus.FAILED.value,
                error=error_message,
            )
        except Exception as e:
            logger.warning(f"Failed to update scenario {scenario_id}: {e}")

    return handler


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

    def mark_failed(e: Exception):
        handler = _create_scenario_failure_handler(scenario_id, self.db)
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
        filter_result = _filter_builds_for_scenario(
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

        # Update status to INGESTING
        scenario_repo.update_one(
            scenario_id,
            {
                "status": ScenarioStatus.INGESTING.value,
                "filtering_started_at": datetime.utcnow(),
                "ingestion_started_at": datetime.utcnow(),
                "builds_total": builds_total,
                "current_task_id": self.request.id,
                "error_message": None,
            },
        )

        # Publish SSE event for UI update
        publish_scenario_update(
            scenario_id=scenario_id,
            status=ScenarioStatus.INGESTING.value,
            builds_total=builds_total,
            current_phase="Ingesting build data (clone, worktree, logs)",
        )

        # Check if we have any work to do by querying the DB
        ingestion_build_repo = TrainingIngestionBuildRepository(self.db)

        # We need to know if there are any pending builds to ingest.
        # We can check total count or distinct repos.
        # Since we need repos later, let's get distinct repos now or just check count.
        # But filter returned builds_total, so we can trust that for "is there work?".

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

            scenario_repo.update_one(
                scenario_id,
                {
                    "status": ScenarioStatus.INGESTED.value,
                    "builds_ingested": builds_total,
                    "ingestion_completed_at": datetime.utcnow(),
                },
            )
            publish_scenario_update(
                scenario_id=scenario_id,
                status=ScenarioStatus.INGESTED.value,
                builds_total=builds_total,
                builds_ingested=builds_total,
                current_phase="Ingestion complete. Start processing when ready.",
            )
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
            # If using affected_repo_ids (new flow), we can just update many
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


def _resolve_filter_config(scenario: TrainingScenario) -> Dict[str, Any]:
    """Helper to resolve configuration dictionary from scenario."""
    data_config = scenario.data_source_config
    if isinstance(data_config, dict):
        config_dict = data_config
    else:
        config_dict = (
            data_config.model_dump()
            if hasattr(data_config, "model_dump")
            else data_config.__dict__
        )

    # Direct extraction from flat DTO/Dict
    languages = config_dict.get("languages", [])
    conclusions = config_dict.get("conclusions", [])
    ci_providers = config_dict.get("ci_providers", [])

    date_start = config_dict.get("date_start")
    date_end = config_dict.get("date_end")
    build_source_ids = config_dict.get("build_source_ids", [])

    return {
        "languages": languages,
        "conclusions": conclusions,
        "ci_providers": ci_providers,
        "date_start": date_start,
        "date_end": date_end,
        "build_source_ids": build_source_ids,
    }


def _find_matching_repos(
    db, languages: List[str], build_source_ids: List[str] = None
) -> List[Any]:
    """Find repositories matching language and source criteria."""
    raw_repo_repo = RawRepositoryRepository(db)
    repo_query: Dict[str, Any] = {"is_private": False}

    # If build sources are specified, restrict to repos in those sources
    if build_source_ids:
        from app.repositories.source_repo_stats import SourceRepoStatsRepository

        # Use Repository optimization
        repo_stats_repo = SourceRepoStatsRepository(db)
        distinct_repo_ids = repo_stats_repo.get_distinct_repo_ids(build_source_ids)

        if not distinct_repo_ids:
            return []

        repo_query["_id"] = {"$in": distinct_repo_ids}

    if languages and "all" not in languages:
        import re

        # Support case-insensitive matching using Regex
        regex_list = [
            re.compile(f"^{re.escape(lang)}$", re.IGNORECASE) for lang in languages
        ]
        repo_query["main_lang"] = {"$in": regex_list}

    return list(raw_repo_repo.find_many(repo_query))


def _process_ingestion_builds(
    db, scenario_id: str, repos: List[Any], filters: Dict[str, Any], corr_prefix: str
) -> int:
    """Query builds and create ingestion records."""
    ingestion_build_repo = TrainingIngestionBuildRepository(db)
    raw_build_run_repo = RawBuildRunRepository(db)

    repo_ids = [str(r.id) for r in repos]
    repo_cache = {str(r.id): r for r in repos}

    # Use optimized repository method
    batch_size = 1000
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


def _filter_builds_for_scenario(
    db,
    scenario: TrainingScenario,
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
    filters = _resolve_filter_config(scenario)

    # 2. Find matching repositories
    repos = _find_matching_repos(
        db, filters["languages"], filters.get("build_source_ids")
    )

    if not repos:
        logger.warning(f"{corr_prefix} [filter] No repos match filter criteria")
        return {"status": "error", "error": "No repositories match filter criteria"}

    logger.info(f"{corr_prefix} [filter] Found {len(repos)} matching repos")

    # 3. Process builds
    total_inserted = _process_ingestion_builds(
        db, scenario_id, repos, filters, corr_prefix
    )

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


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="app.tasks.training_ingestion.aggregate_scenario_ingestion",
    queue="scenario_ingestion",
    soft_time_limit=120,
    time_limit=180,
)
def aggregate_scenario_ingestion(
    self: SafeTask,
    results: List[Dict[str, Any]],
    scenario_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Chord callback: Aggregate ingestion results and mark scenario as INGESTED.

    After all repo ingestion chains complete, marks builds as INGESTED/FAILED.
    Does NOT auto-dispatch processing - user triggers Phase 2 manually.
    """

    def mark_failed(e: Exception):
        handler = _create_scenario_failure_handler(scenario_id, self.db)
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
        logger.info(
            f"{corr_prefix} [aggregate_ingestion] Processing results for {scenario_id}"
        )

        scenario_repo = TrainingScenarioRepository(self.db)
        ingestion_build_repo = TrainingIngestionBuildRepository(self.db)

        now = datetime.utcnow()

        # Determine per-build final status from resource_status in DB
        # 1. Check if git_history failed (affects ALL builds)
        git_history_failed = ingestion_build_repo.collection.count_documents(
            {
                "scenario_id": ObjectId(scenario_id),
                "status": IngestionStatus.INGESTING.value,
                "resource_status.git_history.status": "failed",
            }
        )

        if git_history_failed > 0:
            # Clone failed - mark all as FAILED
            ingestion_build_repo.collection.update_many(
                {
                    "scenario_id": ObjectId(scenario_id),
                    "status": IngestionStatus.INGESTING.value,
                },
                {
                    "$set": {
                        "status": IngestionStatus.FAILED.value,
                        "ingestion_error": "Clone failed",
                        "ingested_at": now,
                    }
                },
            )
        else:
            # 2. Mark builds with failed git_worktree as FAILED
            ingestion_build_repo.collection.update_many(
                {
                    "scenario_id": ObjectId(scenario_id),
                    "status": IngestionStatus.INGESTING.value,
                    "resource_status.git_worktree.status": "failed",
                },
                {
                    "$set": {
                        "status": IngestionStatus.FAILED.value,
                        "ingestion_error": "Worktree creation failed",
                        "ingested_at": now,
                    }
                },
            )

            # 3. Mark builds with failed build_logs as MISSING_RESOURCE
            ingestion_build_repo.collection.update_many(
                {
                    "scenario_id": ObjectId(scenario_id),
                    "status": IngestionStatus.INGESTING.value,
                    "resource_status.build_logs.status": "failed",
                },
                {
                    "$set": {
                        "status": IngestionStatus.MISSING_RESOURCE.value,
                        "ingestion_error": "Log download failed or expired",
                        "ingested_at": now,
                    }
                },
            )

            # 4. Mark remaining INGESTING builds as INGESTED
            ingestion_build_repo.collection.update_many(
                {
                    "scenario_id": ObjectId(scenario_id),
                    "status": IngestionStatus.INGESTING.value,
                },
                {
                    "$set": {
                        "status": IngestionStatus.INGESTED.value,
                        "ingested_at": now,
                    }
                },
            )

        # Count by status
        status_counts = ingestion_build_repo.count_by_status(scenario_id)
        ingested = status_counts.get(IngestionStatus.INGESTED.value, 0)
        missing_resource = status_counts.get(IngestionStatus.MISSING_RESOURCE.value, 0)
        failed = status_counts.get(IngestionStatus.FAILED.value, 0)
        total_builds = ingested + missing_resource + failed

        # Update scenario
        scenario_repo.update_one(
            scenario_id,
            {
                "status": ScenarioStatus.INGESTED.value,
                "builds_ingested": ingested,
                "builds_missing_resource": missing_resource,
                "builds_failed": failed,
                "ingestion_completed_at": now,
            },
        )

        # Build status message
        if failed > 0 or missing_resource > 0:
            parts = [f"{ingested} ready"]
            if failed > 0:
                parts.append(f"{failed} failed (retryable)")
            if missing_resource > 0:
                parts.append(f"{missing_resource} missing resources")
            msg = f"Ingestion done: {', '.join(parts)}. Start processing when ready."
        else:
            msg = f"Ingestion complete: {ingested} builds ready. Start processing when ready."

        logger.info(f"{corr_prefix} [aggregate_ingestion] {msg}")

        # Publish event for frontend
        publish_scenario_update(
            scenario_id=scenario_id,
            status=ScenarioStatus.INGESTED.value,
            builds_total=total_builds,
            builds_ingested=ingested,
            builds_missing_resource=missing_resource,
            builds_failed=failed,
            current_phase=msg,
        )

        return {
            "status": "completed",
            "final_status": ScenarioStatus.INGESTED.value,
            "builds_ingested": ingested,
            "builds_missing_resource": missing_resource,
            "builds_failed": failed,
        }

    return self.run_safe(
        job_id=scenario_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.training_ingestion.handle_scenario_chord_error",
    queue="scenario_ingestion",
    soft_time_limit=60,
    time_limit=120,
)
def handle_scenario_chord_error(
    self: PipelineTask,
    task_id: str,
    scenario_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Error callback for ingestion chord failure.
    """
    from celery.result import AsyncResult

    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

    # Try to get error info
    error_msg = "Unknown ingestion error"
    try:
        result = AsyncResult(task_id)
        if isinstance(result.result, Exception):
            error_msg = str(result.result)
        elif result.result:
            error_msg = str(result.result)
    except Exception as e:
        logger.warning(f"Could not retrieve exception for task {task_id}: {e}")

    logger.error(
        f"{corr_prefix} Ingestion chord failed for scenario {scenario_id}: {error_msg}"
    )

    ingestion_build_repo = TrainingIngestionBuildRepository(self.db)
    scenario_repo = TrainingScenarioRepository(self.db)

    now = datetime.utcnow()

    # Mark all INGESTING builds as FAILED
    failed_count = ingestion_build_repo.collection.update_many(
        {
            "scenario_id": ObjectId(scenario_id),
            "status": IngestionStatus.INGESTING.value,
        },
        {
            "$set": {
                "status": IngestionStatus.FAILED.value,
                "ingestion_error": f"Ingestion chord failed: {error_msg}",
                "ingested_at": now,
            }
        },
    ).modified_count

    # Check if any builds made it to INGESTED
    ingested_count = ingestion_build_repo.collection.count_documents(
        {
            "scenario_id": ObjectId(scenario_id),
            "status": IngestionStatus.INGESTED.value,
        }
    )

    if ingested_count > 0:
        # Some builds made it through
        scenario_repo.update_one(
            scenario_id,
            {
                "status": ScenarioStatus.INGESTED.value,
                "builds_ingested": ingested_count,
                "builds_failed": failed_count,
                "ingestion_completed_at": now,
            },
        )
        publish_scenario_update(
            scenario_id=scenario_id,
            status=ScenarioStatus.INGESTED.value,
            builds_ingested=ingested_count,
            builds_failed=failed_count,
        )
    else:
        # No builds made it
        scenario_repo.update_one(
            scenario_id,
            {
                "status": ScenarioStatus.FAILED.value,
                "error_message": error_msg,
            },
        )
        publish_scenario_update(
            scenario_id=scenario_id,
            status=ScenarioStatus.FAILED.value,
            error=error_msg,
        )

    return {
        "status": "handled",
        "failed_builds": failed_count,
        "ingested_builds": ingested_count,
        "error": error_msg,
    }


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

    def mark_failed(e: Exception):
        handler = _create_scenario_failure_handler(scenario_id, self.db)
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
                msg += (
                    f" ({missing_count} builds have missing resources - not retryable)"
                )
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

        logger.info(
            f"{corr_prefix} Reset {reset_result.modified_count} failed builds to PENDING"
        )

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
            commit_shas = list(
                {b["commit_sha"] for b in repo_builds if b.get("commit_sha")}
            )

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

        publish_scenario_update(
            scenario_id=scenario_id,
            status=ScenarioStatus.INGESTING.value,
            current_phase=f"Re-ingesting {len(pending_builds)} failed builds...",
        )

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
