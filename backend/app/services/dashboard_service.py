from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from pymongo.database import Database

from app.dtos import DashboardMetrics, DashboardSummaryResponse, RepoDistributionEntry
from app.dtos.dashboard import (
    AdminDashboardExtras,
    DashboardLayoutResponse,
    DatasetEnrichmentStats,
    ModelPipelineStats,
    MonitoringSummary,
    WidgetConfigDto,
)
from app.entities.user_dashboard_layout import (
    DEFAULT_WIDGETS,
    UserDashboardLayout,
    WidgetConfig,
)
from app.repositories.training_scenario import TrainingScenarioRepository
from app.repositories.user_dashboard_layout import UserDashboardLayoutRepository


class DashboardService:
    """Service for dashboard summary, layout, and statistics.

    Responsibilities:
    - Calculate dashboard metrics from raw data collections
    - Manage user dashboard layouts
    - Aggregate admin-only pipeline statistics
    """

    # Collection names (centralized)
    RAW_REPOS_COLLECTION = "raw_repositories"
    RAW_BUILDS_COLLECTION = "raw_build_runs"
    BUILD_SOURCES_COLLECTION = "build_sources"
    TRAINING_SCENARIOS_COLLECTION = "training_scenarios"
    SOURCE_BUILDS_COLLECTION = "source_builds"
    MODEL_REPO_CONFIGS_COLLECTION = "model_repo_configs"
    SYSTEM_LOGS_COLLECTION = "system_logs"
    USERS_COLLECTION = "users"

    def __init__(self, db: Database):
        self.db = db
        self.layout_repo = UserDashboardLayoutRepository(db)
        self._scenario_repo = TrainingScenarioRepository(db)

    def get_summary(
        self, current_user: Optional[dict] = None
    ) -> DashboardSummaryResponse:
        """Get dashboard summary with RBAC filtering.

        Returns aggregated metrics from public repositories:
        - Total builds, success rate, average duration
        - Repository distribution (builds per repo)
        - Active repos count
        - Admin-only pipeline statistics

        Args:
            current_user: Current user dict with role and github_accessible_repos

        Returns:
            DashboardSummaryResponse with metrics and repo distribution
        """
        user_context = self._extract_user_context(current_user)

        # Get repositories matching user's accessibility
        repos_with_ids = self._fetch_accessible_repositories(user_context)

        # Early return if no repos
        if not repos_with_ids:
            return self._create_empty_summary()

        repo_ids, repos_map = repos_with_ids

        # Fetch all build metrics in single aggregation pipeline
        build_metrics = self._calculate_build_metrics(repo_ids)

        # Calculate repo distribution using aggregation (avoid N+1 query)
        repo_distribution = self._calculate_repo_distribution(repos_map, build_metrics)

        # Fetch dataset count
        dataset_count = self.db[self.BUILD_SOURCES_COLLECTION].count_documents({})

        # Admin extras (only if user is admin)
        admin_extras = (
            self._fetch_admin_pipeline_stats() if user_context["is_admin"] else None
        )

        return DashboardSummaryResponse(
            metrics=DashboardMetrics(
                total_builds=int(build_metrics["total_builds"]),
                success_rate=float(build_metrics["success_rate"]),
                average_duration_minutes=float(build_metrics["avg_duration_minutes"]),
            ),
            trends=[],
            repo_distribution=repo_distribution,
            dataset_count=dataset_count,
            active_repos=len(repos_map),
            admin_extras=admin_extras,
        )

    # =====================================================
    # PRIVATE HELPER METHODS - User Context & RBAC
    # =====================================================

    def _extract_user_context(self, current_user: Optional[dict]) -> Dict[str, Any]:
        """Extract and normalize user context for RBAC filtering."""
        if not current_user:
            return {
                "is_admin": True,
                "role": "admin",
                "accessible_repos": [],
            }

        return {
            "is_admin": current_user.get("role") == "admin",
            "role": current_user.get("role", "user"),
            "accessible_repos": current_user.get("github_accessible_repos", []),
        }

    def _fetch_accessible_repositories(
        self, user_context: Dict
    ) -> Optional[Tuple[List[ObjectId], Dict[ObjectId, str]]]:
        """Fetch repositories accessible to user (public repos only).

        Returns:
            Tuple of (repo_ids list, repo_id->full_name dict) or None if no repos
        """
        repo_filter = {}

        # Add accessible repos filter for non-admin users
        if not user_context["is_admin"] and user_context["accessible_repos"]:
            repo_filter["full_name"] = {"$in": user_context["accessible_repos"]}
        elif not user_context["is_admin"]:
            # Non-admin with no accessible repos
            return None

        repos = list(
            self.db[self.RAW_REPOS_COLLECTION].find(
                repo_filter, {"_id": 1, "full_name": 1}
            )
        )

        if not repos:
            return None

        repo_ids = [r["_id"] for r in repos]
        repos_map = {r["_id"]: r["full_name"] for r in repos}

        return repo_ids, repos_map

    def _create_empty_summary(self) -> DashboardSummaryResponse:
        """Create empty dashboard summary (no repos case)."""
        return DashboardSummaryResponse(
            metrics=DashboardMetrics(
                total_builds=0,
                success_rate=0.0,
                average_duration_minutes=0.0,
            ),
            trends=[],
            repo_distribution=[],
            dataset_count=0,
            active_repos=0,
            admin_extras=None,
        )

    # =====================================================
    # PRIVATE HELPER METHODS - Build Metrics (Optimized)
    # =====================================================

    def _calculate_build_metrics(self, repo_ids: List[ObjectId]) -> Dict[str, Any]:
        """Calculate all build metrics in single aggregation pipeline.

        Optimized: Single MongoDB pipeline instead of multiple count_documents calls.

        Returns:
            Dict with total_builds (int), success_rate (float), avg_duration_minutes (float)
        """
        pipeline = [
            {
                "$match": {
                    "raw_repo_id": {"$in": repo_ids},
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_builds": {"$sum": 1},
                    "successful_builds": {
                        "$sum": {"$cond": [{"$eq": ["$conclusion", "success"]}, 1, 0]}
                    },
                    "avg_duration_seconds": {
                        "$avg": {
                            "$cond": [
                                {"$ne": ["$duration_seconds", None]},
                                "$duration_seconds",
                                None,
                            ]
                        }
                    },
                }
            },
        ]

        results = list(self.db[self.RAW_BUILDS_COLLECTION].aggregate(pipeline))

        if not results:
            return {
                "total_builds": 0,
                "success_rate": 0.0,
                "avg_duration_minutes": 0.0,
            }

        result = results[0]
        total_builds = result["total_builds"]
        successful_builds = result["successful_builds"]
        avg_duration_seconds = result["avg_duration_seconds"] or 0

        return {
            "total_builds": total_builds,
            "success_rate": (
                (successful_builds / total_builds * 100) if total_builds > 0 else 0.0
            ),
            "avg_duration_minutes": (
                avg_duration_seconds / 60 if avg_duration_seconds else 0.0
            ),
        }

    def _calculate_repo_distribution(
        self, repos_map: Dict[ObjectId, str], build_metrics: Dict
    ) -> List[RepoDistributionEntry]:
        """Calculate build count per repository using aggregation pipeline.

        Optimized: Uses $facet or separate group instead of N+1 queries.

        Args:
            repos_map: Dict of repo_id -> full_name
            build_metrics: Result from _calculate_build_metrics (for reference)

        Returns:
            List of RepoDistributionEntry sorted by build count descending
        """
        pipeline = [
            {"$match": {"raw_repo_id": {"$in": list(repos_map.keys())}}},
            {
                "$group": {
                    "_id": "$raw_repo_id",
                    "build_count": {"$sum": 1},
                }
            },
            {"$sort": {"build_count": -1}},
        ]

        distributions = list(self.db[self.RAW_BUILDS_COLLECTION].aggregate(pipeline))

        # Build result with full_name from repos_map
        result = []
        for dist in distributions:
            repo_id = dist["_id"]
            result.append(
                RepoDistributionEntry(
                    id=str(repo_id),
                    repository=repos_map.get(repo_id, "Unknown"),
                    builds=dist["build_count"],
                )
            )

        # Add repos with 0 builds
        for repo_id, repo_name in repos_map.items():
            if not any(d.id == str(repo_id) for d in result):
                result.append(
                    RepoDistributionEntry(
                        id=str(repo_id),
                        repository=repo_name,
                        builds=0,
                    )
                )

        return result

    # =====================================================
    # PRIVATE HELPER METHODS - Admin Pipeline Statistics
    # =====================================================

    def _fetch_admin_pipeline_stats(self) -> AdminDashboardExtras:
        """Fetch admin-only pipeline statistics (optimized).

        Returns all admin stats in minimal DB calls:
        - Training scenario pipeline stats
        - Model pipeline stats
        - System monitoring (24h errors)
        - User count
        """
        training_stats = self._calculate_training_scenario_stats()
        model_stats = self._calculate_model_pipeline_stats()
        monitoring_stats = self._calculate_monitoring_stats()
        total_users = self.db[self.USERS_COLLECTION].count_documents({})

        return AdminDashboardExtras(
            dataset_enrichment=training_stats,
            model_pipeline=model_stats,
            monitoring=monitoring_stats,
            total_users=total_users,
        )

    def _calculate_training_scenario_stats(self) -> DatasetEnrichmentStats:
        """Calculate training scenario pipeline stats using aggregation."""
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_scenarios": {"$sum": 1},
                    "queued_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "queued"]}, 1, 0]}
                    },
                    "processing_count": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$in": [
                                        "$status",
                                        [
                                            "filtering",
                                            "ingesting",
                                            "processing",
                                            "splitting",
                                        ],
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                    "completed_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}
                    },
                }
            }
        ]

        result = list(self.db[self.TRAINING_SCENARIOS_COLLECTION].aggregate(pipeline))
        group = result[0] if result else {}

        total_enriched_builds = self.db[self.SOURCE_BUILDS_COLLECTION].count_documents(
            {}
        )

        # Dataset export stats
        total_datasets = self.db["training_dataset_exports"].count_documents({})
        exported_datasets = self.db["training_dataset_exports"].count_documents(
            {"status": "completed"}
        )

        return DatasetEnrichmentStats(
            active_scenarios=group.get("total_scenarios", 0),
            queued_scenarios=group.get("queued_count", 0),
            processing_scenarios=group.get("processing_count", 0),
            completed_scenarios=group.get("completed_count", 0),
            total_enriched_builds=total_enriched_builds,
            total_datasets=total_datasets,
            exported_datasets=exported_datasets,
        )

    def _calculate_model_pipeline_stats(self) -> ModelPipelineStats:
        """Calculate model pipeline stats using aggregation."""
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_repos": {"$sum": 1},
                    "fetching_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "fetching"]}, 1, 0]}
                    },
                    "ingesting_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "ingesting"]}, 1, 0]}
                    },
                    "processing_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "processing"]}, 1, 0]}
                    },
                    "processed_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "processed"]}, 1, 0]}
                    },
                }
            }
        ]

        result = list(self.db[self.MODEL_REPO_CONFIGS_COLLECTION].aggregate(pipeline))
        group = result[0] if result else {}

        # New: explicit import/ingest metrics from model_repo_configs
        # Imported = total repos in model pipeline (all statuses)
        imported_repos = self.db[self.MODEL_REPO_CONFIGS_COLLECTION].count_documents({})
        # Count repos in model_repo_configs with status = 'ingested'
        ingested_repos_distinct = self.db[
            self.MODEL_REPO_CONFIGS_COLLECTION
        ].count_documents({"status": "ingested"})

        return ModelPipelineStats(
            total_repos=group.get("total_repos", 0),
            fetching_repos=group.get("fetching_count", 0),
            ingesting_repos=group.get("ingesting_count", 0),
            processing_repos=group.get("processing_count", 0),
            processed_repos=group.get("processed_count", 0),
            imported_repos=imported_repos,
            ingested_repos_distinct=ingested_repos_distinct,
        )

    def _calculate_monitoring_stats(self) -> MonitoringSummary:
        """Calculate system monitoring stats (24h window)."""
        day_ago = datetime.utcnow() - timedelta(hours=24)

        error_count = self.db[self.SYSTEM_LOGS_COLLECTION].count_documents(
            {"level": "ERROR", "timestamp": {"$gte": day_ago}}
        )

        return MonitoringSummary(
            celery_workers=0,  # TODO: Fetch from Celery stats if available
            queue_depth=0,  # TODO: Fetch from queue backend if available
            error_count_24h=error_count,
        )

    # =====================================================
    # PUBLIC METHODS - Dashboard Layout Management
    # =====================================================

    def get_layout(self, user_id: ObjectId) -> DashboardLayoutResponse:
        """Get user's saved dashboard layout.

        Returns default layout if user has no saved layout yet.

        Args:
            user_id: User's ObjectId

        Returns:
            DashboardLayoutResponse with user's widget configuration
        """
        layout = self.layout_repo.find_by_user(user_id)

        if not layout:
            # Return default layout for new users
            widgets = [self._convert_widget_config_to_dto(w) for w in DEFAULT_WIDGETS]
            return DashboardLayoutResponse(widgets=widgets)

        return DashboardLayoutResponse(
            widgets=[self._convert_widget_config_to_dto(w) for w in layout.widgets]
        )

    def save_layout(
        self, user_id: ObjectId, widgets: List[WidgetConfigDto]
    ) -> DashboardLayoutResponse:
        """Save user's dashboard layout.

        Args:
            user_id: User's ObjectId
            widgets: List of widget configurations to save

        Returns:
            DashboardLayoutResponse with saved widget configuration
        """
        # Convert DTOs to entity models
        widget_configs = [
            WidgetConfig(
                _id=None,
                widget_id=w.widget_id,
                widget_type=w.widget_type,
                title=w.title,
                enabled=w.enabled,
                x=w.x,
                y=w.y,
                w=w.w,
                h=w.h,
            )
            for w in widgets
        ]

        # Upsert layout in repository
        layout = UserDashboardLayout(_id=None, user_id=user_id, widgets=widget_configs)
        saved = self.layout_repo.upsert_by_user(user_id, layout)

        return DashboardLayoutResponse(
            widgets=[self._convert_widget_config_to_dto(w) for w in saved.widgets]
        )

    # =====================================================
    # PRIVATE HELPER METHODS - Data Mapping
    # =====================================================

    def _convert_widget_config_to_dto(self, widget: WidgetConfig) -> WidgetConfigDto:
        """Convert WidgetConfig entity to DTO."""
        return WidgetConfigDto(
            widget_id=widget.widget_id,
            widget_type=widget.widget_type,
            title=widget.title,
            enabled=widget.enabled,
            x=widget.x,
            y=widget.y,
            w=widget.w,
            h=widget.h,
        )
