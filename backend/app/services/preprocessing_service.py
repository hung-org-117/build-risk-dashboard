"""
Preprocessing Service - Strategy Pattern for ML Dataset preprocessing.

Strategies for:
- Missing features: fill, drop, mean (using sklearn.impute)
- Normalization: z_score, min_max, none (using sklearn.preprocessing)

Refactored to support Split-Apply pattern (Fit on Train, Transform on Test).
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler

from app.tasks.pipeline.constants import DEFAULT_FEATURES

logger = logging.getLogger(__name__)

METADATA_COLUMNS = DEFAULT_FEATURES


@dataclass
class PreprocessingConfig:
    """Configuration for preprocessing operations."""

    missing_strategy: str = "fill_zero"  # drop_row, fill_mean, fill_median, fill_zero
    fill_value: float = 0.0
    normalization_method: str = "none"  # none, z_score, min_max, robust

    @classmethod
    def from_dict(cls, config: Any) -> "PreprocessingConfig":
        """
        Create config from dictionary or Entity object.
        """
        if not config:
            return cls()

        # Convert entity/object to dict if needed
        if hasattr(config, "dict"):
            config_dict = config.dict()
        elif hasattr(config, "model_dump"):
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
                    missing_config.get("strategy", "fill_zero")
                    if isinstance(missing_config, dict)
                    else getattr(missing_config, "strategy", "fill_zero")
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

        # Handle Flat structure
        return cls(
            missing_strategy=config_dict.get("missing_values_strategy", "fill_zero"),
            fill_value=config_dict.get("fill_value", 0),
            normalization_method=config_dict.get(
                "normalization", config_dict.get("normalization_method", "none")
            ),
        )


class PreprocessingStrategy(ABC):
    """Base class for stateful preprocessing strategies."""

    def __init__(self):
        self.is_fitted = False

    @abstractmethod
    def fit(self, df: pd.DataFrame, columns: List[str]) -> "PreprocessingStrategy":
        """Calculate and store parameters from the dataframe."""
        pass

    @abstractmethod
    def transform(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        """Apply stored parameters to the dataframe."""
        pass

    def fit_transform(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        """Fit and transform in one step."""
        return self.fit(df, columns).transform(df, columns)


class MissingValuesStrategy(PreprocessingStrategy):
    """Base class for missing values handling strategies."""

    pass


class FillMissingStrategy(MissingValuesStrategy):
    """Fill missing values with a constant."""

    def __init__(self, fill_value: float = 0.0):
        super().__init__()
        self.fill_value = fill_value

    def fit(self, df: pd.DataFrame, columns: List[str]) -> "FillMissingStrategy":
        # Constant filling is stateless, nothing to learn
        self.is_fitted = True
        return self

    def transform(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        if columns:
            df = df.copy()
            # Simple fillna is faster/easier than SimpleImputer for constants
            df[columns] = df[columns].fillna(self.fill_value)
            # logger.info(f"Filled {len(columns)} columns with value {self.fill_value}")
        return df


class DropMissingStrategy(MissingValuesStrategy):
    """Drop rows with missing values."""

    def fit(self, df: pd.DataFrame, columns: List[str]) -> "DropMissingStrategy":
        # Nothing to learn
        self.is_fitted = True
        return self

    def transform(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        if columns:
            original_len = len(df)
            df = df.dropna(subset=columns)
            dropped = original_len - len(df)
            if dropped > 0:
                logger.debug(f"Dropped {dropped} rows with missing values")
        return df


class ImputerStrategy(MissingValuesStrategy):
    """Base for Mean/Median imputation using SimpleImputer."""

    def __init__(self, strategy: str):
        super().__init__()
        self.strategy = strategy
        self.imputer = None
        self.fitted_columns = []

    def fit(self, df: pd.DataFrame, columns: List[str]) -> "ImputerStrategy":
        if columns:
            # Select numeric columns only
            numeric_cols = [
                c for c in columns if df[c].dtype in ["float64", "int64", "float32", "int32"]
            ]
            self.fitted_columns = numeric_cols

            if numeric_cols:
                self.imputer = SimpleImputer(strategy=self.strategy)
                self.imputer.fit(df[numeric_cols])

        self.is_fitted = True
        return self

    def transform(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        # Use only columns that were fitted
        target_cols = [c for c in columns if c in self.fitted_columns]

        if target_cols and self.imputer:
            df = df.copy()
            # Check if target cols exist in df
            existing_cols = [c for c in target_cols if c in df.columns]
            if existing_cols:
                df[existing_cols] = self.imputer.transform(df[existing_cols])
        return df


class MeanFillMissingStrategy(ImputerStrategy):
    def __init__(self):
        super().__init__(strategy="mean")


class MedianFillMissingStrategy(ImputerStrategy):
    def __init__(self):
        super().__init__(strategy="median")


class NormalizationStrategy(PreprocessingStrategy):
    """Base class for normalization strategies."""

    pass


class NoNormalizationStrategy(NormalizationStrategy):
    """No normalization - pass through."""

    def fit(self, df: pd.DataFrame, columns: List[str]) -> "NoNormalizationStrategy":
        self.is_fitted = True
        return self

    def transform(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        return df


class SklearnScalerStrategy(NormalizationStrategy):
    """Wrapper for Sklearn Scalers (Standard, MinMax, Robust)."""

    def __init__(self, scaler_cls):
        super().__init__()
        self.scaler = None
        self.scaler_cls = scaler_cls
        self.fitted_columns = []

    def fit(self, df: pd.DataFrame, columns: List[str]) -> "SklearnScalerStrategy":
        if columns:
            self.fitted_columns = columns
            self.scaler = self.scaler_cls()
            self.scaler.fit(df[columns])

        self.is_fitted = True
        return self

    def transform(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        # Ensure we only define columns that were fitted
        target_cols = [c for c in columns if c in self.fitted_columns]

        if target_cols and self.scaler:
            df = df.copy()
            # Ensure columns exist
            valid_cols = [c for c in target_cols if c in df.columns]
            if valid_cols:
                df[valid_cols] = self.scaler.transform(df[valid_cols])
        return df


class ZScoreNormalizationStrategy(SklearnScalerStrategy):
    def __init__(self):
        super().__init__(StandardScaler)


class MinMaxNormalizationStrategy(SklearnScalerStrategy):
    def __init__(self):
        super().__init__(MinMaxScaler)


class RobustNormalizationStrategy(SklearnScalerStrategy):
    def __init__(self):
        super().__init__(RobustScaler)


class MissingValuesStrategyFactory:
    """Factory for creating missing values strategies."""

    STRATEGIES = {
        "drop_row": DropMissingStrategy,
        "fill_mean": MeanFillMissingStrategy,
        "fill_median": MedianFillMissingStrategy,
        "fill_zero": FillMissingStrategy,
    }

    @classmethod
    def create(cls, strategy_name: str, fill_value: float = 0.0) -> MissingValuesStrategy:
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
        "robust": RobustNormalizationStrategy,
    }

    @classmethod
    def create(cls, method_name: str) -> NormalizationStrategy:
        strategy_class = cls.STRATEGIES.get(method_name, NoNormalizationStrategy)
        return strategy_class()


class PreprocessingService:
    """
    Service for preprocessing ML datasets.

    Logic:
    1. init(config)
    2. fit(train_df) -> Learns params (mean, std, etc.)
    3. transform(any_df) -> Applies params
    """

    def __init__(self, config: Optional[PreprocessingConfig] = None):
        self.config = config or PreprocessingConfig()

        self.missing_strategy = MissingValuesStrategyFactory.create(
            self.config.missing_strategy, self.config.fill_value
        )
        self.normalization_strategy = NormalizationStrategyFactory.create(
            self.config.normalization_method
        )
        self.feature_cols = []
        self.numeric_cols = []
        self.is_fitted = False

    @classmethod
    def from_dict(cls, config_dict: Optional[Dict[str, Any]]) -> "PreprocessingService":
        """Create service from dictionary config."""
        config = PreprocessingConfig.from_dict(config_dict)
        return cls(config)

    def _identify_columns(self, df: pd.DataFrame):
        """Identify feature and numeric columns."""
        self.feature_cols = [c for c in df.columns if c not in METADATA_COLUMNS]
        self.numeric_cols = [
            c for c in self.feature_cols if df[c].dtype in ["float64", "int64", "float32", "int32"]
        ]

    def fit(self, df: pd.DataFrame) -> "PreprocessingService":
        """
        Fit preprocessing strategies on the training data.
        """
        self._identify_columns(df)

        # Fit missing value strategy
        self.missing_strategy.fit(df, self.feature_cols)

        # Fit normalization strategy
        # Note: We should fit normalization usually AFTER handling missing values logic,
        # but in sklearn pipelines, imputers transform the data first.
        # Here we follow:
        # 1. Fit Imputer on DF
        # 2. Transform DF (temp) to get filled values
        # 3. Fit Scaler on filled values

        # Create a temp copy for fitting scaler to avoid fitting on NaNs if imputer fills them
        df_imputed = self.missing_strategy.transform(df, self.feature_cols)

        self.normalization_strategy.fit(df_imputed, self.numeric_cols)

        self.is_fitted = True
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply learned preprocessing to the dataframe.
        """
        if not self.is_fitted:
            logger.warning("PreprocessingService transforming without fit! Params will be empty.")
            # Depending on strategy implementation, might do nothing or fail.

        # 1. Handle missing values
        # Re-identify columns just to be safe if DF has extra/missing cols,
        # but usually we trust the fitted columns.
        # Strategies handle column matching internally.

        # Use columns found during fit if available
        feature_cols = (
            self.feature_cols
            if self.feature_cols
            else [c for c in df.columns if c not in METADATA_COLUMNS]
        )
        numeric_cols = (
            self.numeric_cols
            if self.numeric_cols
            else [
                c for c in feature_cols if df[c].dtype in ["float64", "int64", "float32", "int32"]
            ]
        )

        df = self.missing_strategy.transform(df, feature_cols)

        # 2. Apply normalization
        df = self.normalization_strategy.transform(df, numeric_cols)

        return df

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fit and transform in one step."""
        return self.fit(df).transform(df)
