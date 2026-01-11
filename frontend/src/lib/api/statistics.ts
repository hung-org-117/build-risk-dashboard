import { api } from "./client";

// Types
export interface VersionStatistics {
    total_builds: number;
    enriched_builds: number;
    failed_builds: number;
    partial_builds: number;
    enrichment_rate: number;
    success_rate: number;
    total_features_selected: number;
    avg_features_per_build: number;
    total_feature_values_extracted: number;
    quality_score?: number;
    completeness_score?: number;
    validity_score?: number;
    consistency_score?: number;
    coverage_score?: number;
    processing_duration_seconds?: number;
}

export interface BuildStatusBreakdown {
    status: string;
    count: number;
    percentage: number;
}

export interface FeatureCompleteness {
    feature_name: string;
    non_null_count: number;
    null_count: number;
    completeness_pct: number;
    data_type: string;
}

export interface VersionStatisticsResponse {
    scenario_id: string;
    scenario_name: string;
    status: string;
    statistics: VersionStatistics;
    build_status_breakdown: BuildStatusBreakdown[];
    feature_completeness: FeatureCompleteness[];
    started_at?: string;
    completed_at?: string;
    evaluated_at?: string;
}

export interface HistogramBin {
    min_value: number;
    max_value: number;
    count: number;
    percentage: number;
}

export interface NumericStats {
    min: number;
    max: number;
    mean: number;
    median: number;
    std: number;
    q1: number;
    q3: number;
    iqr: number;
}

export interface NumericDistribution {
    feature_name: string;
    data_type: string;
    total_count: number;
    null_count: number;
    bins: HistogramBin[];
    stats?: NumericStats;
}

export interface CategoricalValue {
    value: string;
    count: number;
    percentage: number;
}

export interface CategoricalDistribution {
    feature_name: string;
    data_type: string;
    total_count: number;
    null_count: number;
    unique_count: number;
    values: CategoricalValue[];
    truncated: boolean;
}

export interface FeatureDistributionResponse {
    scenario_id: string;
    distributions: Record<string, NumericDistribution | CategoricalDistribution>;
}

export interface CorrelationPair {
    feature_1: string;
    feature_2: string;
    correlation: number;
    strength: string;
}

export interface CorrelationMatrixResponse {
    scenario_id: string;
    features: string[];
    matrix: (number | null)[][];
    significant_pairs: CorrelationPair[];
}

// Scan Metrics Types
export interface MetricSummary {
    sum: number;
    avg: number;
    max: number;
    min: number;
    count: number;
}

export interface TrivySummary {
    vuln_total: MetricSummary;
    vuln_critical: MetricSummary;
    vuln_high: MetricSummary;
    vuln_medium: MetricSummary;
    vuln_low: MetricSummary;
    misconfig_total: MetricSummary;
    misconfig_critical: MetricSummary;
    misconfig_high: MetricSummary;
    misconfig_medium: MetricSummary;
    misconfig_low: MetricSummary;
    secrets_count: MetricSummary;
    scan_duration_ms: MetricSummary;
    has_critical_count: number;
    has_high_count: number;
    total_scans: number;
}

export interface SonarSummary {
    bugs: MetricSummary;
    code_smells: MetricSummary;
    vulnerabilities: MetricSummary;
    security_hotspots: MetricSummary;
    complexity: MetricSummary;
    cognitive_complexity: MetricSummary;
    duplicated_lines_density: MetricSummary;
    ncloc: MetricSummary;
    reliability_rating_avg: number | null;
    security_rating_avg: number | null;
    maintainability_rating_avg: number | null;
    alert_status_ok_count: number;
    alert_status_error_count: number;
    total_scans: number;
}

export interface ScanSummary {
    total_builds: number;
    builds_with_trivy: number;
    builds_with_sonar: number;
    builds_with_any_scan: number;
    trivy_coverage_pct: number;
    sonar_coverage_pct: number;
}

export interface ScanMetricsStatisticsResponse {
    scenario_id: string;
    scan_summary: ScanSummary;
    trivy_summary: TrivySummary;
    sonar_summary: SonarSummary;
}

export const statisticsApi = {
    getVersionStatistics: async (
        scenarioId: string
    ): Promise<VersionStatisticsResponse> => {
        const response = await api.get<VersionStatisticsResponse>(
            `/scenarios/${scenarioId}/statistics`
        );
        return response.data;
    },

    getDistributions: async (
        scenarioId: string,
        options?: {
            features?: string[];
            bins?: number;
            top_n?: number;
        }
    ): Promise<FeatureDistributionResponse> => {
        const response = await api.get<FeatureDistributionResponse>(
            `/scenarios/${scenarioId}/statistics/distributions`,
            {
                params: {
                    features: options?.features?.join(","),
                    bins: options?.bins,
                    top_n: options?.top_n,
                },
            }
        );
        return response.data;
    },

    getCorrelation: async (
        scenarioId: string,
        features?: string[]
    ): Promise<CorrelationMatrixResponse> => {
        const response = await api.get<CorrelationMatrixResponse>(
            `/scenarios/${scenarioId}/statistics/correlation`,
            {
                params: features ? { features: features.join(",") } : undefined,
            }
        );
        return response.data;
    },

    getScanMetrics: async (
        scenarioId: string
    ): Promise<ScanMetricsStatisticsResponse> => {
        const response = await api.get<ScanMetricsStatisticsResponse>(
            `/scenarios/${scenarioId}/statistics/scans`
        );
        return response.data;
    },
};
