"""
Splitting Strategies Package

This package provides modular splitting strategies for ML training datasets.
Each strategy is in a separate file for better organization and maintainability.

For CV strategies (L1GO, L2GO, etc.), use CVGeneratorFactory.
For single-split strategies (random, stratified), use SplittingStrategyFactory.
"""

from app.services.strategies.base import BaseSplittingStrategy, SplitResult
from app.services.strategies.cv_factory import CVGeneratorFactory
from app.services.strategies.cv_generators import (
    BaseCVGenerator,
    CVFold,
    L1GOCrossValidator,
    L2GOCrossValidator,
)
from app.services.strategies.factory import CV_STRATEGIES, SplittingStrategyFactory
from app.services.strategies.random import RandomSplitStrategy
from app.services.strategies.stratified import StratifiedSplitStrategy
from app.services.strategies.stratified_within_group import (
    StratifiedWithinGroupStrategy,
)
from app.services.strategies.time_series import TimeSeriesSplitStrategy

__all__ = [
    # Base classes
    "BaseSplittingStrategy",
    "SplitResult",
    "BaseCVGenerator",
    "CVFold",
    # Single-split strategies
    "RandomSplitStrategy",
    "TimeSeriesSplitStrategy",
    "StratifiedSplitStrategy",
    "StratifiedWithinGroupStrategy",
    # CV generators
    "L1GOCrossValidator",
    "L2GOCrossValidator",
    # Factories
    "SplittingStrategyFactory",
    "CVGeneratorFactory",
    "CV_STRATEGIES",
]
