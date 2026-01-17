"""
Splitting Strategy Factory - Creates strategy instances from config.

For CV strategies (L1GO, L2GO, etc.), use CVGeneratorFactory instead.
This factory handles non-CV strategies (random, stratified, time_series).
"""

from app.entities.enums import SplitStrategy
from app.entities.training_dataset_export import ExportSplittingConfig
from app.services.strategies.base import BaseSplittingStrategy
from app.services.strategies.no_split import NoSplitStrategy
from app.services.strategies.random import RandomSplitStrategy
from app.services.strategies.stratified import StratifiedSplitStrategy
from app.services.strategies.stratified_within_group import (
    StratifiedWithinGroupStrategy,
)
from app.services.strategies.time_series import TimeSeriesSplitStrategy

# CV strategies that require the CV generator (not single-split)
CV_STRATEGIES = {
    SplitStrategy.L1GO_CV,
    SplitStrategy.L2GO_CV,
}


class SplittingStrategyFactory:
    """Factory for creating splitting strategy instances."""

    STRATEGY_MAP = {
        SplitStrategy.NO_SPLIT: NoSplitStrategy,
        SplitStrategy.RANDOM_SPLIT: RandomSplitStrategy,
        SplitStrategy.TIME_SERIES_SPLIT: TimeSeriesSplitStrategy,
        SplitStrategy.STRATIFIED_SPLIT: StratifiedSplitStrategy,
        SplitStrategy.STRATIFIED_WITHIN_GROUP: StratifiedWithinGroupStrategy,
    }

    @classmethod
    def is_cv_strategy(cls, strategy: SplitStrategy) -> bool:
        """Check if strategy is a CV strategy requiring multi-fold generation."""
        return strategy in CV_STRATEGIES

    @classmethod
    def create(cls, config: ExportSplittingConfig) -> BaseSplittingStrategy:
        """
        Create a splitting strategy instance based on config.

        Args:
            config: ExportSplittingConfig with strategy type

        Returns:
            BaseSplittingStrategy instance

        Raises:
            ValueError: If strategy type is unknown or is a CV strategy
        """
        strategy_type = config.strategy

        if cls.is_cv_strategy(strategy_type):
            raise ValueError(
                f"Strategy {strategy_type} is a CV strategy. "
                f"Use CVGeneratorFactory.create() instead."
            )

        strategy_class = cls.STRATEGY_MAP.get(strategy_type)

        if strategy_class is None:
            raise ValueError(f"Unknown splitting strategy: {strategy_type}")

        return strategy_class(config)
