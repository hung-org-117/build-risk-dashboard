"""
YAML Validation Service for ML Scenarios.

Provides strict schema validation for scenario YAML configuration using Pydantic v2.
Returns clear, actionable error messages with field paths and expected values.
"""

import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

logger = logging.getLogger(__name__)

# =============================================================================
# ENUMS - Valid values for categorical fields
# =============================================================================


class SplitStrategyEnum(str, Enum):
    """Valid splitting strategies."""

    STRATIFIED_WITHIN_GROUP = "stratified_within_group"
    LEAVE_ONE_OUT = "leave_one_out"
    LEAVE_TWO_OUT = "leave_two_out"
    IMBALANCED_TRAIN = "imbalanced_train"
    EXTREME_NOVELTY = "extreme_novelty"


class GroupByDimensionEnum(str, Enum):
    """Valid group_by dimensions."""

    LANGUAGE_GROUP = "language_group"
    PERCENTAGE_OF_BUILDS_BEFORE = "percentage_of_builds_before"
    NUMBER_OF_BUILDS_BEFORE = "number_of_builds_before"
    TIME_OF_DAY = "time_of_day"


class FilterByEnum(str, Enum):
    """Valid filter_by options."""

    ALL = "all"
    BY_LANGUAGE = "by_language"
    BY_NAME = "by_name"
    BY_OWNER = "by_owner"


class OutputFormatEnum(str, Enum):
    """Valid output formats."""

    PARQUET = "parquet"
    CSV = "csv"
    PICKLE = "pickle"


class MissingValuesStrategyEnum(str, Enum):
    """Valid missing values strategies."""

    DROP_ROW = "drop_row"
    FILL = "fill"
    MEAN = "mean"
    SKIP_FEATURE = "skip_feature"


class NormalizationMethodEnum(str, Enum):
    """Valid normalization methods."""

    Z_SCORE = "z_score"
    MIN_MAX = "min_max"
    ROBUST = "robust"
    NONE = "none"


# =============================================================================
# SCHEMA MODELS
# =============================================================================


class ScenarioInfoSchema(BaseModel):
    """Scenario metadata section."""

    name: str = Field(..., min_length=1, description="Unique scenario name")
    description: Optional[str] = Field(None, description="Scenario description")
    version: str = Field(default="1.0", description="Version string")


class DateRangeSchema(BaseModel):
    """Date range for filtering builds."""

    start: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")

    @field_validator("start", "end", mode="before")
    @classmethod
    def validate_date_string(cls, value: Any) -> Optional[str]:
        """Convert date to string if needed."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        return str(value)


class RepositoriesFilterSchema(BaseModel):
    """Repository filter configuration."""

    filter_by: FilterByEnum = Field(
        default=FilterByEnum.ALL, description="Filter mode for repositories"
    )
    languages: List[str] = Field(
        default_factory=list,
        description="Languages to include (required if filter_by=by_language)",
    )
    repo_names: List[str] = Field(
        default_factory=list,
        description="Repo full names (required if filter_by=by_name)",
    )
    owners: List[str] = Field(
        default_factory=list,
        description="Owners/orgs (required if filter_by=by_owner)",
    )

    @model_validator(mode="after")
    def validate_filter_has_values(self) -> "RepositoriesFilterSchema":
        """Ensure filter has corresponding values."""
        if self.filter_by == FilterByEnum.BY_LANGUAGE and not self.languages:
            raise ValueError("languages list is required when filter_by='by_language'")
        if self.filter_by == FilterByEnum.BY_NAME and not self.repo_names:
            raise ValueError("repo_names list is required when filter_by='by_name'")
        if self.filter_by == FilterByEnum.BY_OWNER and not self.owners:
            raise ValueError("owners list is required when filter_by='by_owner'")
        return self


class BuildsFilterSchema(BaseModel):
    """Build filter configuration."""

    date_range: Optional[DateRangeSchema] = None
    conclusions: List[str] = Field(
        default_factory=lambda: ["success", "failure"],
        description="Build conclusions to include",
    )
    exclude_bots: bool = Field(default=True, description="Exclude bot commits")


class DataSourceSchema(BaseModel):
    """Data source configuration."""

    repositories: RepositoriesFilterSchema = Field(
        default_factory=RepositoriesFilterSchema
    )
    builds: BuildsFilterSchema = Field(default_factory=BuildsFilterSchema)
    ci_provider: str = Field(
        default="all",
        description="CI provider: all | github_actions | circleci",
    )


class FeaturesSchema(BaseModel):
    """Feature selection configuration."""

    dag_features: List[str] = Field(
        default_factory=list,
        description="DAG features to extract (supports wildcards: build_*, git_*)",
    )
    scan_metrics: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description="Scan metrics: {sonarqube: [...], trivy: [...]}",
    )
    exclude: List[str] = Field(
        default_factory=list,
        description="Features to exclude (supports wildcards)",
    )


class SplitRatiosSchema(BaseModel):
    """Split ratio configuration."""

    train: float = Field(default=0.7, ge=0.0, le=1.0)
    val: float = Field(default=0.15, ge=0.0, le=1.0)
    test: float = Field(default=0.15, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_ratios_sum(self) -> "SplitRatiosSchema":
        """Ratios should sum to 1.0 (with tolerance)."""
        total = self.train + self.val + self.test
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Ratios must sum to 1.0, got {total:.2f} "
                f"(train={self.train}, val={self.val}, test={self.test})"
            )
        return self


class SplittingConfigSchema(BaseModel):
    """Splitting configuration (inside config: key)."""

    ratios: SplitRatiosSchema = Field(default_factory=SplitRatiosSchema)
    stratify_by: str = Field(default="outcome", description="Column to stratify by")

    # Leave-out specific
    test_groups: List[str] = Field(default_factory=list)
    val_groups: List[str] = Field(default_factory=list)
    train_groups: List[str] = Field(default_factory=list)

    # Imbalanced train specific
    reduce_label: Optional[int] = Field(
        None, description="Label to reduce (0=success, 1=failure)"
    )
    reduce_ratio: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Ratio to reduce"
    )

    # Extreme novelty specific
    novelty_group: Optional[str] = Field(None, description="Group for novelty testing")
    novelty_label: Optional[int] = Field(None, description="Label for novelty testing")


class SplittingSchema(BaseModel):
    """Splitting section configuration."""

    strategy: SplitStrategyEnum = Field(
        ..., description="Splitting strategy (required)"
    )
    group_by: GroupByDimensionEnum = Field(
        default=GroupByDimensionEnum.LANGUAGE_GROUP,
        description="Dimension to group by",
    )
    config: SplittingConfigSchema = Field(default_factory=SplittingConfigSchema)

    @model_validator(mode="after")
    def validate_strategy_has_required_config(self) -> "SplittingSchema":
        """Validate strategy-specific required fields."""
        if self.strategy == SplitStrategyEnum.LEAVE_ONE_OUT:
            if not self.config.test_groups:
                raise ValueError("leave_one_out strategy requires config.test_groups")
        if self.strategy == SplitStrategyEnum.LEAVE_TWO_OUT:
            if not self.config.test_groups or not self.config.val_groups:
                raise ValueError(
                    "leave_two_out strategy requires config.test_groups and config.val_groups"
                )
        if self.strategy == SplitStrategyEnum.IMBALANCED_TRAIN:
            if self.config.reduce_label is None:
                raise ValueError(
                    "imbalanced_train strategy requires config.reduce_label"
                )
        if self.strategy == SplitStrategyEnum.EXTREME_NOVELTY:
            if self.config.novelty_group is None or self.config.novelty_label is None:
                raise ValueError(
                    "extreme_novelty strategy requires config.novelty_group and config.novelty_label"
                )
        return self


class PreprocessingSchema(BaseModel):
    """Preprocessing configuration."""

    missing_values_strategy: MissingValuesStrategyEnum = Field(
        default=MissingValuesStrategyEnum.DROP_ROW,
        description="Strategy for handling missing values",
    )
    fill_value: Union[int, float, str] = Field(
        default=0, description="Value to fill (if strategy=fill)"
    )
    normalization_method: NormalizationMethodEnum = Field(
        default=NormalizationMethodEnum.Z_SCORE,
        description="Normalization method",
    )
    strict_mode: bool = Field(
        default=False, description="Fail if any feature is missing"
    )


class OutputSchema(BaseModel):
    """Output configuration."""

    format: OutputFormatEnum = Field(
        default=OutputFormatEnum.PARQUET, description="Output file format"
    )
    include_metadata: bool = Field(
        default=True, description="Include metadata in output"
    )


class MLScenarioYAMLSchema(BaseModel):
    """
    Complete ML Scenario YAML Schema.

    This is the root model for validating scenario YAML files.
    """

    scenario: ScenarioInfoSchema = Field(
        ..., description="Scenario metadata (required)"
    )
    data_source: DataSourceSchema = Field(
        default_factory=DataSourceSchema,
        description="Data source filters (optional, defaults to all)",
    )
    features: FeaturesSchema = Field(
        default_factory=FeaturesSchema,
        description="Feature selection (optional)",
    )
    splitting: SplittingSchema = Field(
        ..., description="Splitting configuration (required)"
    )
    preprocessing: PreprocessingSchema = Field(
        default_factory=PreprocessingSchema,
        description="Preprocessing config (optional)",
    )
    output: OutputSchema = Field(
        default_factory=OutputSchema,
        description="Output format (optional)",
    )


# =============================================================================
# VALIDATION RESULT MODELS
# =============================================================================


class ValidationErrorDetail(BaseModel):
    """Single validation error with context."""

    field: str = Field(..., description="Field path that failed validation")
    message: str = Field(..., description="Human-readable error message")
    expected: Optional[str] = Field(None, description="Expected value/type")
    got: Optional[str] = Field(None, description="Actual value received")


class ValidationResult(BaseModel):
    """Result of YAML validation."""

    valid: bool = Field(..., description="Whether the YAML is valid")
    errors: List[ValidationErrorDetail] = Field(
        default_factory=list, description="List of validation errors"
    )
    warnings: List[str] = Field(
        default_factory=list, description="List of warnings (non-blocking)"
    )
    parsed_config: Optional[Dict[str, Any]] = Field(
        None, description="Parsed config if valid"
    )


# =============================================================================
# VALIDATION SERVICE
# =============================================================================


class YAMLValidatorService:
    """
    Service for validating ML Scenario YAML configurations.

    Usage:
        validator = YAMLValidatorService()
        result = validator.validate_yaml_string(yaml_content)
        if not result.valid:
            for error in result.errors:
                print(f"{error.field}: {error.message}")
    """

    @staticmethod
    def validate_yaml_string(yaml_content: str) -> ValidationResult:
        """
        Validate YAML string against MLScenarioYAMLSchema.

        Args:
            yaml_content: Raw YAML string

        Returns:
            ValidationResult with valid flag, errors, warnings, and parsed config
        """
        errors: List[ValidationErrorDetail] = []
        warnings: List[str] = []

        # Step 1: Parse YAML
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationErrorDetail(
                        field="<yaml>",
                        message=f"Invalid YAML syntax: {str(e)}",
                    )
                ],
            )

        if not isinstance(data, dict):
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationErrorDetail(
                        field="<root>",
                        message="YAML must be a dictionary/object at the root level",
                        expected="object",
                        got=type(data).__name__,
                    )
                ],
            )

        # Step 2: Validate against Pydantic schema
        try:
            validated = MLScenarioYAMLSchema.model_validate(data)
            return ValidationResult(
                valid=True,
                errors=[],
                warnings=warnings,
                parsed_config=validated.model_dump(mode="json"),
            )
        except ValidationError as e:
            for err in e.errors():
                field_path = ".".join(str(loc) for loc in err["loc"])
                error_type = err["type"]
                error_msg = err["msg"]

                # Make error messages more user-friendly
                if error_type == "missing":
                    message = f"Required field is missing"
                elif error_type == "enum":
                    # Extract allowed values from context
                    ctx = err.get("ctx", {})
                    expected = ctx.get("expected", "")
                    message = f"Invalid value. {error_msg}"
                else:
                    message = error_msg

                errors.append(
                    ValidationErrorDetail(
                        field=field_path or "<root>",
                        message=message,
                        expected=err.get("ctx", {}).get("expected"),
                        got=str(err.get("input")) if err.get("input") else None,
                    )
                )

            return ValidationResult(
                valid=False,
                errors=errors,
                warnings=warnings,
            )

    @staticmethod
    def validate_yaml_file(file_path: Path) -> ValidationResult:
        """Validate YAML file from disk."""
        try:
            content = file_path.read_text(encoding="utf-8")
            return YAMLValidatorService.validate_yaml_string(content)
        except FileNotFoundError:
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationErrorDetail(
                        field="<file>",
                        message=f"File not found: {file_path}",
                    )
                ],
            )
        except Exception as e:
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationErrorDetail(
                        field="<file>",
                        message=f"Error reading file: {str(e)}",
                    )
                ],
            )

    @staticmethod
    def get_schema_documentation() -> Dict[str, Any]:
        """
        Generate schema documentation for frontend display.

        Returns a structured dict with section info, field descriptions,
        and valid values for enums.
        """
        return {
            "sections": [
                {
                    "name": "scenario",
                    "required": True,
                    "description": "Scenario metadata",
                    "fields": [
                        {
                            "name": "name",
                            "type": "string",
                            "required": True,
                            "description": "Unique scenario name",
                        },
                        {
                            "name": "description",
                            "type": "string",
                            "required": False,
                            "description": "Human-readable description",
                        },
                        {
                            "name": "version",
                            "type": "string",
                            "required": False,
                            "default": "1.0",
                            "description": "Version string",
                        },
                    ],
                },
                {
                    "name": "data_source",
                    "required": False,
                    "description": "Filters for selecting builds from database",
                    "fields": [
                        {
                            "name": "repositories.filter_by",
                            "type": "enum",
                            "required": False,
                            "default": "all",
                            "values": [e.value for e in FilterByEnum],
                            "description": "How to filter repositories",
                        },
                        {
                            "name": "repositories.languages",
                            "type": "list[string]",
                            "required": "if filter_by=by_language",
                            "description": "Languages to include",
                        },
                        {
                            "name": "builds.date_range.start",
                            "type": "date (YYYY-MM-DD)",
                            "required": False,
                            "description": "Filter builds after this date",
                        },
                        {
                            "name": "builds.conclusions",
                            "type": "list[string]",
                            "required": False,
                            "default": ["success", "failure"],
                            "description": "Build conclusions to include",
                        },
                        {
                            "name": "ci_provider",
                            "type": "string",
                            "required": False,
                            "default": "all",
                            "description": "CI provider: all, github_actions, circleci",
                        },
                    ],
                },
                {
                    "name": "features",
                    "required": False,
                    "description": "Feature selection configuration",
                    "fields": [
                        {
                            "name": "dag_features",
                            "type": "list[string]",
                            "required": False,
                            "description": "Feature patterns (wildcards: build_*, git_*, log_*)",
                            "example": ["build_*", "git_*", "history_*"],
                        },
                        {
                            "name": "scan_metrics",
                            "type": "object",
                            "required": False,
                            "description": "Scan metrics by tool: {sonarqube: [...], trivy: [...]}",
                        },
                    ],
                },
                {
                    "name": "splitting",
                    "required": True,
                    "description": "Data splitting strategy configuration",
                    "fields": [
                        {
                            "name": "strategy",
                            "type": "enum",
                            "required": True,
                            "values": [e.value for e in SplitStrategyEnum],
                            "description": "Splitting strategy to use",
                        },
                        {
                            "name": "group_by",
                            "type": "enum",
                            "required": False,
                            "default": "language_group",
                            "values": [e.value for e in GroupByDimensionEnum],
                            "description": "Dimension for grouping builds",
                        },
                        {
                            "name": "config.ratios",
                            "type": "object",
                            "required": False,
                            "default": {"train": 0.7, "val": 0.15, "test": 0.15},
                            "description": "Split ratios (must sum to 1.0)",
                        },
                        {
                            "name": "config.test_groups",
                            "type": "list[string]",
                            "required": "for leave_one_out, leave_two_out",
                            "description": "Groups to use as test set",
                        },
                        {
                            "name": "config.reduce_label",
                            "type": "int (0 or 1)",
                            "required": "for imbalanced_train",
                            "description": "Label to reduce: 0=success, 1=failure",
                        },
                        {
                            "name": "config.novelty_group",
                            "type": "string",
                            "required": "for extreme_novelty",
                            "description": "Group for novelty testing",
                        },
                    ],
                },
                {
                    "name": "preprocessing",
                    "required": False,
                    "description": "Data preprocessing options",
                    "fields": [
                        {
                            "name": "missing_values_strategy",
                            "type": "enum",
                            "required": False,
                            "default": "drop_row",
                            "values": [e.value for e in MissingValuesStrategyEnum],
                            "description": "How to handle missing values",
                        },
                        {
                            "name": "normalization_method",
                            "type": "enum",
                            "required": False,
                            "default": "z_score",
                            "values": [e.value for e in NormalizationMethodEnum],
                            "description": "Normalization method for numeric features",
                        },
                    ],
                },
                {
                    "name": "output",
                    "required": False,
                    "description": "Output file configuration",
                    "fields": [
                        {
                            "name": "format",
                            "type": "enum",
                            "required": False,
                            "default": "parquet",
                            "values": [e.value for e in OutputFormatEnum],
                            "description": "Output file format",
                        },
                        {
                            "name": "include_metadata",
                            "type": "boolean",
                            "required": False,
                            "default": True,
                            "description": "Include build metadata in output",
                        },
                    ],
                },
            ],
            "strategies": {
                "stratified_within_group": {
                    "description": "Split data within each group maintaining stratification",
                    "required_config": ["ratios", "stratify_by"],
                },
                "leave_one_out": {
                    "description": "Leave one group out for testing",
                    "required_config": ["test_groups"],
                },
                "leave_two_out": {
                    "description": "Leave two groups out for validation and testing",
                    "required_config": ["test_groups", "val_groups"],
                },
                "imbalanced_train": {
                    "description": "Reduce samples of one label in training set",
                    "required_config": ["reduce_label", "reduce_ratio"],
                },
                "extreme_novelty": {
                    "description": "All samples of specific group+label go to test only",
                    "required_config": ["novelty_group", "novelty_label"],
                },
            },
        }
