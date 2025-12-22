"""
Pipeline Input Preparer - Build inputs, check resources, filter features.

This module acts as the preparation layer before Hamilton execution:
1. Build all input objects from entities
2. Check which resources are available
3. Filter features based on available resources
4. Return a PreparedPipelineInput ready for execution

Usage:
    prepared = prepare_pipeline_input(
        raw_repo=raw_repo,
        feature_config=feature_config,
        raw_build_run=raw_build_run,
        selected_features=["feature1", "feature2"],
    )

    # Then pass to HamiltonPipeline.execute()
    result = pipeline.execute(prepared)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from app.entities.raw_build_run import RawBuildRun
from app.entities.raw_repository import RawRepository
from app.paths import LOGS_DIR, get_repo_path, get_worktrees_path
from app.tasks.pipeline.constants import DEFAULT_FEATURES
from app.tasks.pipeline.feature_dag._inputs import (
    GitHubClientInput,
    HamiltonInputs,
    build_hamilton_inputs,
)
from app.tasks.pipeline.feature_dag._metadata import (
    build_metadata_registry,
    get_required_resources_for_features,
)
from app.tasks.pipeline.shared.resources import (
    check_resource_availability,
    get_input_resource_names,
)

logger = logging.getLogger(__name__)


@dataclass
class PreparedPipelineInput:
    """
    Prepared input for Hamilton pipeline execution.

    Contains all inputs, validated features, and resource status.
    """

    # Hamilton inputs
    inputs: HamiltonInputs

    # Features to extract (already filtered by resources)
    features_to_extract: Set[str]

    # Tracking info
    skipped_features: Set[str] = field(default_factory=set)
    missing_resources: Set[str] = field(default_factory=set)
    available_resources: Set[str] = field(default_factory=set)

    # Commit availability (for logging/tracking)
    is_commit_available: bool = False

    # Optional GitHub client (kept separate as it's not in HamiltonInputs)
    github_client: Optional[GitHubClientInput] = None

    @property
    def has_features(self) -> bool:
        """Check if there are any features to extract."""
        return len(self.features_to_extract) > 0


def _get_all_feature_names() -> Set[str]:
    """Get all available feature names from metadata registry."""
    from app.tasks.pipeline.constants import HAMILTON_MODULES

    registry = build_metadata_registry(HAMILTON_MODULES)
    return set(registry.keys())


def _filter_features_by_resources(
    features: Set[str],
    available_resources: Set[str],
) -> tuple[Set[str], Set[str]]:
    """
    Filter features based on available resources.

    Args:
        features: Set of feature names to filter
        available_resources: Set of available resource values

    Returns:
        Tuple of (valid_features, skipped_features)
    """
    valid = set()
    skipped = set()

    for feature in features:
        required = get_required_resources_for_features({feature})
        if required <= available_resources:
            valid.add(feature)
        else:
            missing = required - available_resources
            logger.debug(f"Feature {feature} requires missing resources: {missing}")
            skipped.add(feature)

    return valid, skipped


def prepare_pipeline_input(
    raw_repo: RawRepository,
    feature_config: Dict[str, Any],
    raw_build_run: RawBuildRun,
    selected_features: Optional[List[str]] = None,
    github_client: Optional[GitHubClientInput] = None,
) -> PreparedPipelineInput:
    """
    Prepare all inputs for Hamilton pipeline execution.

    This function:
    1. Builds all input objects from entities (git, repo, build, logs)
    2. Checks which resources are available
    3. Filters requested features based on available resources
    4. Returns a PreparedPipelineInput ready for execution

    Args:
        raw_repo: RawRepository entity
        feature_config: Feature configuration dict
        raw_build_run: RawBuildRun entity
        selected_features: Optional list of features to extract (None = all)
        github_client: Optional GitHub client for API features

    Returns:
        PreparedPipelineInput with validated inputs and features
    """
    # Build paths using github_repo_id (stable across renames)
    repo_path = get_repo_path(raw_repo.github_repo_id)
    worktrees_base = get_worktrees_path(raw_repo.github_repo_id)

    # Build all Hamilton inputs
    inputs = build_hamilton_inputs(
        raw_repo=raw_repo,
        feature_config=feature_config,
        build_run=raw_build_run,
        repo_path=repo_path,
        worktrees_base=worktrees_base,
        logs_base=LOGS_DIR,
    )

    # Build inputs dict for resource checking
    inputs_dict: Dict[str, Any] = {
        "git_history": inputs.git_history,
        "git_worktree": inputs.git_worktree,
        "repo": inputs.repo,
        "build_run": inputs.build_run,
        "feature_config": inputs.feature_config,
        "build_logs": inputs.build_logs,
    }

    if github_client:
        inputs_dict["github_client"] = github_client

    # Check which resources are available
    available_resources = check_resource_availability(inputs_dict)

    # Get all available features
    all_features = _get_all_feature_names()

    # Determine requested features
    if selected_features:
        requested_features = (set(selected_features) | DEFAULT_FEATURES) & all_features
    else:
        requested_features = all_features.copy()

    # Filter features based on available resources
    valid_features, skipped_features = _filter_features_by_resources(
        requested_features, available_resources
    )

    # Calculate missing resources
    all_required = get_required_resources_for_features(requested_features)
    missing_resources = all_required - available_resources

    # Filter out input resource names (these are inputs, not features)
    input_names = get_input_resource_names()
    features_to_extract = valid_features - input_names

    # Log warnings
    if skipped_features:
        logger.warning(
            f"Skipping {len(skipped_features)} features due to missing resources: "
            f"{sorted(skipped_features)[:5]}{'...' if len(skipped_features) > 5 else ''}"
        )
        logger.warning(f"Missing resources: {sorted(missing_resources)}")

    if not features_to_extract:
        logger.warning("No features to extract after resource validation")

    return PreparedPipelineInput(
        inputs=inputs,
        features_to_extract=features_to_extract,
        skipped_features=skipped_features,
        missing_resources=missing_resources,
        available_resources=available_resources,
        is_commit_available=inputs.is_commit_available,
        github_client=github_client,
    )
