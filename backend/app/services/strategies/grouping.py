"""
Grouping utilities for splitting strategies.

This module provides functions for creating group columns from data:
- Language normalization
- Equal-width binning for numeric features
- Time slot creation for time-based grouping
"""

import logging
from typing import Optional

import pandas as pd

from app.entities.enums import GroupByDimension

logger = logging.getLogger(__name__)


def create_language_column(df: pd.DataFrame) -> str:
    """
    Create normalized language column for grouping.

    Args:
        df: DataFrame to modify (in-place)

    Returns:
        Column name to use for grouping
    """
    column_name = "_language"

    # Use repo_language from DEFAULT_FEATURES (extracted by Hamilton DAG)
    if "repo_language" in df.columns:
        df[column_name] = df["repo_language"].str.lower().fillna("other")
    else:
        df[column_name] = "other"

    return column_name


def create_equal_width_bins(
    df: pd.DataFrame,
    column: str,
    num_bins: int = 4,
) -> str:
    """
    Create N equal-width bins for a numeric column.

    Args:
        df: DataFrame to modify (in-place)
        column: Source column name
        num_bins: Number of bins to create

    Returns:
        Column name of the created bin column
    """
    bin_column = f"_{column}_bin"

    if column not in df.columns:
        df[bin_column] = "0-100"
        return bin_column

    min_val = df[column].min()
    max_val = df[column].max()

    if min_val == max_val or pd.isna(min_val) or pd.isna(max_val):
        df[bin_column] = (
            f"{int(min_val) if not pd.isna(min_val) else 0}-"
            f"{int(max_val) if not pd.isna(max_val) else 100}"
        )
        return bin_column

    # Calculate equal-width bin edges
    bin_width = (max_val - min_val) / num_bins
    bins = [min_val + i * bin_width for i in range(num_bins + 1)]
    bins[-1] = max_val + 0.001  # Ensure max value is included

    labels = [f"{int(bins[i])}-{int(bins[i + 1])}" for i in range(num_bins)]
    df[bin_column] = pd.cut(
        df[column], bins=bins, labels=labels, include_lowest=True
    ).astype(str)

    return bin_column


def create_time_slots(df: pd.DataFrame, num_slots: int = 4) -> str:
    """
    Create N time slots from 24-hour cycle.

    Args:
        df: DataFrame to modify (in-place)
        num_slots: Number of time slots to create

    Returns:
        Column name of the created time slot column
    """
    bin_column = "_time_slot"
    hours_per_slot = 24 // num_slots

    # Get hour from available sources
    if "build_hour" in df.columns:
        hour_col = df["build_hour"]
    elif "build_started_at" in df.columns:
        df["_temp_hour"] = pd.to_datetime(df["build_started_at"]).dt.hour
        hour_col = df["_temp_hour"]
    else:
        hour_col = pd.Series([12] * len(df))

    def hour_to_slot(h):
        if pd.isna(h):
            return "12:00-18:00"
        slot_idx = int(h // hours_per_slot)
        start = slot_idx * hours_per_slot
        end = min((slot_idx + 1) * hours_per_slot, 24)
        return f"{start:02d}:00-{end:02d}:00"

    df[bin_column] = hour_col.apply(hour_to_slot)
    return bin_column


def get_group_label(group_by: GroupByDimension, value: str) -> str:
    """
    Get human-readable label for a group value.

    Args:
        group_by: Grouping dimension
        value: Group value

    Returns:
        Human-readable label
    """
    group_by_str = str(group_by) if not isinstance(group_by, str) else group_by

    if group_by_str == "repo_language":
        return str(value).title() if value else "Unknown"

    # Time and numeric bins already have descriptive labels
    return str(value)
