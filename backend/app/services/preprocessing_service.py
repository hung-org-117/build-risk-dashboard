"""
Preprocessing Service - Strategy Pattern for ML Dataset preprocessing.

Strategies for:
- Missing features: fill, drop, mean (using sklearn.impute)
- Normalization: z_score, min_max, none (using sklearn.preprocessing)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import MinMaxScaler, StandardScaler

logger = logging.getLogger(__name__)

# Metadata columns that should not be preprocessed
METADATA_COLUMNS = frozenset(["id", "outcome", "repo_full_name", "primary_language"])


@dataclass
class PreprocessingConfig:
    """Configuration for preprocessing operations."""

    missing_strategy: str = "fill"  # fill, drop, mean
    fill_value: float = 0.0
    normalization_method: str = "none"  # none, z_score, min_max

    @classmethod
    def from_dict(cls, config: Any) -> "PreprocessingConfig":
        """
        Create config from dictionary or Entity object.

        Handles:
        1. Nested dict (YAML raw): {missing_features: {strategy: ...}, normalization: {method: ...}}
        2. Flat Entity/Dict (MLScenario): {missing_values_strategy: ..., normalization_method: ...}
        """
        if not config:
            return cls()

        # Convert entity/object to dict if needed
        if hasattr(config, "dict"):
            # Pydantic v1
            config_dict = config.dict()
        elif hasattr(config, "model_dump"):
            # Pydantic v2
            config_dict = config.model_dump()
        elif hasattr(config, "__dict__"):
            config_dict = config.__dict__
        elif isinstance(config, dict):
            config_dict = config
        else:
            return cls()

        # Check for nested structure (legacy/YAML raw style)
        if "missing_features" in config_dict or "normalization" in config_dict:
            missing_config = config_dict.get("missing_features", {})
            normalization_config = config_dict.get("normalization", {})

            return cls(
                missing_strategy=(
                    missing_config.get("strategy", "fill")
                    if isinstance(missing_config, dict)
                    else getattr(missing_config, "strategy", "fill")
                ),
                fill_value=(
                    missing_config.get("fill_value", 0)
                    if isinstance(missing_config, dict)
                    else getattr(missing_config, "fill_value", 0)
                ),
                normalization_method=(
                    normalization_config.get("method", "none")
                    if isinstance(normalization_config, dict)
                    else getattr(normalization_config, "method", "none")
                ),
            )

        # Handle Flat structure (MLScenario Entity style)
        # Entity field: missing_values_strategy -> Service field: missing_strategy
        return cls(
            missing_strategy=config_dict.get("missing_values_strategy", "fill"),
            fill_value=config_dict.get("fill_value", 0),
            normalization_method=config_dict.get("normalization_method", "none"),
        )


class MissingValuesStrategy(ABC):
    """Base class for missing values handling strategies."""

    @abstractmethod
    def handle(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        """Handle missing values in the specified columns."""
        pass


class FillMissingStrategy(MissingValuesStrategy):
    """Fill missing values with a constant using SimpleImputer."""

    def __init__(self, fill_value: float = 0.0):
        self.fill_value = fill_value

    def handle(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        if columns:
            df = df.copy()
            imputer = SimpleImputer(strategy="constant", fill_value=self.fill_value)
            df[columns] = imputer.fit_transform(df[columns])
            logger.info(f"Filled {len(columns)} columns with value {self.fill_value}")
        return df


class DropMissingStrategy(MissingValuesStrategy):
    """Drop rows with missing values."""

    def handle(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        if columns:
            original_len = len(df)
            df = df.dropna(subset=columns)
            dropped = original_len - len(df)
            logger.info(f"Dropped {dropped} rows with missing values")
        return df


class MeanFillMissingStrategy(MissingValuesStrategy):
    """Fill missing values with column mean using SimpleImputer."""

    def handle(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        if columns:
            df = df.copy()
            # Select numeric columns only for mean imputation
            numeric_cols = [
                c
                for c in columns
                if df[c].dtype in ["float64", "int64", "float32", "int32"]
            ]
            if numeric_cols:
                imputer = SimpleImputer(strategy="mean")
                df[numeric_cols] = imputer.fit_transform(df[numeric_cols])
                logger.info(f"Filled {len(numeric_cols)} columns with column means")
        return df


class NormalizationStrategy(ABC):
    """Base class for normalization strategies."""

    @abstractmethod
    def normalize(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        """Normalize the specified columns."""
        pass


class NoNormalizationStrategy(NormalizationStrategy):
    """No normalization - pass through."""

    def normalize(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        return df


class ZScoreNormalizationStrategy(NormalizationStrategy):
    """Z-score (standardization) normalization using StandardScaler."""

    def normalize(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        if not columns:
            return df

        df = df.copy()
        scaler = StandardScaler()
        df[columns] = scaler.fit_transform(df[columns])

        logger.info(f"Applied z-score normalization to {len(columns)} columns")
        return df


class MinMaxNormalizationStrategy(NormalizationStrategy):
    """Min-max normalization (0-1 scaling) using MinMaxScaler."""

    def normalize(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        if not columns:
            return df

        df = df.copy()
        scaler = MinMaxScaler()
        df[columns] = scaler.fit_transform(df[columns])

        logger.info(f"Applied min-max normalization to {len(columns)} columns")
        return df


class MissingValuesStrategyFactory:
    """Factory for creating missing values strategies."""

    STRATEGIES = {
        "fill": FillMissingStrategy,
        "drop": DropMissingStrategy,
        "mean": MeanFillMissingStrategy,
    }

    @classmethod
    def create(
        cls, strategy_name: str, fill_value: float = 0.0
    ) -> MissingValuesStrategy:
        strategy_class = cls.STRATEGIES.get(strategy_name, FillMissingStrategy)
        if strategy_class == FillMissingStrategy:
            return strategy_class(fill_value)
        return strategy_class()


class NormalizationStrategyFactory:
    """Factory for creating normalization strategies."""

    STRATEGIES = {
        "none": NoNormalizationStrategy,
        "z_score": ZScoreNormalizationStrategy,
        "min_max": MinMaxNormalizationStrategy,
    }

    @classmethod
    def create(cls, method_name: str) -> NormalizationStrategy:
        strategy_class = cls.STRATEGIES.get(method_name, NoNormalizationStrategy)
        return strategy_class()


class PreprocessingService:
    """
    Service for preprocessing ML datasets.

    Uses Strategy Pattern for flexible missing values and normalization handling.
    """

    def __init__(self, config: Optional[PreprocessingConfig] = None):
        self.config = config or PreprocessingConfig()
        self._missing_strategy = MissingValuesStrategyFactory.create(
            self.config.missing_strategy, self.config.fill_value
        )
        self._normalization_strategy = NormalizationStrategyFactory.create(
            self.config.normalization_method
        )

    @classmethod
    def from_dict(cls, config_dict: Optional[Dict[str, Any]]) -> "PreprocessingService":
        """Create service from dictionary config."""
        config = PreprocessingConfig.from_dict(config_dict)
        return cls(config)

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply all preprocessing steps to the DataFrame.

        Steps:
        1. Handle missing values
        2. Apply normalization

        Args:
            df: Input DataFrame with features

        Returns:
            Preprocessed DataFrame
        """
        # Get feature columns (exclude metadata)
        feature_cols = [c for c in df.columns if c not in METADATA_COLUMNS]

        # Get numeric columns for normalization
        numeric_cols = [
            c
            for c in feature_cols
            if df[c].dtype in ["float64", "int64", "float32", "int32"]
        ]

        # Step 1: Handle missing values
        df = self._missing_strategy.handle(df, feature_cols)

        # Step 2: Apply normalization
        df = self._normalization_strategy.normalize(df, numeric_cols)

        return df
