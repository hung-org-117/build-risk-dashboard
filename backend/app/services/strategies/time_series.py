"""
Time Series Split Strategy - Splits based on chronological order.
"""

import pandas as pd

from app.services.strategies.base import BaseSplittingStrategy, SplitResult


class TimeSeriesSplitStrategy(BaseSplittingStrategy):
    """
    Time Series Split: Splits based on time (Train < Val < Test).
    Sorts by build_started_at ASC to ensure chronological ordering.
    """

    def split(
        self,
        df: pd.DataFrame,
        group_column: str,
        label_column: str = "outcome",
    ) -> SplitResult:
        ratios = self.config.ratios or {"train": 0.7, "val": 0.15, "test": 0.15}

        # Sort by build time ASC to ensure chronological order
        if "build_started_at" in df.columns:
            df = df.sort_values("build_started_at", na_position="first").reset_index(
                drop=True
            )

        indices = df.index.tolist()
        n = len(indices)
        train_end = int(n * ratios.get("train", 0.7))
        val_end = int(n * (ratios.get("train", 0.7) + ratios.get("val", 0.15)))

        return SplitResult(
            train_indices=indices[:train_end],
            val_indices=indices[train_end:val_end],
            test_indices=indices[val_end:],
            metadata={
                "strategy": "time_series_split",
                "ratios": ratios,
                "note": "Train=oldest, Val=middle, Test=newest",
            },
        )
