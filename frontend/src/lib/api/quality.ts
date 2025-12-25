import { api } from "./client";

// Types
export interface QualityIssue {
    severity: "info" | "warning" | "error";
    category: string;
    feature_name?: string;
    message: string;
    details?: Record<string, unknown>;
}

export interface QualityMetric {
    feature_name: string;
    data_type: string;
    total_values: number;
    null_count: number;
    completeness_pct: number;
    validity_pct: number;
    min_value?: number;
    max_value?: number;
    mean_value?: number;
    std_dev?: number;
    expected_range?: [number, number];
    out_of_range_count: number;
    invalid_value_count: number;
    issues: string[];
}

export interface QualityReport {
    id: string;
    dataset_id: string;
    version_id: string;
    status: "pending" | "running" | "completed" | "failed";
    error_message?: string;
    quality_score: number;
    completeness_score: number;
    validity_score: number;
    consistency_score: number;
    coverage_score: number;
    total_builds: number;
    enriched_builds: number;
    partial_builds: number;
    failed_builds: number;
    total_features: number;
    features_with_issues: number;
    feature_metrics: QualityMetric[];
    issues: QualityIssue[];
    issue_counts: Record<string, number>;
    started_at?: string;
    completed_at?: string;
    created_at?: string;
}

export interface EvaluateQualityResponse {
    report_id: string;
    status: string;
    message: string;
    quality_score?: number;
}

export interface UserSettingsResponse {
    user_id: string;
    browser_notifications: boolean;
    created_at: string;
    updated_at: string;
}

export interface UpdateUserSettingsRequest {
    browser_notifications?: boolean;
}

export const qualityApi = {
    evaluate: async (
        datasetId: string,
        versionId: string
    ): Promise<EvaluateQualityResponse> => {
        const response = await api.post<EvaluateQualityResponse>(
            `/datasets/${datasetId}/versions/${versionId}/evaluate`
        );
        return response.data;
    },

    getReport: async (
        datasetId: string,
        versionId: string
    ): Promise<QualityReport | { available: false; message: string }> => {
        const response = await api.get<
            QualityReport | { available: false; message: string }
        >(`/datasets/${datasetId}/versions/${versionId}/quality-report`);
        return response.data;
    },
};

export const userSettingsApi = {
    get: async (): Promise<UserSettingsResponse> => {
        const response = await api.get<UserSettingsResponse>("/user-settings");
        return response.data;
    },

    update: async (request: UpdateUserSettingsRequest): Promise<UserSettingsResponse> => {
        const response = await api.patch<UserSettingsResponse>("/user-settings", request);
        return response.data;
    },
};
