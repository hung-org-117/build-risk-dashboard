"""
Stratified Within Group Strategy - Stratified split within each group.
"""

import pandas as pd

from app.services.strategies.base import BaseSplittingStrategy, SplitResult


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
