"""
Leave-One-Group-Out (L1GO) Strategy

Requires ≥3 groups. 1 group → Test, 1 group → Val, remaining → Train.
Raises ValueError if prerequisites are not met.
"""

import pandas as pd

from app.services.strategies.base import BaseSplittingStrategy, SplitResult


class LeaveOneOutStrategy(BaseSplittingStrategy):
    """
    Strategy A: Leave-One-Group-Out (L1GO)

    Requires ≥3 groups. Raises ValueError if not enough groups.
    1 group → Test
    1 group → Val
    Remaining groups → Train
    """

    def split(
        self,
        df: pd.DataFrame,
        group_column: str,
        label_column: str = "outcome",
    ) -> SplitResult:
        test_groups = self.config.test_groups or []
        val_groups = self.config.val_groups or []

        all_groups = df[group_column].unique().tolist()

        # BLOCK: Require at least 3 groups
        if len(all_groups) < 3:
            raise ValueError(
                f"L1GO requires at least 3 groups, but only {len(all_groups)} found. "
                f"Please select a different grouping dimension or use a different strategy."
            )

        # Validate user selection
        if not test_groups:
            raise ValueError("L1GO requires selecting 1 group for Test set.")
        if not val_groups:
            raise ValueError("L1GO requires selecting 1 group for Validation set.")
        if set(test_groups) & set(val_groups):
            raise ValueError("Test and Validation groups must be different.")

        train_groups = [g for g in all_groups if g not in test_groups + val_groups]

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
