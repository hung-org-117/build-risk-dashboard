"""
Script to visualize Hamilton DAG as a PNG image.

Usage:
    cd backend
    python visualize_dag.py
"""

from pathlib import Path

from hamilton import driver

from app.tasks.pipeline.constants import HAMILTON_MODULES

# Features used in Risk Model (from app/services/risk_model/inference.py)
# Temporal features (used in LSTM sequence - build history patterns)
TEMPORAL_FEATURES = [
    "history_prev_failed",
    "history_fail_streak",
    "history_fail_rate_10",
    "history_avg_churn_5",
    "history_days_since_prev",
]

# Static features (point-in-time values for current build)
STATIC_FEATURES = [
    # Code churn features
    "git_diff_src_churn",
    "git_diff_files_added",
    "git_diff_files_deleted",
    "git_diff_files_modified",
    "git_diff_tests_added",
    "git_diff_tests_deleted",
    "git_diff_src_files",
    "git_diff_doc_files",
    "git_diff_other_files",
    "git_file_commit_density",
    "git_files_modified_ratio",
    "git_change_entropy",
    "git_churn_vs_avg",
    # Repository metrics
    "repo_sloc",
    "repo_age_days",
    "repo_total_commits",
    "repo_test_lines_per_kloc",
    "repo_test_cases_per_kloc",
    "repo_asserts_per_kloc",
    # Team features
    "team_size",
    "author_ownership",
    "author_is_new",
    "author_days_since_commit",
    # Test metrics from build logs
    "log_jobs_count",
    "log_tests_run",
    "log_tests_failed",
    "log_tests_skipped",
    "log_tests_passed",
    "log_test_duration_sec",
    "log_tests_fail_rate",
    "build_duration_sec",
    "build_status_num",
    # Time features
    "build_hour_sin",
    "build_hour_cos",
    "build_hour_risk",
]

# Combined model features
MODEL_FEATURES = TEMPORAL_FEATURES + STATIC_FEATURES


def visualize_hamilton_dag(output_path: str = "dag_visualization.png") -> None:
    """
    Generate a PNG visualization of the Hamilton DAG.

    Args:
        output_path: Path for the output PNG file
    """
    # Build the Hamilton driver with all feature modules
    dr = driver.Builder().with_modules(*HAMILTON_MODULES).build()

    # Generate the visualization
    # display_all_functions creates a DAG visualization of all nodes
    dr.display_all_functions(
        output_file_path=output_path,
        render_kwargs={"format": "png"},
        orient="TB",  # Top-to-Bottom orientation
    )
    print(f"DAG visualization saved to: {output_path}")


def visualize_specific_features(
    features: list[str],
    output_path: str = "dag_features.png",
    orient: str = "LR",  # LR = Left-to-Right (better for slides)
    for_slides: bool = False,
) -> None:
    """
    Generate visualization showing only specific features and their dependencies.

    Args:
        features: List of feature names to visualize
        output_path: Path for the output PNG file
        orient: Graph orientation - 'LR' (horizontal) or 'TB' (vertical)
        for_slides: If True, optimize for presentation slides
    """
    dr = driver.Builder().with_modules(*HAMILTON_MODULES).build()

    # Graphviz render options for better slide presentation
    # For slides, use SVG for vector quality; otherwise PNG
    fmt = "svg" if for_slides else "png"
    output = output_path.replace(".png", f".{fmt}") if for_slides else output_path

    dr.visualize_execution(
        final_vars=features,
        output_file_path=output,
        render_kwargs={"format": fmt},
        inputs={},
        bypass_validation=True,
        orient=orient,
    )
    print(f"Feature-specific DAG saved to: {output}")


if __name__ == "__main__":
    output_dir = Path("artifacts")
    output_dir.mkdir(exist_ok=True)

    # Visualize the complete DAG
    print("Generating complete DAG visualization...")
    visualize_hamilton_dag(str(output_dir / "hamilton_dag_complete.png"))

    # Visualize only MODEL_FEATURES used in risk model
    print(f"\nGenerating MODEL-only DAG ({len(MODEL_FEATURES)} features)...")
    visualize_specific_features(
        MODEL_FEATURES,
        str(output_dir / "hamilton_dag_model_features.png"),
    )

    # Slide-optimized version (horizontal, higher quality)
    print(f"\nGenerating SLIDE-optimized DAG...")
    visualize_specific_features(
        MODEL_FEATURES,
        str(output_dir / "hamilton_dag_for_slides.png"),
        orient="LR",  # Left-to-Right for horizontal layout
        for_slides=True,
    )

    # Tạo thêm phiên bản group theo category
    print(f"\nGenerating category-specific DAGs for slides...")

    # Temporal features only
    visualize_specific_features(
        TEMPORAL_FEATURES,
        str(output_dir / "dag_temporal_features.png"),
        orient="LR",
        for_slides=True,
    )
    print(f"  - Temporal features ({len(TEMPORAL_FEATURES)})")

    # Code churn features
    CODE_FEATURES = [f for f in STATIC_FEATURES if f.startswith("git_")]
    visualize_specific_features(
        CODE_FEATURES,
        str(output_dir / "dag_code_features.png"),
        orient="LR",
        for_slides=True,
    )
    print(f"  - Code features ({len(CODE_FEATURES)})")

    # Repository features
    REPO_FEATURES = [f for f in STATIC_FEATURES if f.startswith("repo_")]
    visualize_specific_features(
        REPO_FEATURES,
        str(output_dir / "dag_repo_features.png"),
        orient="LR",
        for_slides=True,
    )
    print(f"  - Repo features ({len(REPO_FEATURES)})")

    print("\nDone! All DAG visualizations saved to artifacts/")
