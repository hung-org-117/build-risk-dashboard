"""
Data Quality Service - Core evaluation logic for dataset quality assessment.

Evaluates enriched datasets and calculates individual scores for:
- Completeness: % features non-null
- Validity: % values within valid range (from FEATURE_REGISTRY)
- Consistency: % builds with all selected features
- Coverage: % successfully enriched builds
"""

import logging
import statistics
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from fastapi import HTTPException
from pymongo.database import Database

from app.entities.data_quality import (
    DataQualityMetric,
    DataQualityReport,
    HistogramBinCache,
    MetricSource,
    QualityEvaluationStatus,
    QualityIssue,
    QualityIssueSeverity,
    ScanMetricsSummary,
)
from app.repositories.data_quality_repository import DataQualityRepository
from app.repositories.feature_vector import FeatureVectorRepository
from app.repositories.training_enrichment_build import TrainingEnrichmentBuildRepository
from app.repositories.training_scenario import TrainingScenarioRepository
from app.services.feature_service import FeatureService

logger = logging.getLogger(__name__)


class DataQualityService:
    """Service for evaluating dataset quality."""

    def __init__(self, db: Database):
        self.db = db
        self.quality_repo = DataQualityRepository(db)
        self.scenario_repo = TrainingScenarioRepository(db)
        self.build_repo = TrainingEnrichmentBuildRepository(db)
        self.feature_vector_repo = FeatureVectorRepository(db)
        self.feature_service = FeatureService()

    def evaluate_version(self, scenario_id: str) -> DataQualityReport:
        """
        Run quality evaluation for a dataset version.

        Args:
            scenario_id: Scenario ID to evaluate

        Returns:
            DataQualityReport with evaluation results
        """
        # Check for existing running evaluation
        existing = self.quality_repo.find_pending_or_running(scenario_id)
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Quality evaluation is already in progress for this scenario",
            )

        # Get scenario
        scenario = self.scenario_repo.find_by_id(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

        # Check status (should be PROCESSED before quality check makes sense)
        if scenario.status != "processed" and scenario.status != "completed":
            # Allowed in processed or completed (if re-running)
            pass
            # Or raise error if strict

        report = DataQualityReport(
            scenario_id=ObjectId(scenario_id),
        )
        report.mark_started()

        try:
            # Get all enrichment builds for this scenario
            builds, _ = self.build_repo.find_by_scenario(scenario_id)

            if not builds:
                report.mark_failed("No enrichment builds found for this scenario")
                self.quality_repo.insert_one(report)
                return report

            # Get selected features (DAG features)
            selected_features = scenario.feature_config.dag_features or []

            if not selected_features:
                report.mark_failed("No features configured for this scenario")
                self.quality_repo.insert_one(report)
                return report

            # Get feature metadata for validity checks
            feature_metadata = self._get_feature_metadata(selected_features)

            # Calculate metrics
            report.total_builds = len(builds)
            report.total_features = len(selected_features)

            # Load feature vectors for all builds in batch
            raw_build_run_ids = [
                b.raw_build_run_id for b in builds if b.raw_build_run_id
            ]
            feature_vectors_map = (
                self.feature_vector_repo.find_many_by_raw_build_run_ids(
                    raw_build_run_ids
                )
            )

            # Create a helper class to hold build + features for analysis
            class BuildWithFeatures:
                def __init__(self, build, features):
                    self.build = build
                    self.features = features or {}

            builds_with_features = []
            for build in builds:
                fv = feature_vectors_map.get(str(build.raw_build_run_id))
                features = fv.features if fv else {}
                builds_with_features.append(BuildWithFeatures(build, features))

            # Calculate coverage score
            enriched_builds = [
                b for b in builds_with_features if b.features and len(b.features) > 0
            ]
            partial_builds = [
                b for b in enriched_builds if len(b.features) < len(selected_features)
            ]
            failed_builds = [
                b
                for b in builds_with_features
                if not b.features or len(b.features) == 0
            ]

            report.enriched_builds = len(enriched_builds)
            report.partial_builds = len(partial_builds)
            report.failed_builds = len(failed_builds)

            # Coverage: % successfully enriched builds
            report.coverage_score = (
                (len(enriched_builds) / len(builds) * 100) if builds else 0.0
            )

            # Calculate feature metrics
            report.feature_metrics = self._calculate_feature_metrics(
                builds=enriched_builds,
                selected_features=selected_features,
                feature_metadata=feature_metadata,
            )

            # Calculate completeness score
            report.completeness_score = self._calculate_completeness_score(
                report.feature_metrics
            )

            # Calculate validity score
            report.validity_score = self._calculate_validity_score(
                report.feature_metrics
            )

            # Calculate consistency score
            report.consistency_score = self._calculate_consistency_score(
                builds=enriched_builds,
                selected_features=selected_features,
            )

            # Detect issues
            report.issues = self._detect_issues(
                report=report,
                feature_metrics=report.feature_metrics,
            )
            report.features_with_issues = len(
                [m for m in report.feature_metrics if m.issues]
            )

            report.mark_completed()

            logger.info(
                f"Quality evaluation completed for scenario {scenario_id}: "
                f"completeness={report.completeness_score:.1f}, "
                f"validity={report.validity_score:.1f}, "
                f"consistency={report.consistency_score:.1f}, "
                f"coverage={report.coverage_score:.1f}"
            )

        except Exception as e:
            logger.error(f"Quality evaluation failed for scenario {scenario_id}: {e}")
            report.mark_failed(str(e))

        # Save report
        self.quality_repo.insert_one(report)
        return report

    def get_report(self, scenario_id: str) -> Optional[DataQualityReport]:
        """Get the latest quality report for a scenario."""
        return self.quality_repo.find_by_scenario(scenario_id)

    def _get_feature_metadata(
        self, selected_features: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get metadata for selected features including valid_range.

        Returns dict: {feature_name: {data_type, valid_range, valid_values, ...}}
        """
        all_features = self.feature_service.list_features(include_default=True)
        metadata = {}

        for feature in all_features:
            feature_name = feature["name"]
            if feature_name in selected_features:
                metadata[feature_name] = {
                    "data_type": feature.get("data_type", "unknown"),
                    "valid_range": feature.get("valid_range"),
                    "valid_values": feature.get("valid_values"),
                }

        return metadata

    def _calculate_feature_metrics(
        self,
        builds: List[Any],  # BuildWithFeatures objects with .features attribute
        selected_features: List[str],
        feature_metadata: Dict[str, Dict[str, Any]],
    ) -> List[DataQualityMetric]:
        """Calculate quality metrics for each feature."""
        metrics = []

        for feature_name in selected_features:
            meta = feature_metadata.get(feature_name, {})
            data_type = meta.get("data_type", "unknown")
            valid_range = meta.get("valid_range")
            valid_values = meta.get("valid_values")

            # Collect all values for this feature
            values = []
            for build in builds:
                if build.features and feature_name in build.features:
                    values.append(build.features[feature_name])
                else:
                    values.append(None)

            # Calculate metrics
            metric = self._analyze_feature_values(
                feature_name=feature_name,
                values=values,
                data_type=data_type,
                valid_range=valid_range,
                valid_values=valid_values,
            )
            metrics.append(metric)

        return metrics

    def _analyze_feature_values(
        self,
        feature_name: str,
        values: List[Any],
        data_type: str,
        valid_range: Optional[Tuple[float, float]] = None,
        valid_values: Optional[List[str]] = None,
    ) -> DataQualityMetric:
        """Analyze values for a single feature and create metric."""
        total = len(values)
        null_count = sum(1 for v in values if v is None)
        non_null_values = [v for v in values if v is not None]

        metric = DataQualityMetric(
            feature_name=feature_name,
            data_type=data_type,
            total_values=total,
            null_count=null_count,
            completeness_pct=(total - null_count) / total * 100 if total > 0 else 0.0,
            expected_range=valid_range,
            expected_values=valid_values,
        )

        if not non_null_values:
            metric.validity_pct = 100.0  # No values to validate
            return metric

        # Select analysis method based on data type
        if data_type in ("integer", "float", "numeric"):
            return self._analyze_numeric_feature(
                metric, feature_name, non_null_values, valid_range
            )
        elif data_type == "string":
            return self._analyze_string_feature(metric, non_null_values, valid_values)
        elif data_type == "boolean":
            return self._analyze_boolean_feature(metric, non_null_values)
        elif data_type == "list":
            return self._analyze_list_feature(metric, non_null_values)

        return metric

    def _analyze_numeric_feature(
        self,
        metric: DataQualityMetric,
        feature_name: str,
        values: List[Any],
        valid_range: Optional[Tuple[float, float]],
    ) -> DataQualityMetric:
        """Analyze numeric feature values."""
        numeric_values = []
        for v in values:
            try:
                numeric_values.append(float(v))
            except (ValueError, TypeError):
                logger.debug(
                    f"Skipping non-numeric value '{v}' for feature '{feature_name}'"
                )

        if numeric_values:
            metric.min_value = min(numeric_values)
            metric.max_value = max(numeric_values)
            metric.mean_value = statistics.mean(numeric_values)
            if len(numeric_values) > 1:
                metric.std_dev = statistics.stdev(numeric_values)

            # Range validation
            if valid_range:
                min_valid, max_valid = valid_range
                out_of_range = [
                    v for v in numeric_values if v < min_valid or v > max_valid
                ]
                metric.out_of_range_count = len(out_of_range)
                metric.validity_pct = (
                    (len(numeric_values) - len(out_of_range))
                    / len(numeric_values)
                    * 100
                )

                if metric.out_of_range_count > 0:
                    metric.issues.append(
                        f"{metric.out_of_range_count} values outside range "
                        f"[{min_valid}, {max_valid}]"
                    )

        return metric

    def _analyze_string_feature(
        self,
        metric: DataQualityMetric,
        values: List[Any],
        valid_values: Optional[List[str]],
    ) -> DataQualityMetric:
        """Analyze string feature values."""
        string_values = [str(v) for v in values]
        metric.unique_count = len(set(string_values))
        metric.empty_string_count = sum(1 for v in string_values if not v.strip())

        # Value validation for categorical
        if valid_values:
            invalid = [v for v in string_values if v not in valid_values]
            metric.invalid_value_count = len(invalid)
            metric.validity_pct = (
                (len(string_values) - len(invalid)) / len(string_values) * 100
            )

            if metric.invalid_value_count > 0:
                metric.issues.append(
                    f"{metric.invalid_value_count} values not in allowed list"
                )

        return metric

    def _analyze_boolean_feature(
        self,
        metric: DataQualityMetric,
        values: List[Any],
    ) -> DataQualityMetric:
        """Analyze boolean feature values."""
        bool_values = [bool(v) for v in values]
        true_count = sum(bool_values)
        metric.unique_count = (
            2 if true_count > 0 and true_count < len(bool_values) else 1
        )
        metric.validity_pct = 100.0  # All booleans are valid
        return metric

    def _analyze_list_feature(
        self,
        metric: DataQualityMetric,
        values: List[Any],
    ) -> DataQualityMetric:
        """Analyze list feature values."""
        metric.unique_count = len({str(v) for v in values})
        metric.validity_pct = 100.0
        return metric

    def _calculate_completeness_score(self, metrics: List[DataQualityMetric]) -> float:
        """Calculate overall completeness score from feature metrics."""
        if not metrics:
            return 0.0

        return sum(m.completeness_pct for m in metrics) / len(metrics)

    def _calculate_validity_score(self, metrics: List[DataQualityMetric]) -> float:
        """Calculate overall validity score from feature metrics."""
        if not metrics:
            return 0.0

        return sum(m.validity_pct for m in metrics) / len(metrics)

    def _calculate_consistency_score(
        self,
        builds: List[Any],  # BuildWithFeatures objects with .features attribute
        selected_features: List[str],
    ) -> float:
        """
        Calculate consistency score: % builds with all selected features present.
        """
        if not builds or not selected_features:
            return 0.0

        complete_builds = 0
        for build in builds:
            if not build.features:
                continue
            present_features = set(build.features.keys())
            if present_features >= set(selected_features):
                complete_builds += 1

        return (complete_builds / len(builds)) * 100

    def _detect_issues(
        self,
        report: DataQualityReport,
        feature_metrics: List[DataQualityMetric],
    ) -> List[QualityIssue]:
        """Detect quality issues and create issue list."""
        issues: List[QualityIssue] = []

        # Coverage issues
        if report.coverage_score < 50:
            issues.append(
                QualityIssue(
                    severity=QualityIssueSeverity.ERROR,
                    category="coverage",
                    message=f"Low coverage: only {report.coverage_score:.1f}% of builds enriched",
                    details={
                        "enriched": report.enriched_builds,
                        "total": report.total_builds,
                    },
                )
            )
        elif report.coverage_score < 80:
            issues.append(
                QualityIssue(
                    severity=QualityIssueSeverity.WARNING,
                    category="coverage",
                    message=f"Moderate coverage: {report.coverage_score:.1f}% of builds enriched",
                )
            )

        # Completeness issues
        if report.completeness_score < 50:
            issues.append(
                QualityIssue(
                    severity=QualityIssueSeverity.ERROR,
                    category="completeness",
                    message=(
                        f"Low completeness: average {report.completeness_score:.1f}% "
                        "non-null values"
                    ),
                )
            )

        # Feature-level issues
        for metric in feature_metrics:
            # Low completeness for individual features
            if metric.completeness_pct < 30:
                missing_pct = 100 - metric.completeness_pct
                miss_msg = f"Low completeness: {missing_pct:.1f}% missing"
                if miss_msg not in metric.issues:
                    metric.issues.append(miss_msg)

                issues.append(
                    QualityIssue(
                        severity=QualityIssueSeverity.WARNING,
                        category="completeness",
                        feature_name=metric.feature_name,
                        message=(
                            f"Feature '{metric.feature_name}' has {metric.null_count} "
                            f"null values ({missing_pct:.1f}% missing)"
                        ),
                    )
                )

            # Range violations
            if metric.out_of_range_count > 0:
                issues.append(
                    QualityIssue(
                        severity=QualityIssueSeverity.WARNING,
                        category="validity",
                        feature_name=metric.feature_name,
                        message=(
                            f"Feature '{metric.feature_name}' has "
                            f"{metric.out_of_range_count} out-of-range values"
                        ),
                        details={"expected_range": metric.expected_range},
                    )
                )

            # Invalid categorical values
            if metric.invalid_value_count > 0:
                issues.append(
                    QualityIssue(
                        severity=QualityIssueSeverity.WARNING,
                        category="validity",
                        feature_name=metric.feature_name,
                        message=(
                            f"Feature '{metric.feature_name}' has "
                            f"{metric.invalid_value_count} invalid values"
                        ),
                    )
                )

        # Consistency issues
        if report.consistency_score < 50:
            issues.append(
                QualityIssue(
                    severity=QualityIssueSeverity.WARNING,
                    category="consistency",
                    message=(
                        f"Low consistency: only {report.consistency_score:.1f}% "
                        "of builds have all features"
                    ),
                )
            )

        return issues

    # =========================================================================
    # INCREMENTAL UPDATE METHODS (for real-time quality tracking)
    # =========================================================================

    def get_or_create_report(self, scenario_id: str) -> DataQualityReport:
        """
        Get existing report for scenario or create a new one.
        Used for incremental updates during processing.
        """
        existing = self.quality_repo.find_by_scenario(scenario_id)
        if existing:
            return existing

        # Create new report in RUNNING state
        report = DataQualityReport(
            scenario_id=ObjectId(scenario_id),
            status=QualityEvaluationStatus.RUNNING,
        )
        report.started_at = (
            report.started_at or __import__("datetime").datetime.utcnow()
        )
        self.quality_repo.insert_one(report)
        return report

    def update_feature_metrics_incremental(
        self,
        scenario_id: str,
        feature_name: str,
        value: any,
        data_type: str = "unknown",
    ) -> None:
        """
        Update quality metrics incrementally after a feature is extracted.
        Called after each build's features are extracted.

        Args:
            scenario_id: Scenario ID
            feature_name: Name of the extracted feature
            value: The extracted value (can be None)
            data_type: Data type of the feature
        """
        report = self.get_or_create_report(scenario_id)

        # Find or create metric for this feature
        metric = next(
            (m for m in report.feature_metrics if m.feature_name == feature_name),
            None,
        )

        if not metric:
            metric = DataQualityMetric(
                feature_name=feature_name,
                source=MetricSource.FEATURE,
                data_type=data_type,
            )
            report.feature_metrics.append(metric)

        # Update counts
        metric.total_values += 1
        if value is None:
            metric.null_count += 1

        # Recalculate completeness
        if metric.total_values > 0:
            metric.completeness_pct = (
                (metric.total_values - metric.null_count) / metric.total_values * 100
            )

        # Update in DB
        self.quality_repo.update_one(
            str(report.id),
            {"feature_metrics": [m.dict() for m in report.feature_metrics]},
        )

    def update_scan_metrics_incremental(
        self,
        scenario_id: str,
        scan_type: str,  # "trivy" or "sonarqube"
        has_metrics: bool,
    ) -> None:
        """
        Update scan metrics summary incrementally after a scan completes.
        Called after each scan finishes.

        Args:
            scenario_id: Scenario ID
            scan_type: Type of scan ("trivy" or "sonarqube")
            has_metrics: Whether the scan produced metrics
        """
        report = self.get_or_create_report(scenario_id)
        summary = report.scan_metrics_summary or ScanMetricsSummary()

        if scan_type == "trivy":
            summary.trivy_builds_scanned += 1
            if has_metrics:
                summary.trivy_builds_with_metrics += 1
            if summary.trivy_builds_scanned > 0:
                summary.trivy_coverage_pct = (
                    summary.trivy_builds_with_metrics
                    / summary.trivy_builds_scanned
                    * 100
                )
        elif scan_type == "sonarqube":
            summary.sonarqube_builds_scanned += 1
            if has_metrics:
                summary.sonarqube_builds_with_metrics += 1
            if summary.sonarqube_builds_scanned > 0:
                summary.sonarqube_coverage_pct = (
                    summary.sonarqube_builds_with_metrics
                    / summary.sonarqube_builds_scanned
                    * 100
                )

        # Update in DB
        self.quality_repo.update_one(
            str(report.id),
            {"scan_metrics_summary": summary.dict()},
        )

    def _calculate_feature_distributions(
        self,
        scenario_id: str,
        feature_metrics: list,
        bins: int = 20,
    ) -> None:
        """
        Calculate and store histogram distributions for all numeric features.

        Updates feature_metrics in-place with distribution_bins.
        Uses MongoDB aggregation to efficiently compute histograms.
        """
        from app.repositories.training_enrichment_build import (
            TrainingEnrichmentBuildRepository,
        )

        build_repo = TrainingEnrichmentBuildRepository(self.db)

        for metric in feature_metrics:
            if metric.data_type not in ("integer", "float", "numeric"):
                continue

            # Use aggregation to get stats and samples
            agg_result = build_repo.aggregate_feature_stats(
                scenario_id, metric.feature_name
            )
            stats = agg_result.get("stats")
            samples = agg_result.get("samples", [])

            if not stats or stats.get("count", 0) == 0:
                continue

            # Update metric with aggregated stats
            metric.min_value = stats.get("min")
            metric.max_value = stats.get("max")
            metric.mean_value = stats.get("avg")
            metric.std_dev = stats.get("stdDev")

            min_val = stats.get("min", 0)
            max_val = stats.get("max", 0)
            total_count = stats.get("count", 0)

            # Calculate histogram bins
            bin_width = (max_val - min_val) / bins if max_val > min_val else 1
            n = len(samples)

            distribution_bins = []
            for i in range(bins):
                bin_min = min_val + i * bin_width
                bin_max = min_val + (i + 1) * bin_width

                # Count from samples
                if i == bins - 1:
                    count = sum(1 for v in samples if bin_min <= v <= bin_max)
                else:
                    count = sum(1 for v in samples if bin_min <= v < bin_max)

                # Scale to estimated total
                estimated_count = int(count * total_count / n) if n > 0 else 0

                distribution_bins.append(
                    HistogramBinCache(
                        min_value=round(bin_min, 4),
                        max_value=round(bin_max, 4),
                        count=estimated_count,
                        percentage=(
                            round(estimated_count / total_count * 100, 1)
                            if total_count > 0
                            else 0
                        ),
                    )
                )

            metric.distribution_bins = distribution_bins

    def finalize_quality_report(self, scenario_id: str) -> DataQualityReport:
        """
        Finalize quality report after enrichment is complete.
        Calculates final scores and marks report as COMPLETED.

        Called from check_and_notify_enrichment_completed.
        """
        report = self.quality_repo.find_by_scenario(scenario_id)
        if not report:
            # If no report exists, run full evaluation
            return self.evaluate_version(scenario_id)

        # If feature_metrics is empty, run full evaluation to calculate proper scores
        # This handles the case where incremental updates were not used
        if not report.feature_metrics:
            logger.info(
                f"No feature_metrics found for scenario {scenario_id}, "
                "running full evaluation"
            )
            # Delete the existing empty report first
            self.quality_repo.delete_by_scenario(scenario_id)
            return self.evaluate_version(scenario_id)

        # Get scenario for build counts
        scenario = self.scenario_repo.find_by_id(scenario_id)
        if scenario:
            report.total_builds = scenario.builds_total or 0
            report.enriched_builds = scenario.builds_features_extracted or 0
            report.failed_builds = scenario.builds_features_extracted_failed or 0
            report.total_features = len(scenario.feature_config.dag_features or [])

            # Calculate coverage score
            if report.total_builds > 0:
                report.coverage_score = (
                    report.enriched_builds / report.total_builds * 100
                )

            # Populate scan metrics summary from scenario stats
            scans_total = scenario.scans_total or 0
            scans_completed = scenario.scans_completed or 0

            # Get scan tool config to determine which tools are configured
            scan_config = scenario.feature_config.scan_tool_config or {}
            trivy_configured = "trivy" in scan_config
            sonarqube_configured = "sonarqube" in scan_config

            scan_summary = ScanMetricsSummary()

            # Estimate per-tool based on configured tools
            # Each commit can have Trivy and/or SonarQube scans
            if trivy_configured and sonarqube_configured:
                # Both configured - split counts evenly (approximation)
                half_total = scans_total // 2
                half_completed = scans_completed // 2
                scan_summary.trivy_builds_scanned = half_total
                scan_summary.trivy_builds_with_metrics = half_completed
                scan_summary.sonarqube_builds_scanned = scans_total - half_total
                scan_summary.sonarqube_builds_with_metrics = (
                    scans_completed - half_completed
                )
            elif trivy_configured:
                scan_summary.trivy_builds_scanned = scans_total
                scan_summary.trivy_builds_with_metrics = scans_completed
            elif sonarqube_configured:
                scan_summary.sonarqube_builds_scanned = scans_total
                scan_summary.sonarqube_builds_with_metrics = scans_completed

            # Calculate coverage percentages
            if scan_summary.trivy_builds_scanned > 0:
                scan_summary.trivy_coverage_pct = (
                    scan_summary.trivy_builds_with_metrics
                    / scan_summary.trivy_builds_scanned
                    * 100
                )
            if scan_summary.sonarqube_builds_scanned > 0:
                scan_summary.sonarqube_coverage_pct = (
                    scan_summary.sonarqube_builds_with_metrics
                    / scan_summary.sonarqube_builds_scanned
                    * 100
                )

            report.scan_metrics_summary = scan_summary

        # Calculate feature distributions (histogram bins) for numeric features
        self._calculate_feature_distributions(scenario_id, report.feature_metrics)

        # Calculate completeness score from feature metrics
        report.completeness_score = self._calculate_completeness_score(
            report.feature_metrics
        )

        # Calculate validity score
        report.validity_score = self._calculate_validity_score(report.feature_metrics)

        report.mark_completed()

        # Update in DB (including feature_metrics with distributions)
        self.quality_repo.update_one(
            str(report.id),
            {
                "status": (
                    report.status.value
                    if hasattr(report.status, "value")
                    else report.status
                ),
                "completeness_score": report.completeness_score,
                "validity_score": report.validity_score,
                "consistency_score": report.consistency_score,
                "coverage_score": report.coverage_score,
                "total_builds": report.total_builds,
                "enriched_builds": report.enriched_builds,
                "failed_builds": report.failed_builds,
                "total_features": report.total_features,
                "scan_metrics_summary": report.scan_metrics_summary.dict(),
                "feature_metrics": [m.dict() for m in report.feature_metrics],
                "completed_at": report.completed_at,
            },
        )

        logger.info(
            f"Quality report finalized for scenario {scenario_id}: "
            f"completeness={report.completeness_score:.1f}"
        )

        return report
