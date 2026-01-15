from app.tasks.pipeline.feature_dag.extractors import (
    build,
    ci,
    code,
    collaboration,
    repository,
    temporal,
)

DEFAULT_FEATURES = {
    # Core identification
    "build_id",
    "repo_full_name",
    "build_ci_provider",
    # Label (outcome): 0=passed, 1=failed
    "build_status_num",
    # Grouping features for splitting
    "repo_language",
    "build_hour",
    "percentage_of_builds_before",
    "number_of_builds_before",
    "build_started_at",
}


def get_default_features() -> list[str]:
    """Get DEFAULT_FEATURES as sorted list for API responses."""
    return sorted(DEFAULT_FEATURES)


HAMILTON_MODULES = [
    build,
    ci,
    code,
    collaboration,
    repository,
    temporal,
]


def get_input_resource_names() -> frozenset:
    """
    Get all input resource names that should NOT be stored as features.

    These are Hamilton DAG inputs, not actual feature values.
    Derived from INPUT_REGISTRY for single source of truth.
    """
    from app.tasks.pipeline.shared.resources import (
        get_input_resource_names as _get_names,
    )

    return _get_names()
