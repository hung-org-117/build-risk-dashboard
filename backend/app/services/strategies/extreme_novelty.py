"""
Extreme Novelty Strategy - Target Group Label Isolation

Isolates all samples with Target Group + Label → Test set for zero-shot detection.
novelty_label MUST be 0 (success) or 1 (failure).
"""

import pandas as pd

from app.services.strategies.base import BaseSplittingStrategy, SplitResult


class ExtremeNoveltyStrategy(BaseSplittingStrategy):
    """
    Strategy C: Extreme Novelty (Target Group Label Isolation)

    Goal: Zero-shot risk detection.

    1. Extract ALL samples with Target Group + Label → Test Set
    2. Remaining pool → Stratified Train/Val

    novelty_label MUST be 0 (success) or 1 (failure) based on build_status_num.
    """

    def split(
        self,
        df: pd.DataFrame,
        group_column: str,
        label_column: str = "outcome",
    ) -> SplitResult:
        novelty_group = self.config.novelty_group
        novelty_label = self.config.novelty_label
        ratios = self.config.ratios or {"train": 0.8, "val": 0.2}

        # Validate novelty_label (MUST be 0 or 1)
        if novelty_label is None:
            novelty_label = 1  # Default: isolate failures
        if novelty_label not in (0, 1):
            raise ValueError(
                f"novelty_label must be 0 (success) or 1 (failure), got {novelty_label}"
            )

        # Validate novelty_group
        if novelty_group is None:
            raise ValueError("Extreme Novelty requires selecting a target group.")

        # Step 1: Extract ALL samples with novelty_group AND novelty_label → Test
        novelty_mask = (df[group_column] == novelty_group) & (
            df[label_column] == novelty_label
        )
        test_indices = df[novelty_mask].index.tolist()

        # Step 2: Remaining pool = Target Group (opposite label) + All other groups
        remaining_df = df[~novelty_mask]

        if len(remaining_df) < 3:
            raise ValueError(
                f"Not enough samples remaining after isolating target group. "
                f"Remaining: {len(remaining_df)}, need at least 3."
            )

        # Step 3: Stratified split on remaining pool (Train/Val only)
        train_ratio = ratios.get("train", 0.8) / (
            ratios.get("train", 0.8) + ratios.get("val", 0.2)
        )
        train_idx, val_idx, _ = self._get_stratified_split(
            remaining_df,
            label_column,
            train_ratio=train_ratio,
            val_ratio=1 - train_ratio,
        )

        return SplitResult(
            train_indices=train_idx,
            val_indices=val_idx,
            test_indices=test_indices,
            metadata={
                "strategy": "extreme_novelty",
                "group_column": group_column,
                "novelty_group": novelty_group,
                "novelty_label": novelty_label,
                "test_count": len(test_indices),
            },
        )
