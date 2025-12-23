"""
Normalization Service - Apply normalization methods to numeric features during export.

Uses numpy for efficient calculations. Supported methods:
- Min-Max: Scale to [0, 1]
- Z-Score: Standardization (mean=0, std=1)
- Robust: Uses median and IQR (resistant to outliers)
- MaxAbs: Scale by max absolute value (preserves sign, range [-1, 1])
- Log: Log transformation (for skewed distributions)
- Decimal: Scale by power of 10 (divides by 10^k where k = max digits)
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class NormalizationMethod(str, Enum):
    """Available normalization methods."""

    NONE = "none"
    MINMAX = "minmax"  # Scale to [0, 1]
    ZSCORE = "zscore"  # Mean=0, Std=1 (Standardization)
    ROBUST = "robust"  # Median-IQR based (robust to outliers)
    MAXABS = "maxabs"  # Scale by max absolute value [-1, 1]
    LOG = "log"  # Log transformation (log1p for handling zeros)
    DECIMAL = "decimal"  # Decimal scaling


class FeatureNormalizationParams(BaseModel):
    """Parameters calculated for a feature's normalization."""

    feature_name: str
    method: NormalizationMethod
    # MinMax params
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    # Z-Score params
    mean: Optional[float] = None
    std: Optional[float] = None
    # Robust params (median and IQR)
    median: Optional[float] = None
    iqr: Optional[float] = None
    q1: Optional[float] = None
    q3: Optional[float] = None
    # MaxAbs params
    max_abs: Optional[float] = None
    # Decimal scaling params
    scale_factor: Optional[float] = None


class NormalizationService:
    """
    Service for normalizing numeric feature values using numpy.

    Usage:
        1. Calculate normalization parameters from data
        2. Apply normalization to individual values or entire rows

    Supported Methods:
        - NONE: No transformation
        - MINMAX: (x - min) / (max - min) → [0, 1]
        - ZSCORE: (x - mean) / std → mean=0, std=1
        - ROBUST: (x - median) / IQR → resistant to outliers
        - MAXABS: x / max(|x|) → [-1, 1], preserves sparsity
        - LOG: log1p(x) → for right-skewed distributions
        - DECIMAL: x / 10^k → k is number of digits in max value
    """

    @staticmethod
    def _to_numpy_array(values: List[Any]) -> np.ndarray:
        """Convert list of values to numpy array, filtering non-numeric."""
        numeric_values = []
        for value in values:
            if value is not None:
                try:
                    numeric_values.append(float(value))
                except (ValueError, TypeError):
                    continue
        return np.array(numeric_values) if numeric_values else np.array([])

    @staticmethod
    def calculate_params(
        feature_name: str,
        values: List[Any],
        method: NormalizationMethod,
    ) -> FeatureNormalizationParams:
        """
        Calculate normalization parameters from a list of values using numpy.

        Args:
            feature_name: Name of the feature
            values: List of raw values (may include None)
            method: Normalization method to use

        Returns:
            FeatureNormalizationParams with calculated parameters
        """
        arr = NormalizationService._to_numpy_array(values)

        if len(arr) == 0 or method == NormalizationMethod.NONE:
            return FeatureNormalizationParams(
                feature_name=feature_name,
                method=NormalizationMethod.NONE,
            )

        if method == NormalizationMethod.MINMAX:
            return FeatureNormalizationParams(
                feature_name=feature_name,
                method=NormalizationMethod.MINMAX,
                min_value=float(np.min(arr)),
                max_value=float(np.max(arr)),
            )

        if method == NormalizationMethod.ZSCORE:
            return FeatureNormalizationParams(
                feature_name=feature_name,
                method=NormalizationMethod.ZSCORE,
                mean=float(np.mean(arr)),
                std=float(np.std(arr)) if np.std(arr) > 0 else 1.0,
            )

        if method == NormalizationMethod.ROBUST:
            q1_val = float(np.percentile(arr, 25))
            q3_val = float(np.percentile(arr, 75))
            iqr_val = q3_val - q1_val
            return FeatureNormalizationParams(
                feature_name=feature_name,
                method=NormalizationMethod.ROBUST,
                median=float(np.median(arr)),
                iqr=iqr_val if iqr_val > 0 else 1.0,
                q1=q1_val,
                q3=q3_val,
            )

        if method == NormalizationMethod.MAXABS:
            max_abs_val = float(np.max(np.abs(arr)))
            return FeatureNormalizationParams(
                feature_name=feature_name,
                method=NormalizationMethod.MAXABS,
                max_abs=max_abs_val if max_abs_val > 0 else 1.0,
            )

        if method == NormalizationMethod.LOG:
            # For log transformation, we just need min to handle negative values
            min_val = float(np.min(arr))
            return FeatureNormalizationParams(
                feature_name=feature_name,
                method=NormalizationMethod.LOG,
                min_value=min_val,
            )

        if method == NormalizationMethod.DECIMAL:
            max_abs_val = float(np.max(np.abs(arr)))
            if max_abs_val > 0:
                # Find the power of 10 to scale by
                num_digits = int(np.ceil(np.log10(max_abs_val + 1)))
                scale_factor = 10.0**num_digits
            else:
                scale_factor = 1.0
            return FeatureNormalizationParams(
                feature_name=feature_name,
                method=NormalizationMethod.DECIMAL,
                scale_factor=scale_factor,
            )

        return FeatureNormalizationParams(
            feature_name=feature_name,
            method=NormalizationMethod.NONE,
        )

    @staticmethod
    def normalize_value(
        value: Any,
        params: FeatureNormalizationParams,
    ) -> Any:
        """
        Normalize a single value using pre-calculated parameters.

        Args:
            value: Raw value to normalize
            params: Pre-calculated normalization parameters

        Returns:
            Normalized value, or original value if cannot normalize
        """
        if value is None or params.method == NormalizationMethod.NONE:
            return value

        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
            return value

        if params.method == NormalizationMethod.MINMAX:
            min_val = params.min_value
            max_val = params.max_value
            if min_val is None or max_val is None:
                return value
            range_val = max_val - min_val
            if range_val == 0:
                return 0.5  # All values are the same
            return (numeric_value - min_val) / range_val

        if params.method == NormalizationMethod.ZSCORE:
            mean_val = params.mean
            std_val = params.std
            if mean_val is None or std_val is None or std_val == 0:
                return value
            return (numeric_value - mean_val) / std_val

        if params.method == NormalizationMethod.ROBUST:
            median_val = params.median
            iqr_val = params.iqr
            if median_val is None or iqr_val is None or iqr_val == 0:
                return value
            return (numeric_value - median_val) / iqr_val

        if params.method == NormalizationMethod.MAXABS:
            max_abs_val = params.max_abs
            if max_abs_val is None or max_abs_val == 0:
                return value
            return numeric_value / max_abs_val

        if params.method == NormalizationMethod.LOG:
            # Use log1p for stability (handles zeros)
            # Shift values if there are negatives
            min_val = params.min_value or 0
            shift = abs(min_val) + 1 if min_val < 0 else 0
            return float(np.log1p(numeric_value + shift))

        if params.method == NormalizationMethod.DECIMAL:
            scale_factor = params.scale_factor
            if scale_factor is None or scale_factor == 0:
                return value
            return numeric_value / scale_factor

        return value

    @staticmethod
    def normalize_array(
        values: List[Any],
        params: FeatureNormalizationParams,
    ) -> List[Any]:
        """
        Normalize an entire array of values efficiently using numpy.

        Args:
            values: List of values to normalize
            params: Pre-calculated normalization parameters

        Returns:
            List of normalized values
        """
        if params.method == NormalizationMethod.NONE:
            return values

        # Build mask for valid numeric values
        result = []
        for value in values:
            result.append(NormalizationService.normalize_value(value, params))
        return result

    @staticmethod
    def normalize_row(
        row: Dict[str, Any],
        params_map: Dict[str, FeatureNormalizationParams],
    ) -> Dict[str, Any]:
        """
        Normalize all features in a row.

        Args:
            row: Dictionary of feature_name -> value
            params_map: Dictionary of feature_name -> FeatureNormalizationParams

        Returns:
            New dictionary with normalized values
        """
        normalized_row = {}

        for feature_name, value in row.items():
            if feature_name in params_map:
                normalized_row[feature_name] = NormalizationService.normalize_value(
                    value, params_map[feature_name]
                )
            else:
                normalized_row[feature_name] = value

        return normalized_row

    @staticmethod
    def calculate_params_batch(
        feature_values: Dict[str, List[Any]],
        method: NormalizationMethod,
    ) -> Dict[str, FeatureNormalizationParams]:
        """
        Calculate normalization parameters for multiple features.

        Args:
            feature_values: Dictionary of feature_name -> list of values
            method: Normalization method to apply

        Returns:
            Dictionary of feature_name -> FeatureNormalizationParams
        """
        params_map = {}

        for feature_name, values in feature_values.items():
            params_map[feature_name] = NormalizationService.calculate_params(
                feature_name, values, method
            )

        return params_map

    @staticmethod
    def get_normalization_summary(
        params_map: Dict[str, FeatureNormalizationParams],
    ) -> List[Dict[str, Any]]:
        """
        Get a summary of normalization parameters for display.

        Args:
            params_map: Dictionary of feature_name -> FeatureNormalizationParams

        Returns:
            List of summary dictionaries
        """
        summaries = []

        for feature_name, params in params_map.items():
            summary: Dict[str, Any] = {
                "feature_name": feature_name,
                "method": params.method.value,
            }

            if params.method == NormalizationMethod.MINMAX:
                summary["min"] = params.min_value
                summary["max"] = params.max_value
            elif params.method == NormalizationMethod.ZSCORE:
                summary["mean"] = params.mean
                summary["std"] = params.std
            elif params.method == NormalizationMethod.ROBUST:
                summary["median"] = params.median
                summary["iqr"] = params.iqr
                summary["q1"] = params.q1
                summary["q3"] = params.q3
            elif params.method == NormalizationMethod.MAXABS:
                summary["max_abs"] = params.max_abs
            elif params.method == NormalizationMethod.LOG:
                summary["min"] = params.min_value
            elif params.method == NormalizationMethod.DECIMAL:
                summary["scale_factor"] = params.scale_factor

            summaries.append(summary)

        return summaries

    @staticmethod
    def get_available_methods() -> List[Dict[str, str]]:
        """
        Get list of available normalization methods with descriptions.

        Returns:
            List of method info dictionaries
        """
        return [
            {
                "value": NormalizationMethod.NONE.value,
                "label": "None",
                "description": "No transformation applied",
            },
            {
                "value": NormalizationMethod.MINMAX.value,
                "label": "Min-Max",
                "description": "Scale to [0, 1] range",
            },
            {
                "value": NormalizationMethod.ZSCORE.value,
                "label": "Z-Score (Standardization)",
                "description": "Transform to mean=0, std=1",
            },
            {
                "value": NormalizationMethod.ROBUST.value,
                "label": "Robust Scaler",
                "description": "Uses median and IQR, resistant to outliers",
            },
            {
                "value": NormalizationMethod.MAXABS.value,
                "label": "Max Absolute",
                "description": "Scale by max absolute value to [-1, 1]",
            },
            {
                "value": NormalizationMethod.LOG.value,
                "label": "Log Transform",
                "description": "Logarithmic transformation for skewed data",
            },
            {
                "value": NormalizationMethod.DECIMAL.value,
                "label": "Decimal Scaling",
                "description": "Divide by power of 10",
            },
        ]
