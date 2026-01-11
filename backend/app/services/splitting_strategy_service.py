"""
ML Splitting Strategy Service - Implements the 15 splitting strategies.

Strategies are organized by grouping dimension:
- language_group (5 strategies)
- percentage_of_builds_before / number_of_builds_before (5 strategies)
- time_of_day (5 strategies)

Each dimension supports:
1. Stratified Within Group (70-15-15)
2. Leave-One-Out
3. Leave-Two-Out
4. Imbalanced Train (reduce 50% of label 1)
5. Extreme Novelty (all samples of one group+label → test)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit

from app.entities.training_scenario import (
    GroupByDimension,
    SplitStrategy,
    SplittingConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class SplitResult:
    """Result of a splitting operation."""

    train_indices: List[int]
    val_indices: List[int]
    test_indices: List[int]
    metadata: Dict[str, Any]


class BaseSplittingStrategy(ABC):
    """Base class for all splitting strategies."""

    def __init__(self, config: SplittingConfig):
        self.config = config

    @abstractmethod
    def split(
        self,
        df: pd.DataFrame,
        group_column: str,
        label_column: str = "outcome",
    ) -> SplitResult:
        """
        Split the dataframe into train/val/test.

        Args:
            df: DataFrame with all samples
            group_column: Column name for grouping (e.g., 'language_group')
            label_column: Column name for outcome label

        Returns:
            SplitResult with indices for each split
        """
        pass

    def _get_stratified_split(
        self,
        df: pd.DataFrame,
        label_column: str,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        random_state: int = 42,
    ) -> Tuple[List[int], List[int], List[int]]:
        """
        Perform stratified split maintaining label distribution.

        Returns:
            Tuple of (train_indices, val_indices, test_indices)
        """
        indices = df.index.tolist()
        labels = df[label_column].values

        # Handle edge case: not enough samples per class
        unique_labels, counts = np.unique(labels, return_counts=True)
        min_samples_per_class = counts.min()

        if min_samples_per_class < 2:
            # Fall back to random split if not enough samples for stratification
            logger.warning("Not enough samples for stratification, using random split")
            np.random.seed(random_state)
            np.random.shuffle(indices)
            n = len(indices)
            train_end = int(n * train_ratio)
            val_end = int(n * (train_ratio + val_ratio))
            return indices[:train_end], indices[train_end:val_end], indices[val_end:]

        # First split: train vs (val+test)
        test_val_ratio = 1 - train_ratio
        splitter1 = StratifiedShuffleSplit(
            n_splits=1, test_size=test_val_ratio, random_state=random_state
        )

        train_idx, temp_idx = next(splitter1.split(indices, labels))
        train_indices = [indices[i] for i in train_idx]
        temp_indices = [indices[i] for i in temp_idx]
        temp_labels = labels[temp_idx]

        # Second split: val vs test
        val_in_temp = val_ratio / test_val_ratio

        # Check if we have enough samples for second stratification
        _, counts_temp = np.unique(temp_labels, return_counts=True)
        if counts_temp.min() < 2:
            n_temp = len(temp_indices)
            val_end = int(n_temp * val_in_temp)
            val_indices = temp_indices[:val_end]
            test_indices = temp_indices[val_end:]
        else:
            splitter2 = StratifiedShuffleSplit(
                n_splits=1, test_size=1 - val_in_temp, random_state=random_state
            )
            val_idx, test_idx = next(splitter2.split(temp_indices, temp_labels))
            val_indices = [temp_indices[i] for i in val_idx]
            test_indices = [temp_indices[i] for i in test_idx]

        return train_indices, val_indices, test_indices


class StratifiedWithinGroupStrategy(BaseSplittingStrategy):
    """
    Strategy 1/6/11: Stratified Within Group (Baseline 70-15-15)

    Within each group, split 70% train, 15% val, 15% test.
    Stratified by outcome within each group.
    """

    def split(
        self,
        df: pd.DataFrame,
        group_column: str,
        label_column: str = "outcome",
    ) -> SplitResult:
        train_indices = []
        val_indices = []
        test_indices = []

        ratios = self.config.ratios or {"train": 0.7, "val": 0.15, "test": 0.15}
        groups = df[group_column].unique()

        for group in groups:
            group_df = df[df[group_column] == group]
            if len(group_df) < 3:
                # Not enough samples, all go to train
                train_indices.extend(group_df.index.tolist())
                continue

            train_idx, val_idx, test_idx = self._get_stratified_split(
                group_df,
                label_column,
                train_ratio=ratios.get("train", 0.7),
                val_ratio=ratios.get("val", 0.15),
            )
            train_indices.extend(train_idx)
            val_indices.extend(val_idx)
            test_indices.extend(test_idx)

        return SplitResult(
            train_indices=train_indices,
            val_indices=val_indices,
            test_indices=test_indices,
            metadata={
                "strategy": "stratified_within_group",
                "group_column": group_column,
                "groups": list(groups),
                "ratios": ratios,
            },
        )


class LeaveOneOutStrategy(BaseSplittingStrategy):
    """
    Strategy 2/7/12: Leave-One-Group-Out

    1 group → Test
    1 group → Val
    2+ groups → Train
    """

    def split(
        self,
        df: pd.DataFrame,
        group_column: str,
        label_column: str = "outcome",
    ) -> SplitResult:
        test_groups = self.config.test_groups or []
        val_groups = self.config.val_groups or []
        train_groups = self.config.train_groups or []

        # Auto-assign if not specified
        all_groups = df[group_column].unique().tolist()
        if not test_groups or not val_groups or not train_groups:
            if len(all_groups) >= 4:
                test_groups = [all_groups[0]]
                val_groups = [all_groups[1]]
                train_groups = all_groups[2:]
            elif len(all_groups) == 3:
                test_groups = [all_groups[0]]
                val_groups = [all_groups[1]]
                train_groups = [all_groups[2]]
            else:
                # Fallback to stratified split
                logger.warning("Not enough groups for leave-one-out, using stratified")
                return StratifiedWithinGroupStrategy(self.config).split(
                    df, group_column, label_column
                )

        train_indices = df[df[group_column].isin(train_groups)].index.tolist()
        val_indices = df[df[group_column].isin(val_groups)].index.tolist()
        test_indices = df[df[group_column].isin(test_groups)].index.tolist()

        return SplitResult(
            train_indices=train_indices,
            val_indices=val_indices,
            test_indices=test_indices,
            metadata={
                "strategy": "leave_one_out",
                "group_column": group_column,
                "test_groups": test_groups,
                "val_groups": val_groups,
                "train_groups": train_groups,
            },
        )


class LeaveTwoOutStrategy(BaseSplittingStrategy):
    """
    Strategy 3/8/13: Leave-Two-Groups-Out

    2 groups → Test
    1 group → Val
    1+ groups → Train
    """

    def split(
        self,
        df: pd.DataFrame,
        group_column: str,
        label_column: str = "outcome",
    ) -> SplitResult:
        test_groups = self.config.test_groups or []
        val_groups = self.config.val_groups or []
        train_groups = self.config.train_groups or []

        all_groups = df[group_column].unique().tolist()
        if not test_groups or not val_groups or not train_groups:
            if len(all_groups) >= 4:
                test_groups = all_groups[:2]
                val_groups = [all_groups[2]]
                train_groups = all_groups[3:]
            else:
                logger.warning("Not enough groups for leave-two-out, using stratified")
                return StratifiedWithinGroupStrategy(self.config).split(
                    df, group_column, label_column
                )

        train_indices = df[df[group_column].isin(train_groups)].index.tolist()
        val_indices = df[df[group_column].isin(val_groups)].index.tolist()
        test_indices = df[df[group_column].isin(test_groups)].index.tolist()

        return SplitResult(
            train_indices=train_indices,
            val_indices=val_indices,
            test_indices=test_indices,
            metadata={
                "strategy": "leave_two_out",
                "group_column": group_column,
                "test_groups": test_groups,
                "val_groups": val_groups,
                "train_groups": train_groups,
            },
        )


class ImbalancedTrainStrategy(BaseSplittingStrategy):
    """
    Strategy 4/9/14: Imbalanced Train, Balanced Test

    Reduce 50% of label 1 samples in train set.
    Val and Test keep original distribution.
    """

    def split(
        self,
        df: pd.DataFrame,
        group_column: str,
        label_column: str = "outcome",
    ) -> SplitResult:
        reduce_label = self.config.reduce_label
        if reduce_label is None:
            reduce_label = 1
        reduce_ratio = self.config.reduce_ratio or 0.5

        train_indices = []
        val_indices = []
        test_indices = []

        ratios = self.config.ratios or {"train": 0.7, "val": 0.15, "test": 0.15}
        groups = df[group_column].unique()

        for group in groups:
            group_df = df[df[group_column] == group]
            if len(group_df) < 3:
                train_indices.extend(group_df.index.tolist())
                continue

            train_idx, val_idx, test_idx = self._get_stratified_split(
                group_df,
                label_column,
                train_ratio=ratios.get("train", 0.7),
                val_ratio=ratios.get("val", 0.15),
            )

            # Reduce samples with reduce_label in train set
            train_df = group_df.loc[train_idx]
            label_mask = train_df[label_column] == reduce_label
            reduce_indices = train_df[label_mask].index.tolist()
            keep_indices = train_df[~label_mask].index.tolist()

            # Keep only (1 - reduce_ratio) of reduce_label samples
            n_keep = int(len(reduce_indices) * (1 - reduce_ratio))
            np.random.seed(42)
            kept_reduce = (
                list(np.random.choice(reduce_indices, size=n_keep, replace=False))
                if n_keep > 0
                else []
            )

            train_indices.extend(keep_indices + kept_reduce)
            val_indices.extend(val_idx)
            test_indices.extend(test_idx)

        return SplitResult(
            train_indices=train_indices,
            val_indices=val_indices,
            test_indices=test_indices,
            metadata={
                "strategy": "imbalanced_train",
                "group_column": group_column,
                "reduce_label": reduce_label,
                "reduce_ratio": reduce_ratio,
            },
        )


class ExtremeNoveltyStrategy(BaseSplittingStrategy):
    """
    Strategy 5/10/15: Extreme Novelty in Sub-Group

    All samples of one specific group+label combination → Test.
    Remaining samples split normally.
    """

    def split(
        self,
        df: pd.DataFrame,
        group_column: str,
        label_column: str = "outcome",
    ) -> SplitResult:
        novelty_group = self.config.novelty_group
        novelty_label = self.config.novelty_label

        # Auto-select if not specified
        if novelty_group is None:
            groups = df[group_column].unique().tolist()
            novelty_group = groups[0] if groups else None

        if novelty_label is None:
            novelty_label = 1

        if novelty_group is None:
            logger.warning("No groups available for extreme novelty")
            return StratifiedWithinGroupStrategy(self.config).split(
                df, group_column, label_column
            )

        # All samples with novelty_group AND novelty_label → Test
        novelty_mask = (df[group_column] == novelty_group) & (
            df[label_column] == novelty_label
        )
        test_indices = df[novelty_mask].index.tolist()

        # Remaining samples → stratified train/val
        remaining_df = df[~novelty_mask]

        if len(remaining_df) < 3:
            train_indices = remaining_df.index.tolist()
            val_indices = []
        else:
            ratios = self.config.ratios or {"train": 0.7, "val": 0.15, "test": 0.15}
            # Adjust ratios since test is already determined
            train_ratio = ratios.get("train", 0.7) / (
                ratios.get("train", 0.7) + ratios.get("val", 0.15)
            )
            val_ratio = 1 - train_ratio

            train_idx, val_idx, _ = self._get_stratified_split(
                remaining_df,
                label_column,
                train_ratio=train_ratio,
                val_ratio=val_ratio,
            )
            train_indices = train_idx
            val_indices = val_idx

        return SplitResult(
            train_indices=train_indices,
            val_indices=val_indices,
            test_indices=test_indices,
            metadata={
                "strategy": "extreme_novelty",
                "group_column": group_column,
                "novelty_group": novelty_group,
                "novelty_label": novelty_label,
            },
        )


class SplittingStrategyFactory:
    """Factory for creating splitting strategy instances."""

    STRATEGY_MAP = {
        SplitStrategy.STRATIFIED_WITHIN_GROUP: StratifiedWithinGroupStrategy,
        SplitStrategy.LEAVE_ONE_OUT: LeaveOneOutStrategy,
        SplitStrategy.LEAVE_TWO_OUT: LeaveTwoOutStrategy,
        SplitStrategy.IMBALANCED_TRAIN: ImbalancedTrainStrategy,
        SplitStrategy.EXTREME_NOVELTY: ExtremeNoveltyStrategy,
        # String fallbacks
        "stratified_within_group": StratifiedWithinGroupStrategy,
        "leave_one_out": LeaveOneOutStrategy,
        "leave_two_out": LeaveTwoOutStrategy,
        "imbalanced_train": ImbalancedTrainStrategy,
        "extreme_novelty": ExtremeNoveltyStrategy,
    }

    @classmethod
    def create(cls, config: SplittingConfig) -> BaseSplittingStrategy:
        """
        Create a splitting strategy instance based on config.

        Args:
            config: SplittingConfig with strategy type

        Returns:
            BaseSplittingStrategy instance

        Raises:
            ValueError: If strategy type is unknown
        """
        strategy_type = config.strategy
        strategy_class = cls.STRATEGY_MAP.get(strategy_type)

        if strategy_class is None:
            raise ValueError(f"Unknown splitting strategy: {strategy_type}")

        return strategy_class(config)


class SplittingStrategyService:
    """
    Service for applying splitting strategies to datasets.

    Handles:
    - Creating group columns (bins for numeric features)
    - Applying splitting strategies
    - Generating split statistics
    """

    LANGUAGE_GROUPS = {
        "python": "backend",
        "java": "backend",
        "go": "backend",
        "rust": "backend",
        "c": "backend",
        "cpp": "backend",
        "csharp": "backend",
        "javascript": "fullstack",
        "typescript": "fullstack",
        "ruby": "fullstack",
        "php": "fullstack",
        "bash": "scripting",
        "shell": "scripting",
        "powershell": "scripting",
        "perl": "scripting",
        "lua": "scripting",
    }

    def __init__(self):
        pass

    def apply_split(
        self,
        df: pd.DataFrame,
        config: SplittingConfig,
        label_column: str = "outcome",
    ) -> SplitResult:
        """
        Apply splitting strategy to a DataFrame.

        Args:
            df: DataFrame with feature data
            config: SplittingConfig with strategy and grouping
            label_column: Column name for outcome label

        Returns:
            SplitResult with split indices and metadata
        """
        # Temporal ordering: sort by build time before splitting
        # This ensures train=oldest, val=middle, test=newest
        temporal_ordering = getattr(config, "temporal_ordering", True)
        if temporal_ordering and "build_started_at" in df.columns:
            df = df.sort_values("build_started_at", na_position="first").reset_index(
                drop=True
            )
            logger.info("Applied temporal ordering: sorted by build_started_at")

        # Prepare group column based on dimension
        group_column = self._prepare_group_column(df, config.group_by)

        # Create strategy and apply
        strategy = SplittingStrategyFactory.create(config)
        result = strategy.split(df, group_column, label_column)

        # Add metadata
        result.metadata["original_group_by"] = str(config.group_by)
        result.metadata["temporal_ordering"] = temporal_ordering

        return result

    def _prepare_group_column(
        self,
        df: pd.DataFrame,
        group_by: GroupByDimension,
    ) -> str:
        """
        Create/prepare the group column for splitting.

        Args:
            df: DataFrame
            group_by: Grouping dimension

        Returns:
            Column name to use for grouping
        """
        group_by_str = str(group_by) if not isinstance(group_by, str) else group_by

        if (
            group_by_str == "language_group"
            or group_by == GroupByDimension.LANGUAGE_GROUP
        ):
            return self._create_language_group_column(df)

        elif (
            group_by_str == "percentage_of_builds_before"
            or group_by == GroupByDimension.PERCENTAGE_OF_BUILDS_BEFORE
        ):
            return self._create_quartile_bins(df, "percentage_of_builds_before")

        elif (
            group_by_str == "number_of_builds_before"
            or group_by == GroupByDimension.NUMBER_OF_BUILDS_BEFORE
        ):
            return self._create_quartile_bins(df, "number_of_builds_before")

        elif group_by_str == "time_of_day" or group_by == GroupByDimension.TIME_OF_DAY:
            return self._create_time_of_day_bins(df)

        else:
            # Use column directly if exists
            if group_by_str in df.columns:
                return group_by_str
            raise ValueError(f"Unknown grouping dimension: {group_by}")

    def _create_language_group_column(self, df: pd.DataFrame) -> str:
        """Map primary_language to language_group (backend/fullstack/scripting/other)."""
        column_name = "_language_group"

        if "primary_language" in df.columns:
            df[column_name] = (
                df["primary_language"]
                .str.lower()
                .map(lambda x: self.LANGUAGE_GROUPS.get(x, "other"))
            )
        elif "language" in df.columns:
            df[column_name] = (
                df["language"]
                .str.lower()
                .map(lambda x: self.LANGUAGE_GROUPS.get(x, "other"))
            )
        else:
            # Default to "other" if no language column
            df[column_name] = "other"

        return column_name

    def _create_quartile_bins(self, df: pd.DataFrame, column: str) -> str:
        """Create 4 quartile bins for a numeric column."""
        bin_column = f"_{column}_bin"

        if column not in df.columns:
            # Create default bins
            df[bin_column] = "bin_1"
            return bin_column

        # Create quartile bins
        try:
            df[bin_column] = pd.qcut(
                df[column],
                q=4,
                labels=["bin_1", "bin_2", "bin_3", "bin_4"],
                duplicates="drop",
            )
        except ValueError:
            # If not enough unique values, use fixed bins
            min_val = df[column].min()
            max_val = df[column].max()
            if min_val == max_val:
                df[bin_column] = "bin_1"
            else:
                bins = [
                    min_val - 1,
                    min_val + (max_val - min_val) * 0.25,
                    min_val + (max_val - min_val) * 0.5,
                    min_val + (max_val - min_val) * 0.75,
                    max_val + 1,
                ]
                df[bin_column] = pd.cut(
                    df[column],
                    bins=bins,
                    labels=["bin_1", "bin_2", "bin_3", "bin_4"],
                )

        return bin_column

    def _create_time_of_day_bins(self, df: pd.DataFrame) -> str:
        """Create 4 time-of-day bins (night/morning/afternoon/evening)."""
        bin_column = "_time_of_day_bin"

        if "time_of_day" in df.columns:
            hour_col = df["time_of_day"]
        elif "hour" in df.columns:
            hour_col = df["hour"]
        elif "started_at" in df.columns:
            try:
                hour_col = pd.to_datetime(df["started_at"]).dt.hour
            except Exception:
                hour_col = pd.Series([12] * len(df))  # Default to afternoon
        else:
            hour_col = pd.Series([12] * len(df))  # Default to afternoon

        def hour_to_period(h):
            if 0 <= h < 6:
                return "night"
            elif 6 <= h < 12:
                return "morning"
            elif 12 <= h < 18:
                return "afternoon"
            else:
                return "evening"

        df[bin_column] = hour_col.apply(hour_to_period)
        return bin_column

    def get_split_statistics(
        self,
        df: pd.DataFrame,
        result: SplitResult,
        label_column: str = "outcome",
    ) -> Dict[str, Any]:
        """
        Calculate statistics for each split.

        Args:
            df: Original DataFrame
            result: SplitResult with indices
            label_column: Column name for labels

        Returns:
            Dict with statistics for train/val/test
        """
        stats = {
            "train": self._get_subset_stats(df, result.train_indices, label_column),
            "validation": self._get_subset_stats(df, result.val_indices, label_column),
            "test": self._get_subset_stats(df, result.test_indices, label_column),
        }
        return stats

    def _get_subset_stats(
        self,
        df: pd.DataFrame,
        indices: List[int],
        label_column: str,
    ) -> Dict[str, Any]:
        """Get statistics for a subset of data."""
        if not indices:
            return {
                "count": 0,
                "class_distribution": {},
                "positive_rate": 0.0,
            }

        subset = df.loc[indices]
        class_dist = subset[label_column].value_counts().to_dict()
        total = len(subset)
        positive = class_dist.get(1, 0)

        return {
            "count": total,
            "class_distribution": {str(k): v for k, v in class_dist.items()},
            "positive_rate": positive / total if total > 0 else 0.0,
        }
