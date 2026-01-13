"""
Stratified Split Strategy - Maintains label distribution in each split.
"""

import pandas as pd

from app.services.strategies.base import BaseSplittingStrategy, SplitResult


class StratifiedSplitStrategy(BaseSplittingStrategy):
    """
    Stratified Split: Maintains label distribution in each split.
    Like random split but preserves class balance.
    """

    def split(
        self,
        df: pd.DataFrame,
        group_column: str,
        label_column: str = "outcome",
    ) -> SplitResult:
        ratios = self.config.ratios or {"train": 0.7, "val": 0.15, "test": 0.15}

        train_idx, val_idx, test_idx = self._get_stratified_split(
            df,
            label_column,
            train_ratio=ratios.get("train", 0.7),
            val_ratio=ratios.get("val", 0.15),
        )

        return SplitResult(
            train_indices=train_idx,
            val_indices=val_idx,
            test_indices=test_idx,
            metadata={
                "strategy": "stratified_split",
                "ratios": ratios,
            },
        )
