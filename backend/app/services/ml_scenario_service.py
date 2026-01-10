"""
ML Scenario Service - Business logic for ML Dataset Scenario Builder.

Handles:
- YAML config parsing and validation
- Scenario CRUD operations
- Phase orchestration (filter → ingest → process → split)
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import yaml
from bson import ObjectId
from fastapi import HTTPException, status
from pydantic import ValidationError
from pymongo.database import Database

from app.entities.ml_scenario import (
    MLScenario,
    MLScenarioStatus,
    DataSourceConfig,
    FeatureConfig,
    SplittingConfig,
    PreprocessingConfig,
    OutputConfig,
)
from app.entities.ml_scenario_enrichment_build import MLScenarioEnrichmentBuild
from app.entities.ml_scenario_import_build import MLScenarioImportBuild
from app.entities.ml_dataset_split import MLDatasetSplit
from app.repositories.ml_scenario import MLScenarioRepository
from app.repositories.ml_scenario_import_build import MLScenarioImportBuildRepository
from app.repositories.ml_scenario_enrichment_build import (
    MLScenarioEnrichmentBuildRepository,
)
from app.repositories.ml_dataset_split import MLDatasetSplitRepository
from app.repositories.raw_repository import RawRepositoryRepository
from app.repositories.raw_build_run import RawBuildRunRepository
from app import paths

logger = logging.getLogger(__name__)


class MLScenarioService:
    """Service for ML Dataset Scenario Builder operations."""

    def __init__(self, db: Database):
        self.db = db
        self.scenario_repo = MLScenarioRepository(db)
        self.import_build_repo = MLScenarioImportBuildRepository(db)
        self.enrichment_build_repo = MLScenarioEnrichmentBuildRepository(db)
        self.split_repo = MLDatasetSplitRepository(db)
        self.raw_repo_repo = RawRepositoryRepository(db)
        self.raw_build_run_repo = RawBuildRunRepository(db)

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def list_scenarios(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        status_filter: Optional[MLScenarioStatus] = None,
        q: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        List scenarios for a user.

        Args:
            user_id: User ID
            skip: Pagination offset
            limit: Max results
            status_filter: Filter by status
            q: Search query

        Returns:
            Tuple of (scenarios as dicts, total count)
        """
        scenarios, total = self.scenario_repo.list_by_user(
            user_id=user_id,
            skip=skip,
            limit=limit,
            status_filter=status_filter,
            q=q,
        )
        return [self._serialize_scenario(s) for s in scenarios], total

    def get_scenario(
        self,
        scenario_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Get scenario details.

        Args:
            scenario_id: Scenario ID
            user_id: User ID for permission check

        Returns:
            Scenario as dict

        Raises:
            HTTPException: If not found or permission denied
        """
        scenario = self.scenario_repo.find_by_id(scenario_id)
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario {scenario_id} not found",
            )

        # Permission check
        if scenario.created_by and str(scenario.created_by) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this scenario",
            )

        return self._serialize_scenario(scenario)

    def create_scenario(
        self,
        user_id: str,
        name: str,
        yaml_config: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new scenario from YAML config.

        Args:
            user_id: User ID creating the scenario
            name: Scenario name
            yaml_config: Raw YAML configuration string
            description: Optional description

        Returns:
            Created scenario as dict

        Raises:
            HTTPException: If YAML is invalid or name exists
        """
        # Check for duplicate name
        existing = self.scenario_repo.find_by_name(name, user_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Scenario with name '{name}' already exists",
            )

        # Parse and validate YAML
        parsed_config = self._parse_yaml_config(yaml_config)

        # Create scenario entity
        scenario = MLScenario(
            name=name,
            description=description,
            version=parsed_config.get("version", "1.0"),
            yaml_config=yaml_config,
            data_source_config=self._parse_data_source_config(
                parsed_config.get("data_source", {})
            ),
            feature_config=self._parse_feature_config(
                parsed_config.get("features", {})
            ),
            splitting_config=self._parse_splitting_config(
                parsed_config.get("splitting", {})
            ),
            preprocessing_config=self._parse_preprocessing_config(
                parsed_config.get("preprocessing", {})
            ),
            output_config=self._parse_output_config(parsed_config.get("output", {})),
            status=MLScenarioStatus.QUEUED,
            created_by=ObjectId(user_id),
        )

        created = self.scenario_repo.insert_one(scenario)

        # Create scenario directory
        scenario_dir = paths.get_ml_scenario_dir(str(created.id))
        scenario_dir.mkdir(parents=True, exist_ok=True)

        # Save YAML config file
        config_path = paths.get_ml_scenario_config_path(str(created.id))
        config_path.write_text(yaml_config)

        logger.info(f"Created ML scenario: {created.id} - {name}")
        return self._serialize_scenario(created)

    def update_scenario(
        self,
        scenario_id: str,
        user_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        yaml_config: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update scenario fields.

        Args:
            scenario_id: Scenario ID
            user_id: User ID for permission check
            name: New name (optional)
            description: New description (optional)
            yaml_config: New YAML config (optional, re-parses)

        Returns:
            Updated scenario as dict

        Raises:
            HTTPException: If not found or invalid
        """
        scenario = self.scenario_repo.find_by_id(scenario_id)
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario {scenario_id} not found",
            )

        # Permission check
        if scenario.created_by and str(scenario.created_by) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to modify this scenario",
            )

        # Cannot update if processing
        if scenario.status in (
            MLScenarioStatus.FILTERING,
            MLScenarioStatus.INGESTING,
            MLScenarioStatus.PROCESSING,
            MLScenarioStatus.SPLITTING,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update scenario while processing",
            )

        updates: Dict[str, Any] = {"updated_at": datetime.utcnow()}

        if name is not None:
            # Check for duplicate name
            existing = self.scenario_repo.find_by_name(name, user_id)
            if existing and str(existing.id) != scenario_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Scenario with name '{name}' already exists",
                )
            updates["name"] = name

        if description is not None:
            updates["description"] = description

        if yaml_config is not None:
            parsed_config = self._parse_yaml_config(yaml_config)
            updates["yaml_config"] = yaml_config
            updates["data_source_config"] = self._parse_data_source_config(
                parsed_config.get("data_source", {})
            ).model_dump()
            updates["feature_config"] = self._parse_feature_config(
                parsed_config.get("features", {})
            ).model_dump()
            updates["splitting_config"] = self._parse_splitting_config(
                parsed_config.get("splitting", {})
            ).model_dump()
            updates["preprocessing_config"] = self._parse_preprocessing_config(
                parsed_config.get("preprocessing", {})
            ).model_dump()
            updates["output_config"] = self._parse_output_config(
                parsed_config.get("output", {})
            ).model_dump()

            # Update saved config file
            config_path = paths.get_ml_scenario_config_path(scenario_id)
            config_path.write_text(yaml_config)

            # Reset status to QUEUED if updating config
            updates["status"] = MLScenarioStatus.QUEUED.value

        updated = self.scenario_repo.update_one(scenario_id, updates)
        return self._serialize_scenario(updated)

    def delete_scenario(
        self,
        scenario_id: str,
        user_id: str,
    ) -> bool:
        """
        Delete a scenario and all associated data.

        Args:
            scenario_id: Scenario ID
            user_id: User ID for permission check

        Returns:
            True if deleted

        Raises:
            HTTPException: If not found or permission denied
        """
        scenario = self.scenario_repo.find_by_id(scenario_id)
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario {scenario_id} not found",
            )

        # Permission check
        if scenario.created_by and str(scenario.created_by) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this scenario",
            )

        # Delete associated data
        self.import_build_repo.delete_by_scenario(scenario_id)
        self.enrichment_build_repo.delete_by_scenario(scenario_id)
        self.split_repo.delete_by_scenario(scenario_id)

        # Delete files
        paths.cleanup_ml_scenario_files(scenario_id)

        # Delete scenario
        self.scenario_repo.delete_one(scenario_id)

        logger.info(f"Deleted ML scenario: {scenario_id}")
        return True

    # =========================================================================
    # YAML Parsing Helpers
    # =========================================================================

    def _parse_yaml_config(self, yaml_string: str) -> Dict[str, Any]:
        """
        Parse and validate YAML configuration.

        Args:
            yaml_string: Raw YAML string

        Returns:
            Parsed config as dict

        Raises:
            HTTPException: If YAML is invalid
        """
        try:
            config = yaml.safe_load(yaml_string)
            if not isinstance(config, dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="YAML config must be a dictionary",
                )
            return config
        except yaml.YAMLError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid YAML syntax: {str(e)}",
            )

    def _parse_data_source_config(self, config: Dict[str, Any]) -> DataSourceConfig:
        """Parse data_source section of YAML."""
        try:
            repos_config = config.get("repositories", {})
            builds_config = config.get("builds", {})
            date_range = builds_config.get("date_range", {})

            return DataSourceConfig(
                filter_by=repos_config.get("filter_by", "all"),
                languages=repos_config.get("languages", []),
                repo_names=repos_config.get("names", []),
                owners=repos_config.get("owners", []),
                date_start=self._parse_date(date_range.get("start")),
                date_end=self._parse_date(date_range.get("end")),
                conclusions=builds_config.get("conclusions", ["success", "failure"]),
                exclude_bots=builds_config.get("exclude_bots", True),
                ci_provider=config.get("ci_provider", "all"),
            )
        except Exception as e:
            logger.warning(f"Error parsing data_source config: {e}")
            return DataSourceConfig()

    def _parse_feature_config(self, config: Dict[str, Any]) -> FeatureConfig:
        """Parse features section of YAML."""
        try:
            return FeatureConfig(
                dag_features=config.get("dag_features", []),
                scan_metrics=config.get("scan_metrics", {}),
                exclude=config.get("exclude", []),
            )
        except Exception as e:
            logger.warning(f"Error parsing feature config: {e}")
            return FeatureConfig()

    def _parse_splitting_config(self, config: Dict[str, Any]) -> SplittingConfig:
        """Parse splitting section of YAML."""
        try:
            strategy_config = config.get("config", {})
            return SplittingConfig(
                strategy=config.get("strategy", "stratified_within_group"),
                group_by=config.get("group_by", "language_group"),
                groups=strategy_config.get("groups", []),
                ratios=strategy_config.get(
                    "ratios", {"train": 0.7, "val": 0.15, "test": 0.15}
                ),
                stratify_by=strategy_config.get("stratify_by", "outcome"),
                test_groups=strategy_config.get("test_groups", []),
                val_groups=strategy_config.get("val_groups", []),
                train_groups=strategy_config.get("train_groups", []),
                reduce_label=strategy_config.get("reduce_label"),
                reduce_ratio=strategy_config.get("reduce_ratio", 0.5),
                novelty_group=strategy_config.get("novelty_group"),
                novelty_label=strategy_config.get("novelty_label"),
            )
        except Exception as e:
            logger.warning(f"Error parsing splitting config: {e}")
            return SplittingConfig()

    def _parse_preprocessing_config(
        self, config: Dict[str, Any]
    ) -> PreprocessingConfig:
        """Parse preprocessing section of YAML."""
        try:
            missing_config = config.get("missing_features", {})
            return PreprocessingConfig(
                missing_values_strategy=missing_config.get("strategy", "drop_row"),
                fill_value=missing_config.get("fill_value", 0),
                normalization_method=config.get("normalization", {}).get(
                    "method", "z_score"
                ),
                strict_mode=config.get("strict_mode", False),
            )
        except Exception as e:
            logger.warning(f"Error parsing preprocessing config: {e}")
            return PreprocessingConfig()

    def _parse_output_config(self, config: Dict[str, Any]) -> OutputConfig:
        """Parse output section of YAML."""
        try:
            return OutputConfig(
                format=config.get("format", "parquet"),
                include_metadata=config.get("include_metadata", True),
            )
        except Exception as e:
            logger.warning(f"Error parsing output config: {e}")
            return OutputConfig()

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None

    # =========================================================================
    # Serialization
    # =========================================================================

    def _serialize_scenario(self, scenario: MLScenario) -> Dict[str, Any]:
        """Serialize scenario for API response."""
        return {
            "id": str(scenario.id),
            "name": scenario.name,
            "description": scenario.description,
            "version": scenario.version,
            "status": scenario.status,
            "error_message": scenario.error_message,
            # Statistics
            "builds_total": scenario.builds_total,
            "builds_ingested": scenario.builds_ingested,
            "builds_features_extracted": scenario.builds_features_extracted,
            "builds_missing_resource": scenario.builds_missing_resource,
            "builds_failed": scenario.builds_failed,
            # Split counts
            "train_count": scenario.train_count,
            "val_count": scenario.val_count,
            "test_count": scenario.test_count,
            # Config summaries
            "splitting_strategy": (
                scenario.splitting_config.strategy
                if isinstance(scenario.splitting_config, SplittingConfig)
                else scenario.splitting_config.get("strategy")
            ),
            "group_by": (
                scenario.splitting_config.group_by
                if isinstance(scenario.splitting_config, SplittingConfig)
                else scenario.splitting_config.get("group_by")
            ),
            # Timestamps
            "created_at": (
                scenario.created_at.isoformat() if scenario.created_at else None
            ),
            "updated_at": (
                scenario.updated_at.isoformat() if scenario.updated_at else None
            ),
            # Phase timestamps
            "filtering_completed_at": (
                scenario.filtering_completed_at.isoformat()
                if scenario.filtering_completed_at
                else None
            ),
            "ingestion_completed_at": (
                scenario.ingestion_completed_at.isoformat()
                if scenario.ingestion_completed_at
                else None
            ),
            "processing_completed_at": (
                scenario.processing_completed_at.isoformat()
                if scenario.processing_completed_at
                else None
            ),
            "splitting_completed_at": (
                scenario.splitting_completed_at.isoformat()
                if scenario.splitting_completed_at
                else None
            ),
        }

    # =========================================================================
    # Split Files
    # =========================================================================

    def get_scenario_splits(
        self,
        scenario_id: str,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all split files for a scenario.

        Args:
            scenario_id: Scenario ID
            user_id: User ID for permission check

        Returns:
            List of split metadata dicts
        """
        # Permission check via get_scenario
        self.get_scenario(scenario_id, user_id)

        splits = self.split_repo.find_by_scenario(scenario_id)
        return [self._serialize_split(s) for s in splits]

    def _serialize_split(self, split: MLDatasetSplit) -> Dict[str, Any]:
        """Serialize split for API response."""
        return {
            "id": str(split.id),
            "scenario_id": str(split.scenario_id),
            "split_type": split.split_type,
            "record_count": split.record_count,
            "feature_count": split.feature_count,
            "class_distribution": split.class_distribution,
            "group_distribution": split.group_distribution,
            "file_path": split.file_path,
            "file_size_bytes": split.file_size_bytes,
            "file_format": split.file_format,
            "generated_at": (
                split.generated_at.isoformat() if split.generated_at else None
            ),
            "generation_duration_seconds": split.generation_duration_seconds,
        }
