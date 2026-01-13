"""
Splitting Strategy Factory - Creates strategy instances from config.
"""

from app.entities.enums import SplitStrategy
from app.entities.training_dataset_export import ExportSplittingConfig
from app.services.strategies.base import BaseSplittingStrategy
from app.services.strategies.extreme_novelty import ExtremeNoveltyStrategy
from app.services.strategies.imbalanced_train import ImbalancedTrainStrategy
from app.services.strategies.leave_one_out import LeaveOneOutStrategy
from app.services.strategies.leave_two_out import LeaveTwoOutStrategy
from app.services.strategies.random import RandomSplitStrategy
from app.services.strategies.stratified import StratifiedSplitStrategy
from app.services.strategies.stratified_within_group import (
    StratifiedWithinGroupStrategy,
)
from app.services.strategies.time_series import TimeSeriesSplitStrategy


class SplittingStrategyFactory:
    """Factory for creating splitting strategy instances."""

    STRATEGY_MAP = {
        SplitStrategy.RANDOM_SPLIT: RandomSplitStrategy,
        SplitStrategy.TIME_SERIES_SPLIT: TimeSeriesSplitStrategy,
        SplitStrategy.STRATIFIED_SPLIT: StratifiedSplitStrategy,
        SplitStrategy.STRATIFIED_WITHIN_GROUP: StratifiedWithinGroupStrategy,
        SplitStrategy.LEAVE_ONE_OUT: LeaveOneOutStrategy,
        SplitStrategy.LEAVE_TWO_OUT: LeaveTwoOutStrategy,
        SplitStrategy.IMBALANCED_TRAIN: ImbalancedTrainStrategy,
        SplitStrategy.EXTREME_NOVELTY: ExtremeNoveltyStrategy,
    }

    @classmethod
    def create(cls, config: ExportSplittingConfig) -> BaseSplittingStrategy:
        """
        Create a splitting strategy instance based on config.

        Args:
            config: ExportSplittingConfig with strategy type

        Returns:
            BaseSplittingStrategy instance

        Raises:
            ValueError: If strategy type is unknown
        """
        strategy_type = config.strategy
        strategy_class = cls.STRATEGY_MAP.get(strategy_type)

        if strategy_class is None:
            raise ValueError(f"Unknown splitting strategy: {strategy_type}")

        return strategy_class(config)
