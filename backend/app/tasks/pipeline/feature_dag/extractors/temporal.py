"""
Build history and committer experience features.

Features extracted from historical build data:
- Build history: prev_built_result, same_committer, time_since_prev_build
- Committer experience: committer_fail_history, committer_recent_fail_history, committer_avg_exp
- Project history: project_fail_history, project_fail_recent
- Time features: day_week, time_of_day
"""

import logging
from datetime import timezone
from typing import Any, Dict, List, Optional

from hamilton.function_modifiers import extract_fields, tag

from app.tasks.pipeline.feature_dag._inputs import (
    BuildRunInput,
    RawBuildRunsCollection,
    RepoInput,
)
from app.tasks.pipeline.feature_dag._similarity import compute_similarity

logger = logging.getLogger(__name__)

# Threshold for considering two authors as the same person
AUTHOR_SIMILARITY_THRESHOLD = 0.9

# Number of recent builds for "recent" metrics
RECENT_BUILDS_COUNT = 5

# Performance limit for MongoDB queries
MAX_BUILDS_HISTORY = 500


# =============================================================================
# Time Features - REMOVED: moved to build.py as build_day_of_week and build_hour
# =============================================================================


# =============================================================================
# Build History Features (Link to Last Build)
# =============================================================================


@extract_fields(
    {
        "history_prev_result": Optional[str],
        "history_same_committer": Optional[bool],
        "history_days_since_prev": Optional[float],
    }
)
@tag(group="history")
def build_history_features(
    raw_build_runs: RawBuildRunsCollection,
    build_run: BuildRunInput,
    repo: RepoInput,
) -> Dict[str, Any]:
    """
    Extract features related to previous build.

    - history_prev_result: Outcome of the previous build ('passed', 'failed', etc.)
    - history_same_committer: Whether committer is same as previous build
    - history_days_since_prev: Days since previous build completed
    """
    from bson import ObjectId

    result = {
        "history_prev_result": None,
        "history_same_committer": None,
        "history_days_since_prev": None,
    }

    if not build_run.created_at:
        return result

    # Find previous build
    try:
        prev_build = raw_build_runs.find_one(
            {
                "raw_repo_id": ObjectId(repo.id),
                "created_at": {"$lt": build_run.created_at},
            },
            sort=[("created_at", -1)],
        )

        if not prev_build:
            # This is the first build
            return result

        # history_prev_result
        prev_conclusion = prev_build.get("conclusion")
        if prev_conclusion:
            if hasattr(prev_conclusion, "value"):
                prev_conclusion = prev_conclusion.value
            result["history_prev_result"] = str(prev_conclusion)

        # history_same_committer - compare author names
        current_author = _get_build_author(build_run)
        prev_author = _get_author_from_raw(prev_build)

        if current_author and prev_author:
            similarity = compute_similarity(current_author, prev_author)
            result["history_same_committer"] = similarity > AUTHOR_SIMILARITY_THRESHOLD

        # history_days_since_prev
        prev_completed = prev_build.get("completed_at") or prev_build.get("created_at")
        if prev_completed and build_run.created_at:
            delta = build_run.created_at - prev_completed
            result["history_days_since_prev"] = delta.total_seconds() / 86400  # days

    except Exception as e:
        logger.warning(f"Failed to get build history: {e}")

    return result


def _get_build_author(build_run: BuildRunInput) -> Optional[str]:
    """
    Extract author name from build run.

    Uses the normalized commit_author field from BuildRunInput.
    """
    return build_run.commit_author


def _get_author_from_raw(raw_build: dict) -> Optional[str]:
    """
    Extract author from raw build document.

    Uses the normalized commit_author field stored in MongoDB.
    """
    return raw_build.get("commit_author")


@extract_fields(
    {
        "author_fail_rate": Optional[float],
        "author_fail_rate_recent": Optional[float],
    }
)
@tag(group="author")
def author_fail_history_features(
    raw_build_runs: RawBuildRunsCollection,
    build_run: BuildRunInput,
    repo: RepoInput,
) -> Dict[str, Any]:
    """
    Calculate committer's historical fail rates.

    - author_fail_rate: Overall fail rate of this committer
    - author_fail_rate_recent: Fail rate in last N builds by this committer
    """
    from bson import ObjectId

    result = {
        "author_fail_rate": None,
        "author_fail_rate_recent": None,
    }

    current_author = _get_build_author(build_run)
    if not current_author or not build_run.created_at:
        return result

    try:
        # Get previous builds for this repo (limited for performance)
        prev_builds = list(
            raw_build_runs.find(
                {
                    "raw_repo_id": ObjectId(repo.id),
                    "created_at": {"$lte": build_run.created_at},
                    "ci_run_id": {"$ne": build_run.ci_run_id},
                }
            )
            .sort("created_at", -1)
            .limit(MAX_BUILDS_HISTORY)
        )

        if not prev_builds:
            return result

        # Filter to builds by this author (using similarity)
        author_builds: List[dict] = []
        for b in prev_builds:
            build_author = _get_author_from_raw(b)
            if (
                build_author
                and compute_similarity(current_author, build_author)
                > AUTHOR_SIMILARITY_THRESHOLD
            ):
                author_builds.append(b)

        if not author_builds:
            return result

        # Calculate overall fail history
        total = len(author_builds)
        failed = sum(1 for b in author_builds if _is_failed(b))
        result["author_fail_rate"] = round(failed / total, 2) if total > 0 else None

        # Calculate recent fail history (last N builds)
        recent_builds = author_builds[:RECENT_BUILDS_COUNT]
        recent_total = len(recent_builds)
        recent_failed = sum(1 for b in recent_builds if _is_failed(b))
        result["author_fail_rate_recent"] = (
            round(recent_failed / recent_total, 2) if recent_total > 0 else None
        )

    except Exception as e:
        logger.warning(f"Failed to calculate committer fail history: {e}")

    return result


@tag(group="author")
def author_experience(
    raw_build_runs: RawBuildRunsCollection,
    build_run: BuildRunInput,
    repo: RepoInput,
) -> Optional[float]:
    """
    Calculate average experience of committers in the project.

    Experience = total builds before current / number of unique committers
    """
    from bson import ObjectId

    if not build_run.created_at:
        return None

    try:
        # Get previous builds (limited for performance)
        prev_builds = list(
            raw_build_runs.find(
                {
                    "raw_repo_id": ObjectId(repo.id),
                    "created_at": {"$lt": build_run.created_at},
                }
            ).limit(MAX_BUILDS_HISTORY)
        )

        if not prev_builds:
            return None

        # Count unique committers (using similarity grouping)
        unique_authors: List[str] = []
        for b in prev_builds:
            author = _get_author_from_raw(b)
            if not author:
                continue

            # Check if already counted (using similarity)
            is_new = True
            for existing in unique_authors:
                if compute_similarity(author, existing) > AUTHOR_SIMILARITY_THRESHOLD:
                    is_new = False
                    break

            if is_new:
                unique_authors.append(author)

        num_committers = len(unique_authors)
        if num_committers == 0:
            return None

        return round(len(prev_builds) / num_committers, 2)

    except Exception as e:
        logger.warning(f"Failed to calculate committer avg exp: {e}")
        return None


# =============================================================================
# Project History Features
# =============================================================================


@extract_fields(
    {
        "history_project_fail_rate": Optional[float],
        "history_project_fail_recent": Optional[float],
    }
)
@tag(group="project")
def project_fail_history_features(
    raw_build_runs: RawBuildRunsCollection,
    build_run: BuildRunInput,
    repo: RepoInput,
) -> Dict[str, Any]:
    """
    Calculate project's historical fail rates.

    - project_fail_history: Overall fail rate of the project
    - project_fail_recent: Fail rate in last N builds
    """
    from bson import ObjectId

    result = {
        "history_project_fail_rate": None,
        "history_project_fail_recent": None,
    }

    if not build_run.created_at:
        return result

    try:
        # Get previous builds (limited for performance)
        prev_builds = list(
            raw_build_runs.find(
                {
                    "raw_repo_id": ObjectId(repo.id),
                    "created_at": {"$lt": build_run.created_at},
                    "conclusion": {"$in": ["success", "failure"]},
                }
            )
            .sort("created_at", -1)
            .limit(MAX_BUILDS_HISTORY)
        )

        if not prev_builds:
            return result

        # Overall project fail history
        total = len(prev_builds)
        failed = sum(1 for b in prev_builds if _is_failed(b))
        result["history_project_fail_rate"] = (
            round(failed / total, 2) if total > 0 else None
        )

        # Recent project fail history (last N builds)
        recent_builds = prev_builds[:RECENT_BUILDS_COUNT]
        recent_total = len(recent_builds)
        recent_failed = sum(1 for b in recent_builds if _is_failed(b))
        result["history_project_fail_recent"] = (
            round(recent_failed / recent_total, 2) if recent_total > 0 else None
        )

    except Exception as e:
        logger.warning(f"Failed to calculate project fail history: {e}")

    return result


def _is_failed(build: dict) -> bool:
    """Check if a build failed."""
    conclusion = build.get("conclusion")
    if not conclusion:
        return False

    if hasattr(conclusion, "value"):
        conclusion = conclusion.value

    return str(conclusion).lower() in ("failure", "failed")
