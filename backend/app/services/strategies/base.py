"""
Base classes and data structures for splitting strategies.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit

from app.entities.training_dataset_export import ExportSplittingConfig

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

    def __init__(self, config: ExportSplittingConfig):
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
        if len(temp_indices) < 2 or counts_temp.min() < 2:
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
