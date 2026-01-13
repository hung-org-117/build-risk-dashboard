"""
Splitting Strategies Package

This package provides modular splitting strategies for ML training datasets.
Each strategy is in a separate file for better organization and maintainability.
"""

from app.services.strategies.base import BaseSplittingStrategy, SplitResult
from app.services.strategies.extreme_novelty import ExtremeNoveltyStrategy
from app.services.strategies.factory import SplittingStrategyFactory
from app.services.strategies.imbalanced_train import ImbalancedTrainStrategy
from app.services.strategies.leave_one_out import LeaveOneOutStrategy
from app.services.strategies.leave_two_out import LeaveTwoOutStrategy
from app.services.strategies.random import RandomSplitStrategy
from app.services.strategies.stratified import StratifiedSplitStrategy
from app.services.strategies.stratified_within_group import (
    StratifiedWithinGroupStrategy,
)
from app.services.strategies.time_series import TimeSeriesSplitStrategy

__all__ = [
    "BaseSplittingStrategy",
    "SplitResult",
    "RandomSplitStrategy",
    "TimeSeriesSplitStrategy",
    "StratifiedSplitStrategy",
    "StratifiedWithinGroupStrategy",
    "LeaveOneOutStrategy",
    "LeaveTwoOutStrategy",
    "ImbalancedTrainStrategy",
    "ExtremeNoveltyStrategy",
    "SplittingStrategyFactory",
    # Grouping utilities
    "create_language_column",
    "create_equal_width_bins",
    "create_time_slots",
    "get_group_label",
]
