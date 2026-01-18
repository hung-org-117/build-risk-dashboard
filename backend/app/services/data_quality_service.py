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
from pymongo.database import Database

from app.entities.data_quality import (
    DataQualityMetric,
    DataQualityReport,
    HistogramBinCache,
    MetricSource,
    QualityEvaluationStatus,
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
        # Auto-fetch valid_range from registry if not explicitly provided
        if valid_range is None:
            from app.tasks.pipeline.feature_dag._feature_definitions import (
                get_feature_definition,
            )

            defn = get_feature_definition(feature_name)
            if defn and defn.valid_range:
                valid_range = defn.valid_range
                metric.expected_range = valid_range

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
                out_of_range = []
                for v in numeric_values:
                    if min_valid is not None and v < min_valid:
                        out_of_range.append(v)
                    elif max_valid is not None and v > max_valid:
                        out_of_range.append(v)
                metric.out_of_range_count = len(out_of_range)
                metric.validity_pct = (
                    (len(numeric_values) - len(out_of_range))
                    / len(numeric_values)
                    * 100
                )

                if metric.out_of_range_count > 0:
                    range_str = f"[{min_valid}, {max_valid}]"
                    metric.issues.append(
                        f"{metric.out_of_range_count} values outside range {range_str}"
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
        Uses MongoDB aggregation ($bucketAuto) to efficiently compute histograms.
        """
        from app.repositories.training_enrichment_build import (
            TrainingEnrichmentBuildRepository,
        )

        build_repo = TrainingEnrichmentBuildRepository(self.db)

        for metric in feature_metrics:
            if metric.data_type not in ("integer", "float", "numeric"):
                continue

            # Use new $bucketAuto aggregation for accurate histograms
            agg_result = build_repo.aggregate_numeric_stats_and_distribution(
                scenario_id, metric.feature_name, bins=bins
            )

            stats = agg_result.get("stats")
            buckets = agg_result.get("bins", [])

            if not stats or stats.get("count", 0) == 0:
                continue

            # Update metric with aggregated stats if not already set or more accurate
            metric.min_value = stats.get("min")
            metric.max_value = stats.get("max")
            metric.mean_value = stats.get("avg")
            metric.std_dev = stats.get("stdDev")

            total_count = stats.get("count", 0)

            distribution_bins = []

            for b in buckets:
                # $bucketAuto returns _id with min/max bounds
                id_bounds = b.get("_id", {})
                b_min = id_bounds.get("min")
                b_max = id_bounds.get("max")

                # Fallback to explicit output projection
                if b_min is None:
                    b_min = b.get("min")
                if b_max is None:
                    b_max = b.get("max")

                if b_min is None:
                    continue
                if b_max is None:
                    b_max = b_min

                count = b.get("count", 0)

                distribution_bins.append(
                    HistogramBinCache(
                        min_value=round(float(b_min), 4),
                        max_value=round(float(b_max), 4),
                        count=count,
                        percentage=(
                            round(count / total_count * 100, 1)
                            if total_count > 0
                            else 0
                        ),
                    )
                )

            # Sort bins by min_value
            distribution_bins.sort(key=lambda x: x.min_value)

            metric.distribution_bins = distribution_bins

    # =========================================================================
    # SEPARATE FINALIZATION METHODS
    # =========================================================================

    def finalize_feature_quality_report(self, scenario_id: str) -> DataQualityReport:
        """
        Finalize feature extraction portion of quality report.
        Called after feature extraction completes.

        Updates: feature_metrics, completeness_score, validity_score, coverage_score
        """
        report = self.get_or_create_report(scenario_id)
        scenario = self.scenario_repo.find_by_id(scenario_id)

        if not scenario:
            logger.warning(f"Scenario {scenario_id} not found for feature finalization")
            return report

        # Update build counts from scenario
        report.total_builds = scenario.builds_total or 0
        report.enriched_builds = scenario.builds_features_extracted or 0
        report.failed_builds = scenario.builds_features_extracted_failed or 0
        report.total_features = len(scenario.feature_config.dag_features or [])

        # Calculate coverage score
        if report.total_builds > 0:
            report.coverage_score = report.enriched_builds / report.total_builds * 100

        # If no feature_metrics from incremental updates, run full evaluation
        if not report.feature_metrics:
            logger.info("No feature_metrics found, running full feature evaluation")
            # Run full evaluation but only for features
            return self._run_full_feature_evaluation(scenario_id, report)

        # Calculate distributions for numeric features
        self._calculate_feature_distributions(scenario_id, report.feature_metrics)

        # Calculate scores from feature metrics
        report.completeness_score = self._calculate_completeness_score(
            report.feature_metrics
        )
        report.validity_score = self._calculate_validity_score(report.feature_metrics)

        # Update in DB
        self.quality_repo.update_one(
            str(report.id),
            {
                "completeness_score": report.completeness_score,
                "validity_score": report.validity_score,
                "coverage_score": report.coverage_score,
                "total_builds": report.total_builds,
                "enriched_builds": report.enriched_builds,
                "failed_builds": report.failed_builds,
                "total_features": report.total_features,
                "feature_metrics": [m.dict() for m in report.feature_metrics],
            },
        )

        logger.info(
            f"Feature quality report finalized for scenario {scenario_id}: "
            f"completeness={report.completeness_score:.1f}"
        )

        return report

    def finalize_all_scan_reports(self, scenario_id: str) -> DataQualityReport:
        """
        Finalize all scan reports (Trivy + SonarQube) in one call.
        Called when all scans complete (scans_completed + scans_failed >= scans_total).

        Combines finalize_trivy_scan_report and finalize_sonarqube_scan_report.
        """
        from app.entities.sonar_commit_scan import SonarScanStatus
        from app.entities.trivy_commit_scan import TrivyScanStatus
        from app.repositories.sonar_commit_scan import SonarCommitScanRepository
        from app.repositories.trivy_commit_scan import TrivyCommitScanRepository

        report = self.get_or_create_report(scenario_id)
        scenario = self.scenario_repo.find_by_id(scenario_id)

        if not scenario:
            logger.warning(f"Scenario {scenario_id} not found for scan finalization")
            return report

        summary = report.scan_metrics_summary or ScanMetricsSummary()
        scan_config = getattr(scenario.feature_config, "scan_metrics", {}) or {}

        # === Trivy ===
        trivy_repo = TrivyCommitScanRepository(self.db)
        trivy_total = trivy_repo.count_by_scenario(ObjectId(scenario_id))
        trivy_completed = trivy_repo.count_by_scenario_and_status(
            ObjectId(scenario_id), TrivyScanStatus.COMPLETED
        )

        summary.trivy_builds_scanned = trivy_total
        summary.trivy_builds_with_metrics = trivy_completed
        summary.trivy_coverage_pct = (
            (trivy_completed / trivy_total * 100) if trivy_total > 0 else 0.0
        )

        scan_distributions = []

        trivy_metrics = scan_config.get("trivy", [])
        if trivy_metrics:
            trivy_metric_items = self._calculate_scan_metric_distributions(
                scenario_id, trivy_metrics, prefix="trivy_"
            )
            scan_distributions.extend(trivy_metric_items)

        # === SonarQube ===
        sonar_repo = SonarCommitScanRepository(self.db)
        sonar_total = sonar_repo.count_by_scenario(ObjectId(scenario_id))
        sonar_completed = sonar_repo.count_by_scenario_and_status(
            ObjectId(scenario_id), SonarScanStatus.COMPLETED
        )

        summary.sonarqube_builds_scanned = sonar_total
        summary.sonarqube_builds_with_metrics = sonar_completed
        summary.sonarqube_coverage_pct = (
            (sonar_completed / sonar_total * 100) if sonar_total > 0 else 0.0
        )

        sonar_metrics = scan_config.get("sonarqube", [])
        if sonar_metrics:
            sonar_metric_items = self._calculate_scan_metric_distributions(
                scenario_id, sonar_metrics, prefix="sonar_"
            )
            scan_distributions.extend(sonar_metric_items)

        report.scan_metrics_summary = summary
        report.scan_metric_distributions = scan_distributions

        # Update in DB
        self.quality_repo.update_one(
            str(report.id),
            {
                "scan_metrics_summary": summary.dict(),
                "scan_metric_distributions": [m.dict() for m in scan_distributions],
            },
        )

        logger.info(
            f"All scan reports finalized for scenario {scenario_id}: "
            f"Trivy {trivy_completed}/{trivy_total}, "
            f"SonarQube {sonar_completed}/{sonar_total}"
        )

        return report

    def _calculate_scan_metric_distributions(
        self,
        scenario_id: str,
        metric_names: List[str],
        prefix: str,
        bins: int = 20,
    ) -> List[DataQualityMetric]:
        """
        Calculate statistics and histogram distributions for scan metrics.

        Args:
            scenario_id: Scenario ID
            metric_names: List of metric names (without prefix)
            prefix: Metric prefix ("trivy_" or "sonar_")
            bins: Number of histogram bins

        Returns:
            List of DataQualityMetric objects with distributions
        """
        from app.repositories.training_enrichment_build import (
            TrainingEnrichmentBuildRepository,
        )

        build_repo = TrainingEnrichmentBuildRepository(self.db)
        metrics = []

        for metric_name in metric_names:
            # Full metric name with prefix (e.g., "trivy_vulnerability_critical")
            full_metric_name = f"{prefix}{metric_name}"

            # Use the new aggregation method
            agg_result = build_repo.aggregate_scan_metrics_stats_and_distribution(
                scenario_id, full_metric_name, bins=bins
            )

            stats = agg_result.get("stats")
            buckets = agg_result.get("bins", [])

            if not stats or stats.get("count", 0) == 0:
                continue

            # Create DataQualityMetric for this scan metric
            source = (
                MetricSource.TRIVY if prefix == "trivy_" else MetricSource.SONARQUBE
            )

            metric = DataQualityMetric(
                feature_name=full_metric_name,
                source=source,
                data_type="numeric",
                total_values=stats.get("count", 0),
                null_count=0,  # Non-null values only from aggregation
                completeness_pct=100.0,  # All values present if they reached here
                min_value=stats.get("min"),
                max_value=stats.get("max"),
                mean_value=stats.get("avg"),
                std_dev=stats.get("stdDev"),
            )

            # Add histogram bins
            total_count = stats.get("count", 0)
            distribution_bins = []

            for b in buckets:
                id_bounds = b.get("_id", {})
                b_min = id_bounds.get("min") or b.get("min")
                b_max = id_bounds.get("max") or b.get("max")

                if b_min is None:
                    continue
                if b_max is None:
                    b_max = b_min

                count = b.get("count", 0)

                distribution_bins.append(
                    HistogramBinCache(
                        min_value=round(float(b_min), 4),
                        max_value=round(float(b_max), 4),
                        count=count,
                        percentage=(
                            round(count / total_count * 100, 1)
                            if total_count > 0
                            else 0
                        ),
                    )
                )

            distribution_bins.sort(key=lambda x: x.min_value)
            metric.distribution_bins = distribution_bins
            metrics.append(metric)

        return metrics

    def _run_full_feature_evaluation(
        self, scenario_id: str, report: DataQualityReport
    ) -> DataQualityReport:
        """Run full feature evaluation when incremental metrics are not available."""
        scenario = self.scenario_repo.find_by_id(scenario_id)
        if not scenario:
            return report

        try:
            builds, _ = self.build_repo.find_by_scenario(scenario_id)
            if not builds:
                return report

            selected_features = scenario.feature_config.dag_features or []
            if not selected_features:
                return report

            feature_metadata = self._get_feature_metadata(selected_features)

            # Load feature vectors
            feature_vector_ids = [
                b.feature_vector_id for b in builds if b.feature_vector_id
            ]
            feature_vectors_map = self.feature_vector_repo.find_many_by_ids(
                feature_vector_ids
            )

            class BuildWithFeatures:
                def __init__(self, build, features):
                    self.build = build
                    self.features = features or {}

            builds_with_features = []
            for build in builds:
                fv = None
                if build.feature_vector_id:
                    fv = feature_vectors_map.get(str(build.feature_vector_id))
                features = fv.features if fv else {}
                builds_with_features.append(BuildWithFeatures(build, features))

            enriched_builds = [
                b for b in builds_with_features if b.features and len(b.features) > 0
            ]

            report.feature_metrics = self._calculate_feature_metrics(
                builds=enriched_builds,
                selected_features=selected_features,
                feature_metadata=feature_metadata,
            )

            self._calculate_feature_distributions(scenario_id, report.feature_metrics)

            report.completeness_score = self._calculate_completeness_score(
                report.feature_metrics
            )
            report.validity_score = self._calculate_validity_score(
                report.feature_metrics
            )
            report.consistency_score = self._calculate_consistency_score(
                builds=enriched_builds,
                selected_features=selected_features,
            )

            # Update in DB
            self.quality_repo.update_one(
                str(report.id),
                {
                    "completeness_score": report.completeness_score,
                    "validity_score": report.validity_score,
                    "consistency_score": report.consistency_score,
                    "coverage_score": report.coverage_score,
                    "feature_metrics": [m.dict() for m in report.feature_metrics],
                },
            )

        except Exception as e:
            logger.error(f"Full feature evaluation failed: {e}")

        return report
