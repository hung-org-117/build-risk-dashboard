"""
ML Splitting Strategy Service - Applies splitting strategies to datasets.

This service handles:
- Creating group columns (bins for numeric features)
- Applying splitting strategies (delegated to strategies/ package)
- Generating split statistics

Strategy implementations are in app.services.strategies package.
Grouping utilities are in app.services.strategies.grouping module.
"""

import logging
from typing import Any, Dict, List

import pandas as pd

from app.entities.enums import GroupByDimension
from app.entities.training_dataset_export import ExportSplittingConfig
from app.services.strategies import SplitResult, SplittingStrategyFactory
from app.services.strategies.grouping import (
    create_equal_width_bins,
    create_language_column,
    create_time_slots,
    get_group_label,
)

logger = logging.getLogger(__name__)


class SplittingStrategyService:
    """
    Service for applying splitting strategies to datasets.

    Handles:
    - Creating group columns (bins for numeric features)
    - Applying splitting strategies
    - Generating split statistics
    """

    def __init__(self):
        pass

    def apply_split(
        self,
        df: pd.DataFrame,
        config: ExportSplittingConfig,
        label_column: str = "outcome",
    ) -> SplitResult:
        """
        Apply splitting strategy to a DataFrame.

        Args:
            df: DataFrame with feature data
            config: ExportSplittingConfig with strategy and grouping
            label_column: Column name for outcome label

        Returns:
            SplitResult with split indices and metadata
        """
        group_column = self._prepare_group_column(df, config)
        strategy = SplittingStrategyFactory.create(config)
        result = strategy.split(df, group_column, label_column)
        result.metadata["original_group_by"] = str(config.group_by)
        return result

    def _prepare_group_column(
        self,
        df: pd.DataFrame,
        config: ExportSplittingConfig,
    ) -> str:
        """
        Create/prepare the group column for splitting.

        Args:
            df: DataFrame
            config: ExportSplittingConfig with group_by, num_bins, time_slots

        Returns:
            Column name to use for grouping
        """
        group_by = config.group_by
        num_bins = getattr(config, "num_bins", 4)
        time_slots = getattr(config, "time_slots", 4)
        group_by_str = str(group_by) if not isinstance(group_by, str) else group_by

        if (
            group_by_str == "repo_language"
            or group_by == GroupByDimension.REPO_LANGUAGE
        ):
            return create_language_column(df)

        if (
            group_by_str == "percentage_of_builds_before"
            or group_by == GroupByDimension.PERCENTAGE_OF_BUILDS_BEFORE
        ):
            return create_equal_width_bins(df, "percentage_of_builds_before", num_bins)

        if (
            group_by_str == "number_of_builds_before"
            or group_by == GroupByDimension.NUMBER_OF_BUILDS_BEFORE
        ):
            return create_equal_width_bins(df, "number_of_builds_before", num_bins)

        if group_by_str == "time_of_day" or group_by == GroupByDimension.TIME_OF_DAY:
            return create_time_slots(df, time_slots)

        # Use column directly if exists
        if group_by_str in df.columns:
            return group_by_str
        raise ValueError(f"Unknown grouping dimension: {group_by}")

    def get_split_statistics(
        self,
        df: pd.DataFrame,
        result: SplitResult,
        label_column: str = "outcome",
    ) -> Dict[str, Any]:
        """Calculate statistics for each split."""
        return {
            "train": self._get_subset_stats(df, result.train_indices, label_column),
            "validation": self._get_subset_stats(df, result.val_indices, label_column),
            "test": self._get_subset_stats(df, result.test_indices, label_column),
        }

    def _get_subset_stats(
        self,
        df: pd.DataFrame,
        indices: List[int],
        label_column: str,
    ) -> Dict[str, Any]:
        """Get statistics for a subset of data."""
        if not indices:
            return {"count": 0, "class_distribution": {}, "positive_rate": 0.0}

        subset = df.loc[indices]
        class_dist = subset[label_column].value_counts().to_dict()
        total = len(subset)
        positive = class_dist.get(1, 0)

        return {
            "count": total,
            "class_distribution": {str(k): v for k, v in class_dist.items()},
            "positive_rate": positive / total if total > 0 else 0.0,
        }

    def get_available_groups(
        self,
        df: pd.DataFrame,
        group_by: GroupByDimension,
        num_bins: int = 4,
        time_slots: int = 4,
    ) -> Dict[str, Any]:
        """Get available groups with counts for LOO/LTO strategy selection."""
        temp_config = ExportSplittingConfig(
            group_by=group_by,
            num_bins=num_bins,
            time_slots=time_slots,
        )

        group_column = self._prepare_group_column(df.copy(), temp_config)
        group_counts = df[group_column].value_counts().to_dict()

        groups = []
        for value, count in sorted(group_counts.items(), key=lambda x: -x[1]):
            group_info = {
                "value": str(value),
                "label": get_group_label(group_by, value),
                "count": count,
            }
            if count < 50:
                group_info["warning"] = "small_sample"
            groups.append(group_info)

        return {
            "group_by": str(group_by),
            "groups": groups,
            "total_builds": len(df),
            "num_bins": num_bins,
            "time_slots": time_slots,
        }
