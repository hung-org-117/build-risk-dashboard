"""
Cross-Validation Generators for ML Splitting Strategies.

This module provides automated CV generators that iterate through all possible folds,
replacing manual group-selection strategies.

Generators:
- L1GOCrossValidator: Leave-One-Group-Out CV
- L2GOCrossValidator: Leave-Two-Groups-Out CV
- ExtremeNoveltyCrossValidator: Target Label Isolation CV
- ImbalancedKFoldCV: Stratified K-Fold with Label Imbalancing
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Dict, Iterator, List, Optional

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, StratifiedShuffleSplit

logger = logging.getLogger(__name__)


@dataclass
class CVFold:
    """Result of a single CV fold iteration."""

    fold_id: str
    train_indices: List[int]
    val_indices: List[int]
    test_indices: List[int]
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseCVGenerator(ABC):
    """
    Base class for all cross-validation generators.

    Subclasses implement __iter__ to yield CVFold objects for each fold.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        group_column: str,
        label_column: str = "outcome",
        internal_val_ratio: float = 0.2,
        random_state: int = 42,
    ):
        self.df = df
        self.group_column = group_column
        self.label_column = label_column
        self.internal_val_ratio = internal_val_ratio
        self.random_state = random_state
        self.groups = df[group_column].unique().tolist()

    @abstractmethod
    def __iter__(self) -> Iterator[CVFold]:
        """Yield CVFold objects for each iteration."""
        pass

    @abstractmethod
    def __len__(self) -> int:
        """Return total number of folds."""
        pass

    def _stratified_train_val_split(
        self,
        pool_df: pd.DataFrame,
    ) -> tuple[List[int], List[int]]:
        """
        Split pool into train/val using stratified sampling.

        Args:
            pool_df: DataFrame to split

        Returns:
            Tuple of (train_indices, val_indices)
        """
        if len(pool_df) < 2:
            return pool_df.index.tolist(), []

        indices = pool_df.index.tolist()
        labels = pool_df[self.label_column].values

        # Check if stratification is possible
        unique_labels, counts = np.unique(labels, return_counts=True)
        if counts.min() < 2:
            # Fall back to random split
            np.random.seed(self.random_state)
            np.random.shuffle(indices)
            split_point = int(len(indices) * (1 - self.internal_val_ratio))
            return indices[:split_point], indices[split_point:]

        splitter = StratifiedShuffleSplit(
            n_splits=1,
            test_size=self.internal_val_ratio,
            random_state=self.random_state,
        )

        train_idx, val_idx = next(splitter.split(indices, labels))
        return [indices[i] for i in train_idx], [indices[i] for i in val_idx]


class L1GOCrossValidator(BaseCVGenerator):
    """
    Leave-One-Group-Out Cross-Validation.

    For each group G in total N groups:
    - Test Set: All samples from group G
    - Train/Val Pool: All samples from remaining N-1 groups
    - Internal Split: Stratified split by internal_val_ratio

    Yields N folds total.
    """

    def __len__(self) -> int:
        return len(self.groups)

    def __iter__(self) -> Iterator[CVFold]:
        for i, test_group in enumerate(self.groups):
            # Test = current group
            test_mask = self.df[self.group_column] == test_group
            test_indices = self.df[test_mask].index.tolist()

            # Pool = all other groups
            pool_df = self.df[~test_mask]

            if len(pool_df) < 2:
                logger.warning(f"L1GO fold {i}: Not enough samples in pool, skipping")
                continue

            train_indices, val_indices = self._stratified_train_val_split(pool_df)

            yield CVFold(
                fold_id=f"l1go_fold_{i}_{test_group}",
                train_indices=train_indices,
                val_indices=val_indices,
                test_indices=test_indices,
                metadata={
                    "strategy": "l1go_cv",
                    "test_group": str(test_group),
                    "fold_index": i,
                    "total_folds": len(self.groups),
                },
            )


class L2GOCrossValidator(BaseCVGenerator):
    """
    Leave-Two-Groups-Out Cross-Validation.

    For each pair (G1, G2) from C(N, 2) combinations:
    - Test Set: All samples from G1 + G2
    - Train/Val Pool: All samples from remaining N-2 groups
    - Internal Split: Stratified split by internal_val_ratio

    Yields C(N, 2) folds total.
    """

    def __len__(self) -> int:
        n = len(self.groups)
        if n < 3:
            return 0
        return n * (n - 1) // 2  # C(n, 2)

    def __iter__(self) -> Iterator[CVFold]:
        if len(self.groups) < 3:
            logger.warning("L2GO requires at least 3 groups")
            return

        for i, (g1, g2) in enumerate(combinations(self.groups, 2)):
            # Test = both groups
            test_mask = self.df[self.group_column].isin([g1, g2])
            test_indices = self.df[test_mask].index.tolist()

            # Pool = remaining groups
            pool_df = self.df[~test_mask]

            if len(pool_df) < 2:
                logger.warning(f"L2GO fold {i}: Not enough samples in pool, skipping")
                continue

            train_indices, val_indices = self._stratified_train_val_split(pool_df)

            yield CVFold(
                fold_id=f"l2go_fold_{i}_{g1}_{g2}",
                train_indices=train_indices,
                val_indices=val_indices,
                test_indices=test_indices,
                metadata={
                    "strategy": "l2go_cv",
                    "test_groups": [str(g1), str(g2)],
                    "fold_index": i,
                    "total_folds": len(self),
                },
            )


class ExtremeNoveltyCrossValidator(BaseCVGenerator):
    """
    Extreme Novelty (Target Label Isolation) Cross-Validation.

    For each group G:
    - Test Set: ALL samples with target_label from group G
    - Train/Val Pool: Remaining samples (G's opposite label + all other groups)
    - Internal Split: Stratified split by internal_val_ratio

    Evaluates zero-shot detection capability per group.
    Skips groups with no target_label samples.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        group_column: str,
        label_column: str = "outcome",
        target_label: int = 1,
        internal_val_ratio: float = 0.2,
        random_state: int = 42,
    ):
        super().__init__(
            df, group_column, label_column, internal_val_ratio, random_state
        )
        self.target_label = target_label
        # Pre-calculate valid groups (those with target_label samples)
        self._valid_groups = [
            g
            for g in self.groups
            if len(df[(df[group_column] == g) & (df[label_column] == target_label)]) > 0
        ]

    def __len__(self) -> int:
        return len(self._valid_groups)

    def __iter__(self) -> Iterator[CVFold]:
        for i, target_group in enumerate(self._valid_groups):
            # Test = ALL target_label samples from target_group
            test_mask = (self.df[self.group_column] == target_group) & (
                self.df[self.label_column] == self.target_label
            )
            test_indices = self.df[test_mask].index.tolist()

            # Pool = everything else (target_group's opposite label + other groups)
            pool_df = self.df[~test_mask]

            if len(pool_df) < 2:
                logger.warning(
                    f"Extreme Novelty fold {i}: Not enough samples in pool, skipping"
                )
                continue

            train_indices, val_indices = self._stratified_train_val_split(pool_df)

            yield CVFold(
                fold_id=f"novelty_fold_{i}_{target_group}",
                train_indices=train_indices,
                val_indices=val_indices,
                test_indices=test_indices,
                metadata={
                    "strategy": "extreme_novelty_cv",
                    "target_group": str(target_group),
                    "target_label": self.target_label,
                    "test_count": len(test_indices),
                    "fold_index": i,
                    "total_folds": len(self._valid_groups),
                },
            )


class ImbalancedKFoldCV(BaseCVGenerator):
    """
    Imbalanced Train K-Fold Cross-Validation.

    Standard Stratified K-Fold with train set manipulation:
    - For each fold k in K folds:
      - Test Set: k-th fold
      - Train/Val Pool: Remaining K-1 folds
      - Internal Split: Stratified split by internal_val_ratio
      - Train Manipulation: Drop X% of target_label from train set

    Evaluates model robustness under data scarcity.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        group_column: str,  # Unused but kept for interface consistency
        label_column: str = "outcome",
        n_folds: int = 5,
        drop_rate: float = 0.5,
        drop_label: int = 1,
        internal_val_ratio: float = 0.1,
        random_state: int = 42,
    ):
        # Note: group_column is not used in K-Fold CV
        super().__init__(
            df, group_column, label_column, internal_val_ratio, random_state
        )
        self.n_folds = n_folds
        self.drop_rate = drop_rate
        self.drop_label = drop_label

    def __len__(self) -> int:
        return self.n_folds

    def __iter__(self) -> Iterator[CVFold]:
        skf = StratifiedKFold(
            n_splits=self.n_folds, shuffle=True, random_state=self.random_state
        )
        labels = self.df[self.label_column].values
        indices = np.arange(len(self.df))

        for i, (train_val_idx, test_idx) in enumerate(skf.split(indices, labels)):
            # Test = k-th fold
            test_indices = self.df.iloc[test_idx].index.tolist()

            # Train/Val pool = remaining folds
            pool_df = self.df.iloc[train_val_idx]

            # Split pool into train/val
            train_indices, val_indices = self._stratified_train_val_split(pool_df)

            # Manipulate train set: drop X% of drop_label
            train_df = self.df.loc[train_indices]
            label_mask = train_df[self.label_column] == self.drop_label
            drop_candidates = train_df[label_mask].index.tolist()
            keep_candidates = train_df[~label_mask].index.tolist()

            n_drop = int(len(drop_candidates) * self.drop_rate)
            np.random.seed(self.random_state + i)

            if n_drop > 0 and len(drop_candidates) > n_drop:
                kept_label = list(
                    np.random.choice(
                        drop_candidates,
                        size=len(drop_candidates) - n_drop,
                        replace=False,
                    )
                )
            else:
                kept_label = drop_candidates

            final_train_indices = keep_candidates + kept_label

            yield CVFold(
                fold_id=f"imbalanced_fold_{i}",
                train_indices=final_train_indices,
                val_indices=val_indices,
                test_indices=test_indices,
                metadata={
                    "strategy": "imbalanced_kfold_cv",
                    "fold_index": i,
                    "total_folds": self.n_folds,
                    "drop_rate": self.drop_rate,
                    "drop_label": self.drop_label,
                    "original_train_count": len(train_indices),
                    "final_train_count": len(final_train_indices),
                    "dropped_count": len(train_indices) - len(final_train_indices),
                },
            )
