"""
Imbalanced Train Strategy - Robustness Check

Stratified split first, then removes X% of Label 1 from training set only.
Val and Test keep natural distribution.
"""

import numpy as np
import pandas as pd

from app.services.strategies.base import BaseSplittingStrategy, SplitResult


class ImbalancedTrainStrategy(BaseSplittingStrategy):
    """
    Strategy D: Imbalanced Train (Robustness Check)

    1. Initial Split: Stratified split entire dataset into Train/Val/Test
    2. Train Manipulation: Remove X% of Label 1 from training set only
    3. Val and Test keep natural distribution
    """

    def split(
        self,
        df: pd.DataFrame,
        group_column: str,
        label_column: str = "outcome",
    ) -> SplitResult:
        ratios = self.config.ratios or {"train": 0.7, "val": 0.15, "test": 0.15}
        reduce_ratio = getattr(self.config, "imbalance_reduction_rate", None)
        if reduce_ratio is None:
            reduce_ratio = self.config.reduce_ratio or 0.5
        reduce_label = self.config.reduce_label
        if reduce_label is None:
            reduce_label = 1

        # Step 1: Standard stratified split on ENTIRE dataset
        train_idx, val_idx, test_idx = self._get_stratified_split(
            df,
            label_column,
            train_ratio=ratios.get("train", 0.7),
            val_ratio=ratios.get("val", 0.15),
        )

        # Step 2: Manipulate training set only
        train_df = df.loc[train_idx]
        label_mask = train_df[label_column] == reduce_label
        reduce_indices = train_df[label_mask].index.tolist()
        keep_indices = train_df[~label_mask].index.tolist()

        # Keep (1 - reduce_ratio) of reduce_label samples
        n_keep = int(len(reduce_indices) * (1 - reduce_ratio))
        np.random.seed(42)
        kept_reduce = (
            list(np.random.choice(reduce_indices, size=n_keep, replace=False))
            if n_keep > 0
            else []
        )

        final_train = keep_indices + kept_reduce

        return SplitResult(
            train_indices=final_train,
            val_indices=val_idx,
            test_indices=test_idx,
            metadata={
                "strategy": "imbalanced_train",
                "reduce_label": reduce_label,
                "reduce_ratio": reduce_ratio,
                "original_train_count": len(train_idx),
                "final_train_count": len(final_train),
            },
        )
