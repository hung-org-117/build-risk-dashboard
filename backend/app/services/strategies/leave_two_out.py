"""
Leave-Two-Groups-Out (L2GO) Strategy

Requires ≥4 groups. 2 groups → Test, 1 group → Val, remaining → Train.
Raises ValueError if prerequisites are not met.
"""

import pandas as pd

from app.services.strategies.base import BaseSplittingStrategy, SplitResult


class LeaveTwoOutStrategy(BaseSplittingStrategy):
    """
    Strategy B: Leave-Two-Groups-Out (L2GO)

    Requires ≥4 groups. Raises ValueError if not enough groups.
    2 groups → Test
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

        # BLOCK: Require at least 4 groups
        if len(all_groups) < 4:
            raise ValueError(
                f"L2GO requires at least 4 groups, but only {len(all_groups)} found. "
                f"Please select a different grouping dimension or use a different strategy."
            )

        # Validate user selection
        if len(test_groups) != 2:
            raise ValueError("L2GO requires selecting exactly 2 groups for Test set.")
        if not val_groups:
            raise ValueError("L2GO requires selecting 1 group for Validation set.")
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
                "strategy": "leave_two_out",
                "group_column": group_column,
                "test_groups": test_groups,
                "val_groups": val_groups,
                "train_groups": train_groups,
            },
        )
