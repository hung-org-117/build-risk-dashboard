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

pd.set_option("future.no_silent_downcasting", True)

logger = logging.getLogger(__name__)

METADATA_COLUMNS = DEFAULT_FEATURES


@dataclass
class PreprocessingConfig:
    """Configuration for preprocessing operations."""

    missing_strategy: str = "fill_zero"  # fill_zero, fill_mean, fill_median
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
        # Handle ambiguity: TrainingDatasetExport uses 'normalization' as str, legacy uses dict
        is_normalization_dict = isinstance(config_dict.get("normalization"), dict)
        if "missing_features" in config_dict or is_normalization_dict:
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
            for col in columns:
                if col not in df.columns:
                    continue

                # Handle Categorical Columns: Add category if missing
                if isinstance(df[col].dtype, pd.CategoricalDtype):
                    if self.fill_value not in df[col].cat.categories:
                        df[col] = df[col].cat.add_categories([self.fill_value])

                # Simple fillna for the column (fill_value should be numeric for this flow)
                df[col] = df[col].fillna(self.fill_value)

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
                c
                for c in columns
                if df[c].dtype in ["float64", "int64", "float32", "int32"]
            ]
            self.fitted_columns = numeric_cols

            if numeric_cols:
                self.imputer = SimpleImputer(strategy=self.strategy)
                self.imputer.fit(df[numeric_cols])

        self.is_fitted = True
        return self

    def transform(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        # Use only columns that were fitted AND exist in df
        if not self.fitted_columns or not self.imputer:
            return df

        # Check which fitted columns exist in the current dataframe
        existing_fitted_cols = [c for c in self.fitted_columns if c in df.columns]

        if not existing_fitted_cols:
            return df

        df = df.copy()

        # Sklearn requires EXACT same columns as during fit
        # But some columns may be missing from df - we need to handle that
        if len(existing_fitted_cols) == len(self.fitted_columns):
            # All fitted columns exist - can transform directly
            try:
                transformed = self.imputer.transform(df[self.fitted_columns])
                # Handle case where sklearn returns fewer columns (dropped all-null cols)
                if transformed.shape[1] == len(self.fitted_columns):
                    df[self.fitted_columns] = transformed
                else:
                    # Some columns were dropped - need to handle individually
                    for i, col in enumerate(self.fitted_columns):
                        if i < transformed.shape[1]:
                            df[col] = transformed[:, i]
                        else:
                            # Column was dropped - fill with 0
                            df[col] = df[col].fillna(0)
            except ValueError:
                # Fallback: fill all with 0 if sklearn fails
                for col in self.fitted_columns:
                    df[col] = df[col].fillna(0)
        else:
            # Some fitted columns are missing from df
            # Create temp df with all fitted columns, transform, then copy back
            temp_df = pd.DataFrame(index=df.index)
            for col in self.fitted_columns:
                if col in df.columns:
                    temp_df[col] = df[col]
                else:
                    temp_df[col] = float("nan")

            try:
                transformed = self.imputer.transform(temp_df)
                for i, col in enumerate(self.fitted_columns):
                    if col in df.columns and i < transformed.shape[1]:
                        df[col] = transformed[:, i]
            except ValueError:
                # Fallback: fill with 0
                for col in existing_fitted_cols:
                    df[col] = df[col].fillna(0)

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
        if columns and len(df) > 0:
            self.fitted_columns = columns
            self.scaler = self.scaler_cls()
            self.scaler.fit(df[columns])
        elif len(df) == 0:
            logger.warning("Cannot fit scaler: DataFrame is empty (0 samples)")

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
        "fill_mean": MeanFillMissingStrategy,
        "fill_median": MedianFillMissingStrategy,
        "fill_zero": FillMissingStrategy,
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

    def __init__(self, config: Optional[Any] = None):
        self.config = PreprocessingConfig.from_dict(config)
        logger.info(
            f"Initialized PreprocessingService with config: {self.config}"
        )  # Debug version check

        self.missing_strategy = MissingValuesStrategyFactory.create(
            self.config.missing_strategy, self.config.fill_value
        )
        self.normalization_strategy = NormalizationStrategyFactory.create(
            self.config.normalization_method
        )
        self.feature_cols = []
        self.numeric_cols = []
        self.identifier_cols = []  # Columns that should never be filled/imputed
        self.categorical_cols = []  # Columns that should be filled with "unknown"
        self.is_fitted = False

    @classmethod
    def from_dict(cls, config_dict: Optional[Dict[str, Any]]) -> "PreprocessingService":
        """Create service from dictionary config."""
        config = PreprocessingConfig.from_dict(config_dict)
        return cls(config)

    def _identify_columns(self, df: pd.DataFrame):
        """
        Identify feature columns and classify them using metadata from registries.

        Lookups in order:
        1. FEATURE_REGISTRY (84 Hamilton DAG features)
        2. SONARQUBE_METRICS (53 metrics, prefixed with 'sonar_')
        3. TRIVY_METRICS (15 metrics, prefixed with 'trivy_')
        4. Fallback: numeric columns are normalized

        Uses preprocessing_type and normalize attributes to:
        - Determine which columns are features (not in METADATA_COLUMNS)
        - Identify numeric columns that should be normalized (normalize=True)
        - Skip normalization for IDENTIFIER, BINARY, RATIO, CATEGORICAL types
        """
        # Load feature registry
        try:
            from app.tasks.pipeline.feature_dag.registry import FEATURE_REGISTRY
        except ImportError:
            logger.warning("Could not import FEATURE_REGISTRY")
            FEATURE_REGISTRY = {}

        # Load scan metric registries
        try:
            from app.integrations.tools.sonarqube.metrics import SONARQUBE_METRICS

            # Build lookup dict: sonar_{key} -> MetricDefinition
            sonar_registry = {f"sonar_{m.key}": m for m in SONARQUBE_METRICS}
        except ImportError:
            logger.warning("Could not import SONARQUBE_METRICS")
            sonar_registry = {}

        try:
            from app.integrations.tools.trivy.metrics import TRIVY_METRICS

            # Build lookup dict: trivy_{key} -> MetricDefinition
            trivy_registry = {f"trivy_{m.key}": m for m in TRIVY_METRICS}
        except ImportError:
            logger.warning("Could not import TRIVY_METRICS")
            trivy_registry = {}

        self.feature_cols = [c for c in df.columns if c not in METADATA_COLUMNS]

        # Use registries to determine which columns should be normalized
        normalizable_cols = []
        for col in self.feature_cols:
            # Check FEATURE_REGISTRY first
            if col in FEATURE_REGISTRY:
                if FEATURE_REGISTRY[col].normalize:
                    normalizable_cols.append(col)
            # Check SonarQube metrics
            elif col in sonar_registry:
                if sonar_registry[col].normalize:
                    normalizable_cols.append(col)
            # Check Trivy metrics
            elif col in trivy_registry:
                if trivy_registry[col].normalize:
                    normalizable_cols.append(col)
            else:
                # Fallback: if not in any registry, use old logic (numeric = normalize)
                if df[col].dtype in ["float64", "int64", "float32", "int32"]:
                    normalizable_cols.append(col)

        # Identify columns by preprocessing type for special handling
        identifier_cols = []
        categorical_cols = []
        for col in self.feature_cols:
            if col in FEATURE_REGISTRY:
                feat_def = FEATURE_REGISTRY[col]
                if hasattr(feat_def, "preprocessing_type"):
                    ptype = feat_def.preprocessing_type
                    if hasattr(ptype, "value"):
                        ptype = ptype.value
                    if ptype == "identifier":
                        identifier_cols.append(col)
                    elif ptype == "categorical":
                        categorical_cols.append(col)

        self.identifier_cols = identifier_cols
        self.categorical_cols = categorical_cols

        # Filter to only numeric columns that exist in df
        self.numeric_cols = [
            c
            for c in normalizable_cols
            if c in df.columns
            and df[c].dtype in ["float64", "int64", "float32", "int32"]
        ]

        logger.debug(
            f"Identified {len(self.feature_cols)} features, "
            f"{len(self.numeric_cols)} will be normalized"
        )

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

        if len(df_imputed) == 0:
            logger.warning("DataFrame is empty after missing values handling.")

        self.normalization_strategy.fit(df_imputed, self.numeric_cols)

        self.is_fitted = True
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply learned preprocessing to the dataframe.
        """
        if not self.is_fitted:
            logger.warning(
                "PreprocessingService transforming without fit! Params will be empty."
            )
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
                c
                for c in feature_cols
                if df[c].dtype in ["float64", "int64", "float32", "int32"]
            ]
        )

        # Only apply fill strategies to numeric columns, EXCLUDING identifiers
        # Identifiers (like pr_number, history_prev_build_id) should preserve NULL
        identifier_set = set(self.identifier_cols) if self.identifier_cols else set()
        categorical_set = set(self.categorical_cols) if self.categorical_cols else set()

        missing_target_cols = [
            c
            for c in feature_cols
            if c in df.columns
            and pd.api.types.is_numeric_dtype(df[c])
            and c not in identifier_set
            and c not in categorical_set
        ]

        # Handle CATEGORICAL columns: fill with "unknown"
        for col in self.categorical_cols:
            if col in df.columns:
                df[col] = df[col].fillna("unknown")

        df = self.missing_strategy.transform(df, missing_target_cols)

        # 2. Apply normalization
        df = self.normalization_strategy.transform(df, numeric_cols)

        return df

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fit and transform in one step."""
        return self.fit(df).transform(df)
