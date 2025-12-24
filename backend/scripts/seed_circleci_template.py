"""
Seed script for Circle CI DevOps dataset template.

Creates a template with features from the Circle CI research (Replication-Package-2).
Run with: python -m scripts.seed_circleci_template

Includes both existing features and new DevOps/history features.
"""

import logging

from app.database.mongo import get_database
from app.tasks.pipeline.constants import DEFAULT_FEATURES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# NEW: DevOps Features (from Circle CI research)
# =============================================================================
FEATURES_DEVOPS = {
    "num_of_devops_files",
    "devops_change_size",
    "devops_tools_used",
}

# =============================================================================
# NEW: Build History Features (from Circle CI research)
# =============================================================================
FEATURES_BUILD_HISTORY = {
    # Time features
    "day_week",
    "time_of_day",
    # Link to last build
    "prev_built_result",
    "same_committer",
    "elapsed_days_last_build",
    # Project history
    "project_fail_history",
    "project_fail_recent",
}

# NEW: Committer Experience Features (from Circle CI research)
FEATURES_COMMITTER = {
    "committer_fail_history",
    "committer_recent_fail_history",
    "committer_avg_exp",
}

# NEW: Cooperation Features (from Circle CI research)
FEATURES_COOPERATION = {
    "num_of_distinct_authors",
    "total_number_of_revisions",
}

# All features combined
ALL_FEATURES = (
    FEATURES_DEVOPS | FEATURES_BUILD_HISTORY | FEATURES_COMMITTER | FEATURES_COOPERATION
)


def seed_circleci_template():
    """Create or update the Circle CI DevOps dataset template."""
    db = get_database()

    # Exclude default features from the selectable list
    selected_features = sorted(ALL_FEATURES - DEFAULT_FEATURES)

    logger.info(f"Total features available: {len(ALL_FEATURES)}")
    logger.info(f"Selectable features (excluding defaults): {len(selected_features)}")

    # Template document
    template = {
        "name": "Circle CI DevOps",
        "description": (
            "Feature set based on Circle CI research (Replication-Package-2). "
            "Includes DevOps file detection, build history, and committer experience features."
        ),
        "feature_names": selected_features,
        "tags": ["circleci", "devops", "build-prediction", "committer-experience"],
        "source": "seed",
    }

    # Upsert by name
    result = db.dataset_templates.update_one(
        {"name": template["name"]},
        {"$set": template},
        upsert=True,
    )

    if result.upserted_id:
        logger.info(f"✅ Created new template: {template['name']}")
    else:
        logger.info(f"✅ Updated existing template: {template['name']}")

    logger.info(f"   Features included: {len(selected_features)}")

    # Print feature categories for verification
    logger.info("   Feature breakdown by group:")
    logger.info(f"      devops (NEW): {len(FEATURES_DEVOPS)} features")
    logger.info(f"      build_history (NEW): {len(FEATURES_BUILD_HISTORY)} features")
    logger.info(f"      committer (NEW): {len(FEATURES_COMMITTER)} features")
    logger.info(f"      cooperation (NEW): {len(FEATURES_COOPERATION)} features")


if __name__ == "__main__":
    seed_circleci_template()
