"""
Training Ingestion - Shared Utilities.

Common functions and failure handlers used across ingestion tasks.
"""

import logging
from typing import Any, Callable, Dict, List

from bson import ObjectId

from app.entities.training_scenario import ScenarioStatus, TrainingScenario
from app.repositories.raw_repository import RawRepositoryRepository
from app.repositories.training_scenario import TrainingScenarioRepository
from app.tasks.shared.events import publish_scenario_updated

logger = logging.getLogger(__name__)


def create_scenario_failure_handler(redis, scenario_id: str, db) -> Callable[[str, str], None]:
    """
    Create a failure handler for TrainingScenario orchestrator-level tasks.
    Updates status to FAILED and publishes SSE events.

    Args:
        redis: Redis connection (for compatibility)
        scenario_id: The training scenario ID
        db: MongoDB database connection

    Returns:
        Handler function with signature (status: str, error_message: str) -> None
    """

    def handler(status: str, error_message: str) -> None:
        try:
            scenario_repo = TrainingScenarioRepository(db)
            scenario = scenario_repo.find_one_and_update(
                {"_id": ObjectId(scenario_id)},
                {
                    "$set": {
                        "status": ScenarioStatus.FAILED.value,
                        "error_message": error_message,
                    }
                },
                return_updated=True,
            )
            if scenario:
                publish_scenario_updated(scenario, error=error_message)
        except Exception as e:
            logger.warning(f"Failed to update scenario {scenario_id}: {e}")

    return handler


def create_training_ingestion_build_failure_handler(
    db, build_id: str
) -> Callable[[str, str], None]:
    """
    Create a failure handler for TrainingIngestionBuild build-level tasks.
    Updates build status to FAILED when ingestion fails.

    Args:
        db: MongoDB database connection
        build_id: The training ingestion build ID

    Returns:
        Handler function with signature (status: str, error_message: str) -> None
    """
    from app.entities.training_ingestion_build import IngestionStatus
    from app.repositories.training_ingestion_build import TrainingIngestionBuildRepository

    def handler(status: str, error_message: str) -> None:
        try:
            repo = TrainingIngestionBuildRepository(db)
            repo.update_one(
                build_id,
                {
                    "status": IngestionStatus.FAILED.value,
                    "ingestion_error": error_message[:500],
                },
            )
            logger.info(
                f"Marked TrainingIngestionBuild {build_id[:8]} as FAILED: " f"{error_message[:100]}"
            )
        except Exception as e:
            logger.warning(f"Failed to mark TrainingIngestionBuild {build_id[:8]} as FAILED: {e}")

    return handler


def resolve_filter_config(scenario: TrainingScenario) -> Dict[str, Any]:
    """Helper to resolve configuration dictionary from scenario."""
    data_config = scenario.data_source_config
    if isinstance(data_config, dict):
        config_dict = data_config
    else:
        config_dict = (
            data_config.model_dump() if hasattr(data_config, "model_dump") else data_config.__dict__
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


def find_matching_repos(db, languages: List[str], build_source_ids: List[str]) -> List[Any]:
    """Find repositories matching language and source criteria."""
    raw_repo_repo = RawRepositoryRepository(db)
    repo_query: Dict[str, Any] = {"is_private": {"$ne": True}}

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
        regex_list = [re.compile(f"^{re.escape(lang)}$", re.IGNORECASE) for lang in languages]
        repo_query["main_lang"] = {"$in": regex_list}

    return list(raw_repo_repo.find_many(repo_query))
