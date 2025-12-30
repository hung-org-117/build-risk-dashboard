"""
Feature metadata decorators for Hamilton DAG.
"""

from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar

F = TypeVar("F", bound=Callable)


class FeatureCategory(str, Enum):
    """Categories for features."""

    BUILD_LOG = "build_log"
    GIT_HISTORY = "git_history"
    GIT_DIFF = "git_diff"
    REPO_SNAPSHOT = "repo_snapshot"
    PR_INFO = "pr_info"
    DISCUSSION = "discussion"
    TEAM = "team"
    METADATA = "metadata"
    WORKFLOW = "workflow"
    # New categories from Circle CI research
    DEVOPS = "devops"  # DevOps file detection and analysis
    BUILD_HISTORY = "build_history"  # Link to previous build features
    COMMITTER = "committer"  # Committer experience features
    COOPERATION = "cooperation"  # Cooperation features (distinct authors, revisions)


class FeatureDataType(str, Enum):
    """Data types for features."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    LIST_STRING = "list_string"
    LIST_INTEGER = "list_integer"
    JSON = "json"


class OutputFormat(str, Enum):
    """Output format for list features when saving to DB."""

    RAW = "raw"
    COMMA_SEPARATED = "comma"  # "a,b,c"
    HASH_SEPARATED = "hash"  # "a#b#c"
    PIPE_SEPARATED = "pipe"  # "a|b|c"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def build_metadata_registry(modules: list) -> Dict[str, Dict[str, Any]]:
    """
    Build a registry of all feature metadata.

    NOTE: This function now uses FEATURE_REGISTRY as the source of truth,
    ignoring the modules parameter (kept for backwards compatibility).

    Args:
        modules: List of Hamilton feature modules (ignored, kept for compatibility)

    Returns:
        Dictionary mapping feature names to their metadata
    """
    from app.tasks.pipeline.feature_dag._feature_definitions import FEATURE_REGISTRY

    registry = {}
    for name, defn in FEATURE_REGISTRY.items():
        registry[name] = {
            "display_name": defn.display_name,
            "description": defn.description,
            "category": defn.category.value,
            "data_type": defn.data_type.value,
            "required_resources": [r.value for r in defn.required_resources],
            "nullable": defn.nullable,
            "example_value": defn.example_value,
            "unit": defn.unit,
            "output_format": defn.output_format.value if defn.output_format else None,
            "valid_range": defn.valid_range,
            "valid_values": defn.valid_values,
        }
    return registry


def get_required_resources_for_features(
    feature_names: Set[str],
    modules: Optional[list] = None,
) -> Set[str]:
    """
    Get all required resources for a set of features.

    This is useful for optimizing resource loading - only prepare resources
    that are actually needed by the requested features.

    Args:
        feature_names: Set of feature names to check
        modules: Optional list of Hamilton modules. If not provided,
                 lazy-loads HAMILTON_MODULES from constants to avoid
                 circular imports.

    Returns:
        Set of resource names required (e.g., {"git_history", "github_api"})
    """
    # Lazy load to avoid circular import
    if modules is None:
        from app.tasks.pipeline.constants import HAMILTON_MODULES

        modules = HAMILTON_MODULES

    registry = build_metadata_registry(modules)
    resources: Set[str] = set()

    # Include default features that are always extracted
    # Lazy load DEFAULT_FEATURES to avoid circular import
    from app.tasks.pipeline.constants import DEFAULT_FEATURES

    features = feature_names | DEFAULT_FEATURES

    for name in features:
        if name in registry:
            feature_resources = registry[name].get("required_resources", [])
            resources.update(feature_resources)

    return resources


def _is_serializable(value: Any) -> bool:
    """
    Check if a value is JSON-serializable for MongoDB storage.

    Returns False for custom dataclass objects that cannot be encoded.
    """
    from dataclasses import is_dataclass
    from pathlib import Path

    if value is None:
        return True
    if isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, (list, tuple)):
        return all(_is_serializable(v) for v in value)
    if isinstance(value, dict):
        return all(_is_serializable(v) for v in value.values())
    # Path objects are not serializable
    if isinstance(value, Path):
        return False
    # Dataclass instances (like GitHistoryInput, GitWorktreeInput) are not serializable
    if is_dataclass(value) and not isinstance(value, type):
        return False
    # Objects with custom types are likely not serializable
    if hasattr(value, "__dict__") and not isinstance(value, (type, type(None))):
        return False
    return True


def format_features_for_storage(
    features: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Format feature values for MongoDB storage.

    Filters out:
    - Input resource names (git_history, git_worktree, etc.)
    - Non-serializable objects (custom dataclasses, Path objects)

    Uses FEATURE_REGISTRY for output_format metadata.

    Args:
        features: Dictionary of extracted features
    Returns:
        Dictionary with formatted values ready for DB storage
    """
    from app.tasks.pipeline.feature_dag._feature_definitions import FEATURE_REGISTRY
    from app.tasks.pipeline.shared.resources import get_input_resource_names

    input_resource_names = get_input_resource_names()
    result = {}

    for name, value in features.items():
        # Skip input resources - these are not actual features
        if name in input_resource_names:
            continue

        # Skip non-serializable values (custom objects, Path, etc.)
        if not _is_serializable(value):
            continue

        # Get output format from FEATURE_REGISTRY (single source of truth)
        defn = FEATURE_REGISTRY.get(name)
        output_format = defn.output_format if defn and defn.output_format else OutputFormat.RAW

        if value is None:
            result[name] = None
        elif isinstance(value, list):
            if not value:
                result[name] = ""
            elif output_format == OutputFormat.HASH_SEPARATED:
                result[name] = "#".join(str(v) for v in value)
            elif output_format == OutputFormat.COMMA_SEPARATED:
                result[name] = ",".join(str(v) for v in value)
            elif output_format == OutputFormat.PIPE_SEPARATED:
                result[name] = "|".join(str(v) for v in value)
            else:
                # RAW - keep as list
                result[name] = value
        else:
            result[name] = value

    return result


# =============================================================================
# Config Requirements Decorator
# =============================================================================

# Global registry to store config requirements
_CONFIG_REQUIREMENTS: Dict[str, List[Dict[str, Any]]] = {}


def requires_config(**field_specs: Dict[str, Any]) -> Callable[[F], F]:
    """
    Decorator to mark features that need user config input.

    This allows features to declaratively specify their configuration
    requirements instead of relying on a static RepoConfigInput class.

    Config Scopes:
        - "global": Applied to all builds in dataset/repo (e.g., lookback_days)
        - "repo": Applied per-repository (e.g., source_languages, test_frameworks)

    Example:
        @requires_config(
            lookback_days={
                "type": "integer",
                "scope": "global",
                "required": False,
                "description": "Days to look back for commit history",
                "default": 90
            },
            source_languages={
                "type": "list",
                "scope": "repo",
                "required": True,
                "description": "Main programming languages",
                "default": []
            }
        )
        @tag(group="git")
        def my_feature(feature_config: FeatureConfigInput, ...):
            lookback = feature_config.get("lookback_days", 90, scope="global")
            languages = feature_config.get("source_languages", [], scope="repo")

    Args:
        **field_specs: Keyword arguments where key is field name and value
                      is a dict with keys: type, scope, required, description, default

    Returns:
        Decorator function that attaches config requirements to the function
    """

    def decorator(func: F) -> F:
        func_name = func.__name__
        _CONFIG_REQUIREMENTS[func_name] = []

        for field_name, spec in field_specs.items():
            _CONFIG_REQUIREMENTS[func_name].append(
                {
                    "field": field_name,
                    "type": spec.get("type", "string"),
                    "scope": spec.get("scope", "repo"),  # Default to repo scope
                    "required": spec.get("required", True),
                    "description": spec.get("description", ""),
                    "default": spec.get("default"),
                }
            )

        # Add metadata to function itself for introspection
        func._config_requirements = _CONFIG_REQUIREMENTS[func_name]

        return func

    return decorator


def collect_config_requirements(
    feature_names: List[str],
    modules: Optional[list] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Scan selected features and collect all required config fields.

    Args:
        feature_names: List of feature names user has selected
        modules: Optional list of Hamilton modules. If not provided,
                lazy-loads HAMILTON_MODULES from constants.

    Returns:
        Dict mapping field names to their specifications.
        Example:
        {
            "source_languages": {
                "field": "source_languages",
                "type": "list",
                "required": True,
                "description": "Main programming languages",
                "default": []
            }
        }
    """
    # Lazy load to avoid circular import
    if modules is None:
        from app.tasks.pipeline.constants import HAMILTON_MODULES

        modules = HAMILTON_MODULES

    all_fields: Dict[str, Dict[str, Any]] = {}

    for module in modules:
        for name in dir(module):
            if name.startswith("_"):
                continue

            obj = getattr(module, name)

            # Skip non-callable items
            if not callable(obj):
                continue

            # Check if this function is in the selected features
            # OR if it has @extract_fields and any of its fields are selected
            is_selected = name in feature_names

            # Also check @extract_fields
            if not is_selected:
                transforms = getattr(obj, "transform", [])
                for t in transforms:
                    if hasattr(t, "fields") and isinstance(t.fields, dict):
                        for field_name in t.fields.keys():
                            if field_name in feature_names:
                                is_selected = True
                                break
                    if is_selected:
                        break

            # If this feature is selected and has config requirements
            if is_selected and hasattr(obj, "_config_requirements"):
                for req in obj._config_requirements:
                    field_name = req["field"]
                    if field_name in all_fields:
                        # Merge requirements (e.g., if one requires and another doesn't)
                        all_fields[field_name]["required"] = (
                            all_fields[field_name]["required"] or req["required"]
                        )
                    else:
                        all_fields[field_name] = req.copy()

    return all_fields
