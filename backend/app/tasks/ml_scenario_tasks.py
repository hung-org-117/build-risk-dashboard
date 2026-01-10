"""
ML Scenario Pipeline Tasks - Celery tasks for ML Dataset Scenario Builder.

Pipeline Phases:
1. start_scenario_generation - Orchestrator: Filter → Ingest → Process → Split
2. filter_scenario_builds - Query raw_repositories + raw_build_runs by YAML config
3. ingest_scenario_builds - Clone, worktree, logs (reuses existing ingestion)
4. process_scenario_builds - Feature extraction via Hamilton DAG
5. split_scenario_dataset - Apply splitting strategy and export files

Flow:
    start_scenario_generation
        └── chain(
                filter_scenario_builds,
                ingest_scenario_builds,
                process_scenario_builds,
                split_scenario_dataset
            )
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from bson import ObjectId
from celery import chain

from app import paths
from app.celery_app import celery_app
from app.entities.enums import ExtractionStatus
from app.entities.ml_scenario import MLScenario, MLScenarioStatus
from app.entities.ml_scenario_enrichment_build import MLScenarioEnrichmentBuild
from app.entities.ml_scenario_import_build import (
    MLScenarioImportBuild,
    MLScenarioImportBuildStatus,
)
from app.repositories.ml_dataset_split import MLDatasetSplitRepository
from app.repositories.ml_scenario import MLScenarioRepository
from app.repositories.ml_scenario_enrichment_build import (
    MLScenarioEnrichmentBuildRepository,
)
from app.repositories.ml_scenario_import_build import MLScenarioImportBuildRepository
from app.repositories.raw_build_run import RawBuildRunRepository
from app.repositories.raw_repository import RawRepositoryRepository
from app.tasks.base import PipelineTask
from app.tasks.shared.events import publish_scenario_update

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.ml_scenario_tasks.start_scenario_generation",
    queue="scenario_ingestion",
    soft_time_limit=120,
    time_limit=180,
)
def start_scenario_generation(
    self: PipelineTask,
    scenario_id: str,
) -> Dict[str, Any]:
    """
    Orchestrator: Start ML scenario dataset generation.

    Dispatches the full pipeline: Filter → Ingest → Process → Split
    """
    correlation_id = str(uuid.uuid4())
    logger.info(
        f"[start_scenario] Starting scenario {scenario_id}, corr={correlation_id[:8]}"
    )

    scenario_repo = MLScenarioRepository(self.db)

    # Load scenario
    scenario = scenario_repo.find_by_id(scenario_id)
    if not scenario:
        logger.error(f"Scenario {scenario_id} not found")
        return {"status": "error", "error": "Scenario not found"}

    # Update status to FILTERING
    scenario_repo.update_one(
        scenario_id,
        {
            "status": MLScenarioStatus.FILTERING.value,
            "filtering_started_at": datetime.utcnow(),
            "current_task_id": self.request.id,
            "error_message": None,
        },
    )

    # Publish SSE event for UI update
    publish_scenario_update(
        scenario_id=scenario_id,
        status=MLScenarioStatus.FILTERING.value,
        current_phase="Filtering builds from database",
    )

    # Dispatch pipeline chain
    pipeline = chain(
        filter_scenario_builds.s(scenario_id, correlation_id),
        ingest_scenario_builds.s(scenario_id, correlation_id),
        process_scenario_builds.s(scenario_id, correlation_id),
        split_scenario_dataset.s(scenario_id, correlation_id),
    )
    pipeline.apply_async()

    logger.info(f"[start_scenario] Dispatched pipeline for scenario {scenario_id}")

    return {
        "status": "dispatched",
        "scenario_id": scenario_id,
        "correlation_id": correlation_id,
    }


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.ml_scenario_tasks.filter_scenario_builds",
    queue="scenario_ingestion",
    soft_time_limit=300,
    time_limit=360,
)
def filter_scenario_builds(
    self: PipelineTask,
    prev_result: Any,
    scenario_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Phase 1: Filter - Query raw_repositories + raw_build_runs by YAML config.

    Creates MLScenarioImportBuild records for matching builds.
    """
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
    logger.info(f"{corr_prefix} [filter] Starting for scenario {scenario_id}")

    scenario_repo = MLScenarioRepository(self.db)
    import_build_repo = MLScenarioImportBuildRepository(self.db)
    raw_repo_repo = RawRepositoryRepository(self.db)
    raw_build_run_repo = RawBuildRunRepository(self.db)

    scenario = scenario_repo.find_by_id(scenario_id)
    if not scenario:
        return {"status": "error", "error": "Scenario not found"}

    try:
        # Build query from data_source_config
        data_config = scenario.data_source_config
        if isinstance(data_config, dict):
            # Raw dictionary access
            config_dict = data_config
        else:
            # Pydantic entity access - convert to dict to access 'extra' fields
            config_dict = (
                data_config.model_dump()
                if hasattr(data_config, "model_dump")
                else data_config.__dict__
            )

        # Helper to get value from flat key or nested section
        def get_cfg(key, section=None, subkey=None, default=None):
            # 1. Try flat key
            if key in config_dict and config_dict[key] is not None:
                return config_dict[key]
            # 2. Try nested section (e.g., repositories.filter_by)
            if section and section in config_dict:
                section_dict = config_dict[section]
                if isinstance(section_dict, dict) and subkey in section_dict:
                    return section_dict[subkey]
            # 3. Default
            return default

        filter_by = get_cfg("filter_by", "repositories", "filter_by", "all")
        languages = get_cfg("languages", "repositories", "languages", [])
        repo_names = get_cfg("repo_names", "repositories", "repo_names", [])
        owners = get_cfg("owners", "repositories", "owners", [])

        # Builds config
        conclusions = get_cfg(
            "conclusions", "builds", "conclusions", ["success", "failure"]
        )
        exclude_bots = get_cfg("exclude_bots", "builds", "exclude_bots", True)

        # Date range handling (nested in builds.date_range)
        date_start = config_dict.get("date_start")
        date_end = config_dict.get("date_end")

        if not date_start and "builds" in config_dict:
            builds_cfg = config_dict["builds"]
            if isinstance(builds_cfg, dict) and "date_range" in builds_cfg:
                date_range = builds_cfg["date_range"]
                if isinstance(date_range, dict):
                    date_start = date_range.get("start")
                    date_end = date_range.get("end")

        ci_provider = config_dict.get("ci_provider")  # ci_provider is flat in YAML too

        # Query public repositories
        repo_query: Dict[str, Any] = {"is_private": False}

        if filter_by == "by_language" and languages:
            repo_query["main_lang"] = {"$in": [lang.lower() for lang in languages]}
        elif filter_by == "by_name" and repo_names:
            repo_query["full_name"] = {"$in": repo_names}
        elif filter_by == "by_owner" and owners:
            repo_query["$or"] = [{"full_name": {"$regex": f"^{o}/"}} for o in owners]

        repos = raw_repo_repo.find_many(repo_query)
        repo_ids = [str(r.id) for r in repos]

        if not repo_ids:
            logger.warning(f"{corr_prefix} [filter] No repos match filter criteria")
            scenario_repo.update_one(
                scenario_id,
                {
                    "status": MLScenarioStatus.FAILED.value,
                    "error_message": "No repositories match filter criteria",
                },
            )
            return {"status": "error", "error": "No repos match filter"}

        logger.info(f"{corr_prefix} [filter] Found {len(repo_ids)} matching repos")

        # Query builds for these repos
        build_query: Dict[str, Any] = {
            "raw_repo_id": {"$in": [ObjectId(rid) for rid in repo_ids]},
        }

        # Filter by conclusion
        if conclusions:
            build_query["conclusion"] = {"$in": conclusions}

        # Filter by date range
        if date_start or date_end:
            date_filter = {}
            if date_start:
                date_filter["$gte"] = (
                    date_start
                    if isinstance(date_start, datetime)
                    else datetime.fromisoformat(str(date_start))
                )
            if date_end:
                date_filter["$lte"] = (
                    date_end
                    if isinstance(date_end, datetime)
                    else datetime.fromisoformat(str(date_end))
                )
            if date_filter:
                build_query["started_at"] = date_filter

        # Exclude bot commits
        if exclude_bots:
            build_query["$and"] = [
                {"actor_login": {"$not": {"$regex": "\\[bot\\]$", "$options": "i"}}},
                {"actor_login": {"$not": {"$regex": "-bot$", "$options": "i"}}},
            ]

        builds = raw_build_run_repo.find_many(build_query)

        if not builds:
            logger.warning(f"{corr_prefix} [filter] No builds match filter criteria")
            scenario_repo.update_one(
                scenario_id,
                {
                    "status": MLScenarioStatus.FAILED.value,
                    "error_message": "No builds match filter criteria",
                },
            )
            return {"status": "error", "error": "No builds match filter"}

        logger.info(f"{corr_prefix} [filter] Found {len(builds)} matching builds")

        # Create import build records
        import_data = []
        repo_cache = {str(r.id): r for r in repos}

        for build in builds:
            repo = repo_cache.get(str(build.raw_repo_id))
            import_data.append(
                {
                    "raw_repo_id": build.raw_repo_id,
                    "raw_build_run_id": build.id,
                    "ci_run_id": build.ci_run_id or "",
                    "commit_sha": build.commit_sha or "",
                    "repo_full_name": repo.full_name if repo else "",
                    "github_repo_id": repo.github_repo_id if repo else None,
                    "required_resources": ["git_history", "git_worktree", "build_logs"],
                }
            )

        created = import_build_repo.bulk_create_from_raw_builds(
            scenario_id, import_data
        )

        # Update scenario stats
        scenario_repo.update_one(
            scenario_id,
            {
                "status": MLScenarioStatus.INGESTING.value,
                "builds_total": len(builds),
                "filtering_completed_at": datetime.utcnow(),
                "ingestion_started_at": datetime.utcnow(),
            },
        )

        # Publish SSE event for UI update
        publish_scenario_update(
            scenario_id=scenario_id,
            status=MLScenarioStatus.INGESTING.value,
            builds_total=len(builds),
            current_phase="Ingesting build data (clone, worktree, logs)",
        )

        logger.info(f"{corr_prefix} [filter] Created {created} import build records")

        return {
            "status": "completed",
            "repos_found": len(repo_ids),
            "builds_found": len(builds),
            "import_builds_created": created,
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"{corr_prefix} [filter] Error: {error_msg}")
        scenario_repo.update_one(
            scenario_id,
            {
                "status": MLScenarioStatus.FAILED.value,
                "error_message": f"Filter phase failed: {error_msg}",
            },
        )
        raise


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.ml_scenario_tasks.ingest_scenario_builds",
    queue="scenario_ingestion",
    soft_time_limit=120,
    time_limit=180,
)
def ingest_scenario_builds(
    self: PipelineTask,
    prev_result: Any,
    scenario_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Phase 2: Ingest - Clone repos, create worktrees, download logs.

    Dispatches parallel ingestion chains per repo using chord pattern.
    After all chains complete, aggregate_scenario_ingestion callback triggers processing.
    """
    from celery import chord, group

    from app.tasks.pipeline.resource_dag import get_ingestion_tasks_by_level
    from app.tasks.shared import build_ingestion_workflow

    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
    logger.info(f"{corr_prefix} [ingest] Starting for scenario {scenario_id}")

    scenario_repo = MLScenarioRepository(self.db)
    import_build_repo = MLScenarioImportBuildRepository(self.db)
    raw_repo_repo = RawRepositoryRepository(self.db)

    scenario = scenario_repo.find_by_id(scenario_id)
    if not scenario:
        return {"status": "error", "error": "Scenario not found"}

    try:
        # Get pending builds
        pending_builds, total = import_build_repo.find_by_scenario(
            scenario_id, status_filter=MLScenarioImportBuildStatus.PENDING
        )

        if not pending_builds:
            logger.info(f"{corr_prefix} [ingest] No pending builds to ingest")
            scenario_repo.update_one(
                scenario_id,
                {
                    "status": MLScenarioStatus.PROCESSING.value,
                    "ingestion_completed_at": datetime.utcnow(),
                    "processing_started_at": datetime.utcnow(),
                },
            )
            return {"status": "completed", "builds_ingested": 0}

        # Group builds by repo
        builds_by_repo: Dict[str, List[MLScenarioImportBuild]] = {}
        for build in pending_builds:
            repo_id = str(build.raw_repo_id)
            if repo_id not in builds_by_repo:
                builds_by_repo[repo_id] = []
            builds_by_repo[repo_id].append(build)

        # Define required resources (can be configured via YAML in future)
        required_resources = ["git_history", "git_worktree", "build_logs"]
        tasks_by_level = get_ingestion_tasks_by_level(required_resources)

        logger.info(
            f"{corr_prefix} [ingest] Building chains for {len(builds_by_repo)} repos, "
            f"resources={required_resources}"
        )

        # Build ingestion chains per repo
        ingestion_chains = []
        repo_metadata = []

        for raw_repo_id, repo_builds in builds_by_repo.items():
            raw_repo = raw_repo_repo.find_by_id(raw_repo_id)
            if not raw_repo:
                logger.warning(
                    f"{corr_prefix} [ingest] Repo {raw_repo_id} not found, skipping"
                )
                continue

            # Get build IDs and commit SHAs
            build_ids = [b.ci_run_id for b in repo_builds if b.ci_run_id]
            commit_shas = list({b.commit_sha for b in repo_builds if b.commit_sha})

            if not build_ids:
                continue

            # Determine CI provider (default to github_actions)
            ci_provider = "github_actions"

            # Build ingestion chain for this repo
            repo_chain = build_ingestion_workflow(
                tasks_by_level=tasks_by_level,
                raw_repo_id=raw_repo_id,
                github_repo_id=raw_repo.github_repo_id,
                full_name=raw_repo.full_name,
                build_ids=build_ids,
                commit_shas=commit_shas,
                ci_provider=ci_provider,
                correlation_id=correlation_id,
                pipeline_id=scenario_id,
                pipeline_type="ml_scenario",  # New pipeline type
            )

            if repo_chain:
                ingestion_chains.append(repo_chain)
                repo_metadata.append(
                    {
                        "raw_repo_id": raw_repo_id,
                        "full_name": raw_repo.full_name,
                        "builds": len(build_ids),
                        "commits": len(commit_shas),
                    }
                )

        if not ingestion_chains:
            # No ingestion needed - mark all as ingested and proceed
            logger.info(f"{corr_prefix} [ingest] No ingestion chains needed")
            for build in pending_builds:
                import_build_repo.update_status(
                    str(build.id),
                    MLScenarioImportBuildStatus.INGESTED,
                )

            scenario_repo.update_one(
                scenario_id,
                {
                    "status": MLScenarioStatus.PROCESSING.value,
                    "builds_ingested": len(pending_builds),
                    "ingestion_completed_at": datetime.utcnow(),
                    "processing_started_at": datetime.utcnow(),
                },
            )
            return {"status": "completed", "builds_ingested": len(pending_builds)}

        # Dispatch chord: parallel repo chains → aggregate callback
        callback = aggregate_scenario_ingestion.s(
            scenario_id=scenario_id,
            correlation_id=correlation_id,
        )

        chord(group(ingestion_chains), callback).apply_async()

        logger.info(
            f"{corr_prefix} [ingest] Dispatched {len(ingestion_chains)} ingestion chains"
        )

        return {
            "status": "dispatched",
            "ingestion_chains": len(ingestion_chains),
            "repo_metadata": repo_metadata,
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"{corr_prefix} [ingest] Error: {error_msg}")
        scenario_repo.update_one(
            scenario_id,
            {
                "status": MLScenarioStatus.FAILED.value,
                "error_message": f"Ingestion phase failed: {error_msg}",
            },
        )
        raise


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.ml_scenario_tasks.aggregate_scenario_ingestion",
    queue="scenario_ingestion",
    soft_time_limit=120,
    time_limit=180,
)
def aggregate_scenario_ingestion(
    self: PipelineTask,
    results: List[Dict[str, Any]],
    scenario_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Chord callback: Aggregate ingestion results and trigger processing.

    After all repo ingestion chains complete, marks builds as ingested
    and dispatches the processing phase.
    """
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
    logger.info(
        f"{corr_prefix} [aggregate_ingest] Processing results for {scenario_id}"
    )

    scenario_repo = MLScenarioRepository(self.db)
    import_build_repo = MLScenarioImportBuildRepository(self.db)

    scenario = scenario_repo.find_by_id(scenario_id)
    if not scenario:
        return {"status": "error", "error": "Scenario not found"}

    try:
        # Mark pending builds as ingested
        pending_builds, _ = import_build_repo.find_by_scenario(
            scenario_id, status_filter=MLScenarioImportBuildStatus.PENDING
        )
        ingesting_builds, _ = import_build_repo.find_by_scenario(
            scenario_id, status_filter=MLScenarioImportBuildStatus.INGESTING
        )

        ingested_count = 0
        for build in pending_builds + ingesting_builds:
            import_build_repo.update_status(
                str(build.id),
                MLScenarioImportBuildStatus.INGESTED,
            )
            ingested_count += 1

        # Update scenario status
        scenario_repo.update_one(
            scenario_id,
            {
                "status": MLScenarioStatus.PROCESSING.value,
                "builds_ingested": ingested_count,
                "ingestion_completed_at": datetime.utcnow(),
                "processing_started_at": datetime.utcnow(),
            },
        )

        # Publish SSE event for UI update
        publish_scenario_update(
            scenario_id=scenario_id,
            status=MLScenarioStatus.PROCESSING.value,
            builds_total=scenario.builds_total,
            builds_ingested=ingested_count,
            current_phase="Extracting features via Hamilton DAG",
        )

        logger.info(
            f"{corr_prefix} [aggregate_ingest] Ingested {ingested_count} builds, "
            f"dispatching processing"
        )

        # Dispatch processing phase
        process_scenario_builds.delay(None, scenario_id, correlation_id)

        return {
            "status": "completed",
            "builds_ingested": ingested_count,
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"{corr_prefix} [aggregate_ingest] Error: {error_msg}")
        scenario_repo.update_one(
            scenario_id,
            {
                "status": MLScenarioStatus.FAILED.value,
                "error_message": f"Ingestion aggregation failed: {error_msg}",
            },
        )
        raise


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.ml_scenario_tasks.process_scenario_builds",
    queue="scenario_processing",
    soft_time_limit=180,
    time_limit=240,
)
def process_scenario_builds(
    self: PipelineTask,
    prev_result: Any,
    scenario_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Phase 3: Process - Feature extraction via Hamilton DAG.

    Creates MLScenarioEnrichmentBuild records and dispatches sequential
    feature extraction chain (oldest → newest for temporal features).
    """
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
    logger.info(f"{corr_prefix} [process] Starting for scenario {scenario_id}")

    scenario_repo = MLScenarioRepository(self.db)
    import_build_repo = MLScenarioImportBuildRepository(self.db)
    enrichment_build_repo = MLScenarioEnrichmentBuildRepository(self.db)
    raw_build_run_repo = RawBuildRunRepository(self.db)

    scenario = scenario_repo.find_by_id(scenario_id)
    if not scenario:
        return {"status": "error", "error": "Scenario not found"}

    try:
        # Get ingested builds
        ingested_builds, total = import_build_repo.find_by_scenario(
            scenario_id, status_filter=MLScenarioImportBuildStatus.INGESTED
        )

        if not ingested_builds:
            logger.warning(f"{corr_prefix} [process] No ingested builds to process")
            scenario_repo.update_one(
                scenario_id,
                {
                    "status": MLScenarioStatus.SPLITTING.value,
                    "processing_completed_at": datetime.utcnow(),
                    "splitting_started_at": datetime.utcnow(),
                },
            )
            return {"status": "completed", "builds_features_extracted": 0}

        # Get outcome from RawBuildRun.conclusion
        raw_build_run_ids = [b.raw_build_run_id for b in ingested_builds]
        raw_build_runs = {
            str(r.id): r
            for r in [raw_build_run_repo.find_by_id(rid) for rid in raw_build_run_ids]
            if r is not None
        }

        # Sort by build creation time (oldest first) for temporal features
        ingested_builds.sort(
            key=lambda b: (
                raw_build_runs.get(str(b.raw_build_run_id)).created_at
                if raw_build_runs.get(str(b.raw_build_run_id))
                else b.created_at
            )
            or datetime.utcnow()
        )

        # Create enrichment build records
        enrichment_build_ids = []
        for build in ingested_builds:
            raw_run = raw_build_runs.get(str(build.raw_build_run_id))
            # Determine outcome from conclusion
            if raw_run and raw_run.conclusion:
                outcome = 1 if raw_run.conclusion.lower() == "failure" else 0
            else:
                outcome = 1 if "failure" in str(build.status).lower() else 0

            eb = enrichment_build_repo.upsert_for_import_build(
                scenario_id=scenario_id,
                scenario_import_build_id=str(build.id),
                raw_repo_id=str(build.raw_repo_id),
                raw_build_run_id=str(build.raw_build_run_id),
                ci_run_id=build.ci_run_id,
                commit_sha=build.commit_sha,
                repo_full_name=build.repo_full_name,
                outcome=outcome,
                build_started_at=raw_run.run_started_at if raw_run else None,
            )
            enrichment_build_ids.append(str(eb.id))

        logger.info(
            f"{corr_prefix} [process] Created {len(enrichment_build_ids)} enrichment builds"
        )

        # Get selected features from feature_config
        feature_config = scenario.feature_config
        if isinstance(feature_config, dict):
            dag_features = feature_config.get("dag_features", [])
        else:
            dag_features = feature_config.dag_features or []

        # Expand wildcard patterns to actual feature list
        selected_features = _expand_feature_patterns(dag_features)

        logger.info(
            f"{corr_prefix} [process] Feature patterns: {dag_features}, "
            f"expanded to {len(selected_features)} features"
        )

        # Get scan_metrics config for parallel scan dispatch
        if isinstance(feature_config, dict):
            scan_metrics_config = feature_config.get("scan_metrics", {})
        else:
            scan_metrics_config = feature_config.scan_metrics or {}

        has_scans = bool(scan_metrics_config.get("sonarqube")) or bool(
            scan_metrics_config.get("trivy")
        )

        # Dispatch scans (fire-and-forget, parallel to processing)
        if has_scans:
            logger.info(f"{corr_prefix} [process] Dispatching scans in parallel")
            dispatch_scenario_scans.delay(
                scenario_id=scenario_id,
                correlation_id=correlation_id,
            )

        # Dispatch sequential processing chain
        processing_tasks = [
            process_single_scenario_build.si(
                scenario_id=scenario_id,
                enrichment_build_id=build_id,
                selected_features=selected_features,
                correlation_id=correlation_id,
            )
            for build_id in enrichment_build_ids
        ]

        # Chain: B1 → B2 → ... → finalize
        workflow = chain(
            *processing_tasks,
            finalize_scenario_processing.si(
                scenario_id=scenario_id,
                correlation_id=correlation_id,
            ),
        )
        workflow.apply_async()

        logger.info(
            f"{corr_prefix} [process] Dispatched {len(processing_tasks)} builds for processing"
        )

        return {
            "status": "dispatched",
            "enrichment_builds_created": len(enrichment_build_ids),
            "total_builds": len(processing_tasks),
            "scans_dispatched": has_scans,
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"{corr_prefix} [process] Error: {error_msg}")
        scenario_repo.update_one(
            scenario_id,
            {
                "status": MLScenarioStatus.FAILED.value,
                "error_message": f"Processing phase failed: {error_msg}",
            },
        )
        raise


def _build_split_dataframe(
    enrichment_builds: List[Any],
    raw_repos: Dict[str, Any],
    db,
) -> pd.DataFrame:
    """
    Build DataFrame from enrichment builds with features.

    Extracts metadata and loads features from FeatureVector collection.
    Merges both `features` and `scan_metrics` for complete feature set.
    """
    import pandas as pd

    from app.repositories.feature_vector import FeatureVectorRepository

    fv_repo = FeatureVectorRepository(db)
    data = []

    for eb in enrichment_builds:
        raw_repo = raw_repos.get(str(eb.raw_repo_id))
        primary_language = (
            raw_repo.main_lang if raw_repo and raw_repo.main_lang else "other"
        )

        row_data = {
            "id": str(eb.id),
            "outcome": eb.outcome or 0,
            "repo_full_name": eb.repo_full_name,
            "primary_language": primary_language.lower(),
            "build_started_at": eb.build_started_at,  # For temporal ordering
        }

        # Load features from feature_vector (if available)
        if eb.feature_vector_id:
            fv = fv_repo.find_by_id(str(eb.feature_vector_id))
            if fv:
                # Merge DAG features (gh_*, tr_*, git_*, etc.)
                if fv.features:
                    row_data.update(fv.features)

                # Merge scan metrics (sonar_*, trivy_*)
                if fv.scan_metrics:
                    row_data.update(fv.scan_metrics)

        data.append(row_data)

    df = pd.DataFrame(data)
    df.index = range(len(df))
    return df


def _expand_feature_patterns(patterns: List[str]) -> List[str]:
    """
    Expand wildcard feature patterns to actual feature names.

    Patterns like "build_*", "git_*" are expanded using feature metadata.
    """
    from app.tasks.pipeline.feature_dag._feature_definitions import FEATURE_REGISTRY

    if not patterns:
        # Return all available features if no patterns specified
        return list(FEATURE_REGISTRY.keys())

    expanded = set()
    for pattern in patterns:
        if "*" in pattern:
            # Wildcard pattern - match prefix
            prefix = pattern.replace("*", "")
            for feature_name in FEATURE_REGISTRY.keys():
                if feature_name.startswith(prefix):
                    expanded.add(feature_name)
        else:
            # Exact feature name
            if pattern in FEATURE_REGISTRY:
                expanded.add(pattern)

    return list(expanded) if expanded else list(FEATURE_REGISTRY.keys())


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.ml_scenario_tasks.process_single_scenario_build",
    queue="scenario_processing",
    soft_time_limit=300,
    time_limit=600,
    max_retries=2,
)
def process_single_scenario_build(
    self: PipelineTask,
    scenario_id: str,
    enrichment_build_id: str,
    selected_features: List[str],
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Process a single ML scenario build for feature extraction.

    Uses extract_features_for_build helper with Hamilton DAG.
    """
    from app.entities.enums import AuditLogCategory
    from app.tasks.shared import extract_features_for_build

    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

    scenario_repo = MLScenarioRepository(self.db)
    enrichment_build_repo = MLScenarioEnrichmentBuildRepository(self.db)
    raw_build_run_repo = RawBuildRunRepository(self.db)
    raw_repo_repo = RawRepositoryRepository(self.db)

    # Load enrichment build
    enrichment_build = enrichment_build_repo.find_by_id(enrichment_build_id)
    if not enrichment_build:
        logger.error(f"{corr_prefix} EnrichmentBuild {enrichment_build_id} not found")
        return {"status": "error", "error": "EnrichmentBuild not found"}

    if enrichment_build.extraction_status == ExtractionStatus.COMPLETED.value:
        return {"status": "skipped", "reason": "already_processed"}

    # Load dependencies
    raw_build_run = raw_build_run_repo.find_by_id(enrichment_build.raw_build_run_id)
    if not raw_build_run:
        enrichment_build_repo.update_extraction_status(
            enrichment_build_id,
            ExtractionStatus.FAILED,
            error_message="RawBuildRun not found",
        )
        return {"status": "failed", "error": "RawBuildRun not found"}

    raw_repo = raw_repo_repo.find_by_id(raw_build_run.raw_repo_id)
    if not raw_repo:
        enrichment_build_repo.update_extraction_status(
            enrichment_build_id,
            ExtractionStatus.FAILED,
            error_message="RawRepository not found",
        )
        return {"status": "failed", "error": "RawRepository not found"}

    scenario = scenario_repo.find_by_id(scenario_id)
    if not scenario:
        return {"status": "error", "error": "Scenario not found"}

    try:
        # Mark as in progress
        enrichment_build_repo.update_extraction_status(
            enrichment_build_id,
            ExtractionStatus.IN_PROGRESS,
        )

        # Extract features using Hamilton DAG
        result = extract_features_for_build(
            db=self.db,
            raw_repo=raw_repo,
            feature_config={},  # ML scenarios use default config
            raw_build_run=raw_build_run,
            selected_features=selected_features,
            output_build_id=enrichment_build_id,
            category=AuditLogCategory.ML_SCENARIO,  # New category
        )

        # Update enrichment build with result
        if result["status"] == "completed":
            enrichment_build_repo.update_extraction_status(
                enrichment_build_id,
                ExtractionStatus.COMPLETED,
                feature_vector_id=result.get("feature_vector_id"),
            )
        elif result["status"] == "partial":
            enrichment_build_repo.update_extraction_status(
                enrichment_build_id,
                ExtractionStatus.PARTIAL,
                feature_vector_id=result.get("feature_vector_id"),
                error_message="; ".join(result.get("errors", [])),
            )
        else:
            enrichment_build_repo.update_extraction_status(
                enrichment_build_id,
                ExtractionStatus.FAILED,
                error_message="; ".join(result.get("errors", [])),
            )

        # Increment processed count
        scenario_repo.increment_counter(scenario_id, "builds_features_extracted")

        logger.info(
            f"{corr_prefix} [process_single] {enrichment_build_id}: "
            f"status={result['status']}, features={result.get('feature_count', 0)}"
        )

        return {
            "status": result["status"],
            "build_id": enrichment_build_id,
            "feature_count": result.get("feature_count", 0),
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(
            f"{corr_prefix} [process_single] Error for {enrichment_build_id}: {error_msg}"
        )
        enrichment_build_repo.update_extraction_status(
            enrichment_build_id,
            ExtractionStatus.FAILED,
            error_message=error_msg,
        )
        scenario_repo.increment_counter(scenario_id, "builds_failed")
        raise


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.ml_scenario_tasks.finalize_scenario_processing",
    queue="scenario_processing",
    soft_time_limit=60,
    time_limit=120,
)
def finalize_scenario_processing(
    self: PipelineTask,
    scenario_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Finalize processing after all builds extracted.

    Dispatches split_scenario_dataset to continue pipeline.
    """
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
    logger.info(f"{corr_prefix} [finalize_process] Finalizing for {scenario_id}")

    scenario_repo = MLScenarioRepository(self.db)
    enrichment_build_repo = MLScenarioEnrichmentBuildRepository(self.db)

    # Get stats
    stats = enrichment_build_repo.aggregate_stats_by_scenario(scenario_id)
    completed = stats.get("completed", 0)
    partial = stats.get("partial", 0)
    failed = stats.get("failed", 0)
    total = completed + partial + failed

    # Update scenario
    scenario_repo.update_one(
        scenario_id,
        {
            "status": MLScenarioStatus.SPLITTING.value,
            "builds_features_extracted": completed + partial,
            "builds_failed": failed,
            "processing_completed_at": datetime.utcnow(),
            "splitting_started_at": datetime.utcnow(),
        },
    )

    # Publish SSE event for UI update
    scenario = scenario_repo.find_by_id(scenario_id)
    publish_scenario_update(
        scenario_id=scenario_id,
        status=MLScenarioStatus.SPLITTING.value,
        builds_total=scenario.builds_total if scenario else total,
        builds_ingested=scenario.builds_ingested if scenario else total,
        builds_features_extracted=completed + partial,
        builds_failed=failed,
        current_phase="Applying splitting strategy and exporting files",
    )

    logger.info(
        f"{corr_prefix} [finalize_process] Completed: {completed + partial}/{total}, "
        f"failed: {failed}. Dispatching split phase."
    )

    # Dispatch split phase
    split_scenario_dataset.delay(None, scenario_id, correlation_id)

    return {
        "status": "completed",
        "builds_features_extracted": completed + partial,
        "builds_failed": failed,
        "total": total,
    }


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.ml_scenario_tasks.split_scenario_dataset",
    queue="scenario_processing",
    soft_time_limit=600,
    time_limit=720,
)
def split_scenario_dataset(
    self: PipelineTask,
    prev_result: Any,
    scenario_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Phase 4: Split - Apply splitting strategy and export files.

    Uses SplittingStrategyService to split data and exports to parquet/csv.
    """
    import pandas as pd

    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
    logger.info(f"{corr_prefix} [split] Starting for scenario {scenario_id}")

    scenario_repo = MLScenarioRepository(self.db)
    enrichment_build_repo = MLScenarioEnrichmentBuildRepository(self.db)
    split_repo = MLDatasetSplitRepository(self.db)

    scenario = scenario_repo.find_by_id(scenario_id)
    if not scenario:
        return {"status": "error", "error": "Scenario not found"}

    try:
        from app.services.splitting_strategy_service import SplittingStrategyService

        # Get completed enrichment builds
        enrichment_builds = enrichment_build_repo.get_completed_with_features(
            scenario_id
        )

        if not enrichment_builds:
            logger.warning(f"{corr_prefix} [split] No completed builds to split")
            scenario_repo.update_one(
                scenario_id,
                {
                    "status": MLScenarioStatus.FAILED.value,
                    "error_message": "No completed builds to split",
                },
            )
            return {"status": "error", "error": "No completed builds"}

        # Build DataFrame from enrichment builds
        raw_repo_repo = RawRepositoryRepository(self.db)
        raw_repo_ids = list({str(eb.raw_repo_id) for eb in enrichment_builds})
        raw_repos = {
            str(r.id): r
            for r in [raw_repo_repo.find_by_id(rid) for rid in raw_repo_ids]
            if r is not None
        }

        df = _build_split_dataframe(enrichment_builds, raw_repos, self.db)

        # Apply preprocessing using strategy-based service
        preprocessing_config = getattr(scenario, "preprocessing_config", None)
        if preprocessing_config is None and hasattr(scenario, "__dict__"):
            preprocessing_config = scenario.__dict__.get("preprocessing_config")

        if preprocessing_config:
            from app.services.preprocessing_service import PreprocessingService

            config_dict = (
                preprocessing_config
                if isinstance(preprocessing_config, dict)
                else preprocessing_config.__dict__
            )
            preprocessing_service = PreprocessingService.from_dict(config_dict)
            df = preprocessing_service.preprocess(df)
            logger.info(f"{corr_prefix} [split] Applied preprocessing")

        # Apply splitting strategy
        splitting_service = SplittingStrategyService()

        # Get splitting config
        splitting_config = scenario.splitting_config
        if isinstance(splitting_config, dict):
            from app.entities.ml_scenario import SplittingConfig

            splitting_config = SplittingConfig(**splitting_config)

        result = splitting_service.apply_split(
            df=df,
            config=splitting_config,
            label_column="outcome",
        )

        # Assign splits to enrichment builds
        # Use df['id'] column instead of data list
        id_list = df["id"].tolist()
        assignments = {
            "train": [id_list[i] for i in result.train_indices],
            "validation": [id_list[i] for i in result.val_indices],
            "test": [id_list[i] for i in result.test_indices],
        }
        enrichment_build_repo.assign_splits(scenario_id, assignments)

        # Create output directory
        output_dir = paths.get_ml_dataset_dir(scenario_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get output format
        output_config = scenario.output_config
        if isinstance(output_config, dict):
            file_format = output_config.get("format", "parquet")
        else:
            file_format = output_config.format or "parquet"

        # Export split files
        split_stats = {}
        for split_type, indices in [
            ("train", result.train_indices),
            ("validation", result.val_indices),
            ("test", result.test_indices),
        ]:
            if not indices:
                continue

            split_df = df.loc[indices]

            # Determine file path
            file_path = paths.get_ml_dataset_split_path(
                scenario_id, split_type, file_format
            )

            # Export
            start_time = datetime.utcnow()
            if file_format == "parquet":
                split_df.to_parquet(file_path, index=False)
            elif file_format == "csv":
                split_df.to_csv(file_path, index=False)
            else:
                split_df.to_pickle(file_path)

            duration = (datetime.utcnow() - start_time).total_seconds()
            file_size = file_path.stat().st_size

            # Calculate class distribution
            class_dist = split_df["outcome"].value_counts().to_dict()

            # Create split record
            split_repo.create_split(
                scenario_id=scenario_id,
                split_type=split_type,
                record_count=len(split_df),
                feature_count=len(split_df.columns),
                class_distribution={str(k): v for k, v in class_dist.items()},
                group_distribution={},
                file_path=str(file_path.relative_to(paths.DATA_DIR)),
                file_size_bytes=file_size,
                file_format=file_format,
                feature_names=list(split_df.columns),
                generation_duration_seconds=duration,
            )

            split_stats[split_type] = {
                "count": len(split_df),
                "file_size": file_size,
            }

        # Update scenario
        scenario_repo.update_one(
            scenario_id,
            {
                "status": MLScenarioStatus.COMPLETED.value,
                "train_count": len(result.train_indices),
                "val_count": len(result.val_indices),
                "test_count": len(result.test_indices),
                "splitting_completed_at": datetime.utcnow(),
            },
        )

        # Publish SSE event for UI update - COMPLETED
        publish_scenario_update(
            scenario_id=scenario_id,
            status=MLScenarioStatus.COMPLETED.value,
            builds_total=scenario.builds_total,
            builds_ingested=scenario.builds_ingested,
            builds_features_extracted=scenario.builds_features_extracted,
            builds_failed=scenario.builds_failed,
            train_count=len(result.train_indices),
            val_count=len(result.val_indices),
            test_count=len(result.test_indices),
            current_phase="Dataset generation completed",
        )

        logger.info(
            f"{corr_prefix} [split] Completed: train={len(result.train_indices)}, "
            f"val={len(result.val_indices)}, test={len(result.test_indices)}"
        )

        return {
            "status": "completed",
            "train_count": len(result.train_indices),
            "val_count": len(result.val_indices),
            "test_count": len(result.test_indices),
            "split_stats": split_stats,
            "metadata": result.metadata,
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"{corr_prefix} [split] Error: {error_msg}")
        scenario_repo.update_one(
            scenario_id,
            {
                "status": MLScenarioStatus.FAILED.value,
                "error_message": f"Splitting phase failed: {error_msg}",
            },
        )
        raise


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.ml_scenario_tasks.dispatch_scenario_scans",
    queue="scenario_scanning",
    soft_time_limit=300,
    time_limit=600,
)
def dispatch_scenario_scans(
    self: PipelineTask,
    scenario_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Dispatch scans for all unique commits in scenario's ingested builds.

    Fire-and-forget: runs parallel to feature extraction.
    Collects unique commits and dispatches in batches.
    """
    from app.config import settings

    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

    scenario_repo = MLScenarioRepository(self.db)
    import_build_repo = MLScenarioImportBuildRepository(self.db)
    raw_build_run_repo = RawBuildRunRepository(self.db)
    raw_repo_repo = RawRepositoryRepository(self.db)

    scenario = scenario_repo.find_by_id(scenario_id)
    if not scenario:
        return {"status": "error", "error": "Scenario not found"}

    # Get scan_metrics config from feature_config
    feature_config = scenario.feature_config
    if isinstance(feature_config, dict):
        scan_metrics_config = feature_config.get("scan_metrics", {})
    else:
        scan_metrics_config = feature_config.scan_metrics or {}

    has_sonar = bool(scan_metrics_config.get("sonarqube"))
    has_trivy = bool(scan_metrics_config.get("trivy"))

    if not has_sonar and not has_trivy:
        logger.info(f"{corr_prefix} [scans] No scan metrics configured, skipping")
        return {"status": "skipped", "reason": "No scan metrics configured"}

    # Collect unique commits to scan
    commits_to_scan: Dict[tuple, Dict[str, Any]] = {}
    repo_cache: Dict[str, Any] = {}

    # Get all ingested builds
    ingested_builds = import_build_repo.find_by_scenario(
        scenario_id=scenario_id,
        status=MLScenarioImportBuildStatus.INGESTED,
    )

    # Batch query raw_build_runs
    raw_build_run_ids = [
        b.raw_build_run_id for b in ingested_builds if b.raw_build_run_id
    ]
    raw_build_runs = raw_build_run_repo.find_by_ids(raw_build_run_ids)
    build_run_map = {str(r.id): r for r in raw_build_runs}

    for build in ingested_builds:
        raw_run = build_run_map.get(str(build.raw_build_run_id))
        if not raw_run or not raw_run.commit_sha:
            continue

        commit_key = (str(build.raw_repo_id), raw_run.commit_sha)
        if commit_key in commits_to_scan:
            continue

        # Get repo info
        if str(build.raw_repo_id) not in repo_cache:
            raw_repo = raw_repo_repo.find_by_id(str(build.raw_repo_id))
            if raw_repo:
                repo_cache[str(build.raw_repo_id)] = raw_repo

        raw_repo = repo_cache.get(str(build.raw_repo_id))
        if not raw_repo:
            continue

        commits_to_scan[commit_key] = {
            "raw_repo_id": str(build.raw_repo_id),
            "github_repo_id": raw_repo.github_id,
            "commit_sha": raw_run.commit_sha,
            "repo_full_name": raw_repo.full_name,
        }

    if not commits_to_scan:
        logger.info(f"{corr_prefix} [scans] No commits to scan")
        # Mark scans as completed if no scans needed
        scenario_repo.update_one(
            scenario_id,
            {
                "scans_total": 0,
                "scan_extraction_completed": True,
            },
        )
        return {"status": "skipped", "reason": "No commits found"}

    # Calculate scans_total: unique commits × enabled tools
    enabled_tools = (1 if has_sonar else 0) + (1 if has_trivy else 0)
    scans_total = len(commits_to_scan) * enabled_tools

    # Set scans_total BEFORE dispatching
    scenario_repo.set_scans_total(scenario_id, scans_total)

    # Split into batches
    commits_list = list(commits_to_scan.values())
    batch_size = getattr(settings, "SCAN_COMMITS_PER_BATCH", 20)
    batches = [
        commits_list[i : i + batch_size]
        for i in range(0, len(commits_list), batch_size)
    ]

    logger.info(
        f"{corr_prefix} [scans] Dispatching {len(commits_list)} commits in {len(batches)} batches, "
        f"scans_total={scans_total}"
    )

    # Chain batches sequentially
    from celery import chain

    batch_tasks = [
        process_scenario_scan_batch.s(
            scenario_id=scenario_id,
            commits_batch=batch,
            batch_index=i,
            total_batches=len(batches),
            scan_metrics_config=scan_metrics_config,
            correlation_id=correlation_id,
        )
        for i, batch in enumerate(batches)
    ]

    if batch_tasks:
        workflow = chain(
            *batch_tasks,
            finalize_scenario_scans.si(
                scenario_id=scenario_id,
                total_commits=len(commits_list),
                total_batches=len(batches),
                has_sonar=has_sonar,
                has_trivy=has_trivy,
                correlation_id=correlation_id,
            ),
        )
        workflow.apply_async()

    # Publish SSE event with scan progress
    publish_scenario_update(
        scenario_id=scenario_id,
        status=scenario.status if hasattr(scenario, "status") else "processing",
        scans_total=scans_total,
        scans_completed=0,
    )

    return {
        "status": "dispatched",
        "total_commits": len(commits_list),
        "total_batches": len(batches),
        "scans_total": scans_total,
        "has_sonar": has_sonar,
        "has_trivy": has_trivy,
    }


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.ml_scenario_tasks.process_scenario_scan_batch",
    queue="scenario_scanning",
    soft_time_limit=120,
    time_limit=180,
)
def process_scenario_scan_batch(
    self: PipelineTask,
    scenario_id: str,
    commits_batch: List[Dict[str, Any]],
    batch_index: int,
    total_batches: int,
    scan_metrics_config: Dict[str, List[str]],
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Process a single batch of scan dispatches.

    Dispatches scans for all commits in the batch.
    """
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

    logger.info(
        f"{corr_prefix} [scan_batch] Processing batch {batch_index + 1}/{total_batches} "
        f"with {len(commits_batch)} commits"
    )

    from app.tasks.ml_scenario_scan_helpers import dispatch_scan_for_scenario_commit

    dispatched = 0
    for commit_info in commits_batch:
        try:
            dispatch_scan_for_scenario_commit.delay(
                scenario_id=scenario_id,
                raw_repo_id=commit_info["raw_repo_id"],
                github_repo_id=commit_info["github_repo_id"],
                commit_sha=commit_info["commit_sha"],
                repo_full_name=commit_info["repo_full_name"],
                scan_metrics_config=scan_metrics_config,
            )
            dispatched += 1
        except Exception as e:
            logger.warning(
                f"{corr_prefix} [scan_batch] Failed to dispatch for {commit_info['commit_sha'][:8]}: {e}"
            )

    return {
        "status": "completed",
        "batch_index": batch_index,
        "dispatched": dispatched,
        "total_in_batch": len(commits_batch),
    }


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.ml_scenario_tasks.finalize_scenario_scans",
    queue="scenario_scanning",
    soft_time_limit=60,
    time_limit=120,
)
def finalize_scenario_scans(
    self: PipelineTask,
    scenario_id: str,
    total_commits: int,
    total_batches: int,
    has_sonar: bool,
    has_trivy: bool,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """
    Finalize scan dispatch after all batches complete.

    Logs completion (scan results are backfilled by scan tasks themselves).
    """
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

    logger.info(
        f"{corr_prefix} [scans] Completed scan dispatch for scenario {scenario_id[:8]}: "
        f"{total_commits} commits, {total_batches} batches, "
        f"sonar={has_sonar}, trivy={has_trivy}"
    )

    return {
        "status": "completed",
        "total_commits": total_commits,
        "total_batches": total_batches,
        "has_sonar": has_sonar,
        "has_trivy": has_trivy,
    }
