"""
CV Generator Factory - Creates CV generator instances from config.
"""

from typing import Union

import pandas as pd

from app.entities.enums import SplitStrategy
from app.entities.training_dataset_export import ExportSplittingConfig
from app.services.strategies.cv_generators import (
    BaseCVGenerator,
    ExtremeNoveltyCrossValidator,
    ImbalancedKFoldCV,
    L1GOCrossValidator,
    L2GOCrossValidator,
)


class CVGeneratorFactory:
    """Factory for creating CV generator instances."""

    @classmethod
    def create(
        cls,
        df: pd.DataFrame,
        group_column: str,
        config: ExportSplittingConfig,
        label_column: str = "outcome",
    ) -> BaseCVGenerator:
        """
        Create a CV generator instance based on config.

        Args:
            df: DataFrame with feature data
            group_column: Column name for grouping
            config: ExportSplittingConfig with strategy type
            label_column: Column name for outcome label

        Returns:
            BaseCVGenerator instance

        Raises:
            ValueError: If strategy type is not a CV strategy
        """
        strategy = config.strategy
        internal_val_ratio = config.internal_val_ratio
        random_state = 42

        if strategy == SplitStrategy.L1GO_CV:
            return L1GOCrossValidator(
                df=df,
                group_column=group_column,
                label_column=label_column,
                internal_val_ratio=internal_val_ratio,
                random_state=random_state,
            )

        elif strategy == SplitStrategy.L2GO_CV:
            return L2GOCrossValidator(
                df=df,
                group_column=group_column,
                label_column=label_column,
                internal_val_ratio=internal_val_ratio,
                random_state=random_state,
            )

        elif strategy == SplitStrategy.EXTREME_NOVELTY_CV:
            return ExtremeNoveltyCrossValidator(
                df=df,
                group_column=group_column,
                label_column=label_column,
                target_label=config.novelty_target_label,
                internal_val_ratio=internal_val_ratio,
                random_state=random_state,
            )

        elif strategy == SplitStrategy.IMBALANCED_KFOLD_CV:
            return ImbalancedKFoldCV(
                df=df,
                group_column=group_column,
                label_column=label_column,
                n_folds=config.n_folds,
                drop_rate=config.imbalance_drop_rate,
                drop_label=config.imbalance_drop_label,
                internal_val_ratio=internal_val_ratio,
                random_state=random_state,
            )

        else:
            raise ValueError(
                f"Strategy {strategy} is not a CV strategy. "
                f"Use SplittingStrategyFactory.create() instead."
            )
