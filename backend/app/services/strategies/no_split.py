"""
No Split Strategy - Exports entire dataset without splitting.

Use case: When user wants to export full dataset as a single file
for custom preprocessing or external train/test splitting.
"""

import pandas as pd

from app.services.strategies.base import BaseSplittingStrategy, SplitResult


class NoSplitStrategy(BaseSplittingStrategy):
    """
    Strategy that does not split the data.

    All records go to 'train' split (used as the main container).
    Validation and test splits are empty.
    """

    def split(
        self,
        df: pd.DataFrame,
        group_column: str,
        label_column: str = "outcome",
    ) -> SplitResult:
        """Return all indices as 'train', with empty val/test."""
        all_indices = df.index.tolist()

        return SplitResult(
            train_indices=all_indices,
            val_indices=[],
            test_indices=[],
            metadata={
                "strategy": "no_split",
                "total_records": len(all_indices),
            },
        )
