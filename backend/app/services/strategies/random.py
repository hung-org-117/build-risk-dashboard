"""
Random Split Strategy - Pure random assignment without stratification.
"""

import numpy as np
import pandas as pd

from app.services.strategies.base import BaseSplittingStrategy, SplitResult


class RandomSplitStrategy(BaseSplittingStrategy):
    """
    Random Split: Randomly assigns builds to sets based on ratios.
    No stratification or grouping - pure random assignment.
    """

    def split(
        self,
        df: pd.DataFrame,
        group_column: str,
        label_column: str = "outcome",
    ) -> SplitResult:
        ratios = self.config.ratios or {"train": 0.7, "val": 0.15, "test": 0.15}
        indices = df.index.tolist()

        np.random.seed(42)
        np.random.shuffle(indices)

        n = len(indices)
        train_end = int(n * ratios.get("train", 0.7))
        val_end = int(n * (ratios.get("train", 0.7) + ratios.get("val", 0.15)))

        return SplitResult(
            train_indices=indices[:train_end],
            val_indices=indices[train_end:val_end],
            test_indices=indices[val_end:],
            metadata={
                "strategy": "random_split",
                "ratios": ratios,
            },
        )
