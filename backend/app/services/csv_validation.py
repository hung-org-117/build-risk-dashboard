"""
CSV Validation Service - Pandera schema validation for dataset uploads.

Uses Pandera for DataFrame schema validation to catch errors early
before processing builds through CI provider APIs.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
import pandera as pa

from app.ci_providers.models import CIProvider
from app.config import settings

logger = logging.getLogger(__name__)

# Valid CI provider values
VALID_CI_PROVIDERS = [provider.value for provider in CIProvider]


class DatasetCSVSchema(pa.DataFrameModel):
    """
    Schema validation for dataset CSV uploads.

    Note: This uses dynamic column names, so we validate after renaming
    columns to standard names (build_id, repo_name, ci_provider).
    """

    build_id: pa.typing.Series[str] = pa.Field(
        nullable=False,
        description="Build ID from CI provider",
    )

    repo_name: pa.typing.Series[str] = pa.Field(
        nullable=False,
        str_matches=r"^[\w.-]+/[\w.-]+$",  # Format: owner/repo
        description="Repository full name",
    )

    class Config:
        coerce = True
        strict = False  # Allow extra columns


def validate_required_columns(
    df: pd.DataFrame,
    build_id_column: str,
    repo_name_column: str,
    ci_provider_column: Optional[str] = None,
) -> List[str]:
    """
    Validate that required columns exist in DataFrame.

    Args:
        df: DataFrame loaded from CSV
        build_id_column: Column name for build IDs
        repo_name_column: Column name for repo names
        ci_provider_column: Optional column name for CI providers

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    if build_id_column not in df.columns:
        errors.append(f"Required column '{build_id_column}' not found in CSV")

    if repo_name_column not in df.columns:
        errors.append(f"Required column '{repo_name_column}' not found in CSV")

    if ci_provider_column and ci_provider_column not in df.columns:
        errors.append(f"CI provider column '{ci_provider_column}' not found in CSV")

    return errors


def validate_repo_name_format(df: pd.DataFrame, repo_name_column: str) -> Dict[str, Any]:
    """
    Validate repo_name format (owner/repo pattern).

    Args:
        df: DataFrame with repo_name column
        repo_name_column: Name of the repo column

    Returns:
        Dict with valid_repos, invalid_repos counts and invalid list
    """
    repo_pattern = r"^[\w.-]+/[\w.-]+$"

    # Get unique repo names
    unique_repos = df[repo_name_column].dropna().unique()

    valid_repos = []
    invalid_repos = []

    for repo_name in unique_repos:
        repo_str = str(repo_name).strip()
        if "/" in repo_str and len(repo_str.split("/")) == 2:
            owner, name = repo_str.split("/")
            if owner and name:
                valid_repos.append(repo_str)
            else:
                invalid_repos.append(repo_str)
        else:
            invalid_repos.append(repo_str)

    return {
        "valid_repos": valid_repos,
        "invalid_repos": invalid_repos,
        "valid_count": len(valid_repos),
        "invalid_count": len(invalid_repos),
    }


def validate_ci_provider_values(
    df: pd.DataFrame,
    ci_provider_column: str,
) -> Dict[str, Any]:
    """
    Validate CI provider values in a column.

    Args:
        df: DataFrame with CI provider column
        ci_provider_column: Name of the CI provider column

    Returns:
        Dict with valid/invalid counts and invalid values
    """
    unique_providers = df[ci_provider_column].dropna().unique()

    valid_providers = []
    invalid_providers = []

    for provider_value in unique_providers:
        provider_str = str(provider_value).strip().lower()
        if provider_str in VALID_CI_PROVIDERS:
            valid_providers.append(provider_str)
        else:
            invalid_providers.append(str(provider_value))

    return {
        "valid_providers": valid_providers,
        "invalid_providers": invalid_providers,
        "valid_count": len(valid_providers),
        "invalid_count": len(invalid_providers),
    }


def validate_dataset_csv(
    df: pd.DataFrame,
    build_id_column: str,
    repo_name_column: str,
    ci_provider_column: Optional[str] = None,
    single_ci_provider: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Comprehensive validation of uploaded CSV for dataset processing.

    Args:
        df: DataFrame loaded from CSV file
        build_id_column: Column name containing build IDs
        repo_name_column: Column name containing repo names (owner/repo format)
        ci_provider_column: Column name for CI provider (multi-provider mode)
        single_ci_provider: Single CI provider value (single-provider mode)

    Returns:
        Dict with keys:
            - valid: bool - Overall validation passed
            - errors: List[str] - Critical errors that block processing
            - warnings: List[str] - Non-blocking warnings
            - stats: Dict - Statistics about the data
            - repo_validation: Dict - Repo format validation results
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Validate required columns exist
    column_errors = validate_required_columns(
        df=df,
        build_id_column=build_id_column,
        repo_name_column=repo_name_column,
        ci_provider_column=ci_provider_column,
    )
    errors.extend(column_errors)

    # If required columns missing, return early
    if errors:
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "stats": {"total_rows": len(df)},
            "repo_validation": None,
        }

    # 2. Validate CI provider
    if ci_provider_column:
        ci_validation = validate_ci_provider_values(df, ci_provider_column)
        if ci_validation["invalid_count"] > 0:
            errors.append(
                f"Invalid CI providers found: {ci_validation['invalid_providers']}. "
                f"Valid values: {VALID_CI_PROVIDERS}"
            )
    elif single_ci_provider:
        if single_ci_provider not in VALID_CI_PROVIDERS:
            errors.append(
                f"Invalid CI provider: '{single_ci_provider}'. "
                f"Valid values: {VALID_CI_PROVIDERS}"
            )
    else:
        errors.append("CI provider must be specified (single value or column mapping)")

    # 3. Validate repo name format
    repo_validation = validate_repo_name_format(df, repo_name_column)
    if repo_validation["invalid_count"] > 0:
        warnings.append(
            f"{repo_validation['invalid_count']} repos have invalid format "
            f"(expected 'owner/repo'): {repo_validation['invalid_repos'][:5]}"
        )

    # 4. Check for empty/null values in required columns
    null_build_ids = df[build_id_column].isna().sum()
    null_repo_names = df[repo_name_column].isna().sum()

    if null_build_ids > 0:
        warnings.append(f"{null_build_ids} rows have missing build_id values")
    if null_repo_names > 0:
        warnings.append(f"{null_repo_names} rows have missing repo_name values")

    # 5. Check for duplicates
    duplicate_count = df.duplicated(subset=[build_id_column, repo_name_column]).sum()
    if duplicate_count > 0:
        warnings.append(f"{duplicate_count} duplicate build entries found")

    # Build stats
    stats = {
        "total_rows": len(df),
        "unique_repos": df[repo_name_column].nunique(),
        "unique_builds": df[build_id_column].nunique(),
        "null_build_ids": int(null_build_ids),
        "null_repo_names": int(null_repo_names),
        "duplicate_count": int(duplicate_count),
    }

    # 6. Check row limits using config
    if len(df) < settings.CSV_MIN_ROWS:
        errors.append(f"CSV must have at least {settings.CSV_MIN_ROWS} data rows")

    if len(df) > settings.CSV_MAX_ROWS:
        errors.append(f"CSV has {len(df)} rows, exceeds maximum allowed ({settings.CSV_MAX_ROWS})")

    # 7. Check threshold warnings
    total_rows = len(df)
    if total_rows > 0:
        duplicate_rate = duplicate_count / total_rows
        missing_rate = (null_build_ids + null_repo_names) / (total_rows * 2)

        if duplicate_rate > settings.CSV_DUPLICATE_WARN_THRESHOLD:
            threshold_pct = settings.CSV_DUPLICATE_WARN_THRESHOLD * 100
            warnings.append(
                f"High duplicate rate: {duplicate_rate:.1%} " f"(threshold: {threshold_pct:.0f}%)"
            )

        if missing_rate > settings.CSV_MISSING_WARN_THRESHOLD:
            threshold_pct = settings.CSV_MISSING_WARN_THRESHOLD * 100
            warnings.append(
                f"High missing value rate: {missing_rate:.1%} " f"(threshold: {threshold_pct:.0f}%)"
            )

    logger.info(
        f"CSV validation complete: {stats['total_rows']} rows, "
        f"{stats['unique_repos']} repos, {len(errors)} errors, {len(warnings)} warnings"
    )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": stats,
        "repo_validation": repo_validation,
    }


def prepare_validated_dataframe(
    df: pd.DataFrame,
    build_id_column: str,
    repo_name_column: str,
    ci_provider_column: Optional[str] = None,
    single_ci_provider: Optional[str] = None,
) -> pd.DataFrame:
    """
    Prepare DataFrame for processing after validation.

    Renames columns to standard names, adds ci_provider column if single mode,
    and filters out rows with invalid repo formats.

    Args:
        df: Validated DataFrame
        build_id_column: Original column name for build IDs
        repo_name_column: Original column name for repo names
        ci_provider_column: Original column name for CI provider (if multi)
        single_ci_provider: CI provider value (if single mode)

    Returns:
        DataFrame with standardized column names ready for processing
    """
    # Create copy to avoid modifying original
    processed_df = df.copy()

    # Rename to standard column names
    rename_map = {
        build_id_column: "build_id",
        repo_name_column: "repo_name",
    }

    if ci_provider_column:
        rename_map[ci_provider_column] = "ci_provider"

    processed_df = processed_df.rename(columns=rename_map)

    # Add ci_provider column if single mode
    if single_ci_provider and not ci_provider_column:
        processed_df["ci_provider"] = single_ci_provider

    # Filter out rows with invalid data
    processed_df = processed_df.dropna(subset=["build_id", "repo_name"])

    # Ensure build_id is string
    processed_df["build_id"] = processed_df["build_id"].astype(str).str.strip()
    processed_df["repo_name"] = processed_df["repo_name"].astype(str).str.strip()

    # Filter only valid repo format
    valid_repo_pattern = r"^[\w.-]+/[\w.-]+$"
    processed_df = processed_df[processed_df["repo_name"].str.match(valid_repo_pattern, na=False)]

    return processed_df
