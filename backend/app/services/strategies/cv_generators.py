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
