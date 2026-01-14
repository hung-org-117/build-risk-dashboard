/**
 * Training Scenarios API client - Frontend API for Training Dataset Scenario Builder
 * 
 * Replaces ml-scenarios.ts with cleaner API for new Training Scenario flow.
 */

import { api } from "./client";

// =============================================================================
// Types
// =============================================================================

export type TrainingScenarioStatus =
    | "queued"
    | "filtering"
    | "ingesting"
    | "ingested"
    | "processing"
    | "processed"
    | "splitting"
    | "completed"
    | "failed";

export interface TrainingScenarioRecord {
    id: string;
    name: string;
    description?: string;
    version: string;
    status: TrainingScenarioStatus;
    error_message?: string;

    // Statistics
    builds_total: number;
    builds_ingested: number;
    builds_features_extracted: number;
    builds_missing_resource: number;
    builds_failed: number;

    // Scan tracking
    scans_total: number;
    scans_completed: number;
    scans_failed: number;
    feature_extraction_completed: boolean;
    scan_extraction_completed: boolean;



    // Config summaries (from nested configs)
    splitting_strategy?: string;
    group_by?: string;

    // Timestamps
    created_at?: string;
    updated_at?: string;
    filtering_completed_at?: string;
    ingestion_completed_at?: string;
    processing_completed_at?: string;
    splitting_completed_at?: string;
}

export interface TrainingScenarioListResponse {
    items: TrainingScenarioRecord[];
    total: number;
    skip: number;
    limit: number;
}

// Preview builds types for wizard Step 1
export interface PreviewBuild {
    id: string;
    raw_repo_id: string;
    repo_name: string;
    branch: string;
    commit_sha: string;
    conclusion: string;
    language?: string;
    run_started_at?: string;
    duration_seconds?: number;
    ci_provider?: string;
}

export interface PreviewBuildStats {
    total_builds: number;
    total_repos: number;
    outcome_distribution: {
        success: number;
        failure: number;
    };
    repos?: { id: string; full_name: string }[];
}

export interface PreviewBuildsResponse {
    builds: PreviewBuild[];
    stats: PreviewBuildStats;
    pagination: {
        skip: number;
        limit: number;
        total: number;
    };
}

export interface PreviewBuildsParams {
    date_start?: string;
    date_end?: string;
    languages?: string;
    conclusions?: string;
    ci_provider?: string;
    exclude_bots?: boolean;
    skip?: number;
    limit?: number;
}

// Splitting Groups types (for Dynamic Group Discovery)
export interface SplittingGroup {
    value: string;
    label: string;
    count: number;
    warning?: "small_sample";
}

export interface SplittingGroupsResponse {
    group_by: string;
    groups: SplittingGroup[];
    total_builds: number;
    num_bins?: number;
    time_slots?: number;
    error?: string;
    valid_options?: string[];
}

export interface SplittingGroupsParams {
    group_by: string;
    num_bins?: number;
    time_slots?: number;
    date_start?: string;
    date_end?: string;
    languages?: string;
    conclusions?: string;
    ci_provider?: string;
}

export interface GroupPreviewParams {
    group_by: string;
    num_bins?: number;
    time_slots?: number;
}

// Dataset split types
export interface TrainingDatasetSplitRecord {
    id: string;
    scenario_id: string;
    split_type: string;
    record_count: number;
    feature_count: number;
    class_distribution: Record<string, number>;
    group_distribution: Record<string, number>;
    file_path: string;
    file_size_bytes: number;
    file_format: string;
    generated_at?: string;
    generation_duration_seconds: number;
}

// Ingestion build types
export interface TrainingIngestionBuildRecord {
    id: string;
    ci_run_id: string;
    commit_sha: string;
    repo_full_name: string;
    status: "pending" | "ingesting" | "ingested" | "missing_resource" | "failed";
    resource_status: Record<string, { status: string; error?: string }>;
    required_resources: string[];
    ingestion_error?: string;
    created_at?: string;
    ingested_at?: string;
}

// Enrichment build types
export interface TrainingEnrichmentBuildRecord {
    id: string;
    raw_build_run_id: string;
    ci_run_id: string;
    commit_sha: string;
    repo_full_name: string;
    extraction_status: "pending" | "completed" | "failed" | "partial";
    extraction_error?: string;
    feature_count: number;
    expected_feature_count: number;
    split_assignment?: string;
    created_at?: string;
    enriched_at?: string;
}

export interface NodeExecutionDetail {
    node_name: string;
    status: string;
    duration_ms: number;
    features_extracted: string[];
    resources_used: string[];
    error?: string;
    warning?: string;
    skip_reason?: string;
    retry_count: number;
}

export interface FeatureAuditLogDetail {
    id: string;
    duration_ms: number;
    nodes_succeeded: number;
    nodes_failed: number;
    nodes_skipped: number;
    errors: string[];
    warnings: string[];
    node_results: NodeExecutionDetail[];
}

export interface TrainingEnrichmentBuildDetail {
    enrichment_build: TrainingEnrichmentBuildRecord & {
        features: Record<string, any>;
        missing_resources: string[];
        skipped_features: string[];
        expected_feature_count: number;
    };
    raw_build_run: {
        id: string;
        repo_name: string;
        branch: string;
        commit_sha: string;
        ci_run_id: string;
        provider: string;
        web_url?: string;
        conclusion: string;
        run_started_at?: string;
    };
    audit_log?: FeatureAuditLogDetail;
}

// Paginated response
export interface PaginatedResponse<T> {
    items: T[];
    total: number;
    page: number;
    size: number;
}

// Scan status types
export interface ScanStatusResponse {
    scans_total: number;
    scans_completed: number;
    scans_failed: number;
    scans_pending: number;
}

export interface CommitScanRecord {
    id: string;
    scenario_id: string;
    commit_sha: string;
    repo_full_name: string;
    raw_repo_id: string;
    tool_type: "trivy" | "sonarqube";
    status: "pending" | "scanning" | "completed" | "failed";
    error_message?: string;
    metrics?: Record<string, any>;
    scan_config?: Record<string, any>;
    builds_affected: number;
    retry_count: number;
    selected_metrics?: string[]; // Optional: list of metric keys to display in summary
    started_at?: string;
    completed_at?: string;
    builds?: {
        id: string;
        ci_run_id: string;
        ingestion_status: string;
        build_number?: string | number;
        web_url?: string;
    }[];
    created_at?: string;
}

export interface CommitScanListResponse {
    trivy?: PaginatedResponse<CommitScanRecord>;
    sonarqube?: PaginatedResponse<CommitScanRecord>;
}

// Create scenario payload
export interface CreateTrainingScenarioPayload {
    name: string;
    description?: string;
    yaml_config?: string;  // Optional - use if importing from YAML
    data_source_config?: {
        languages?: string[];
        build_source_ids?: string[];
        date_start?: string;
        date_end?: string;
        conclusions?: string[];
        ci_provider?: string;
    };
    feature_config?: {
        dag_features?: string[];
        scan_metrics?: {
            sonarqube?: string[];
            trivy?: string[];
        };
        // Tool configurations (editable via UI)
        scan_tool_config?: Record<string, Record<string, unknown>>;
        extractor_configs?: Record<string, unknown>;
    };
    splitting_config?: {
        strategy?: string;
        group_by?: string;
        groups?: string[];
        ratios?: Record<string, number>;
        stratify_by?: string;
    };
    preprocessing_config?: {
        missing_values_strategy?: string;
        normalization_method?: string;
    };
    output_config?: {
        format?: string;
        include_metadata?: boolean;
    };
}

// =============================================================================
// API Client
// =============================================================================

export const trainingScenariosApi = {
    /**
     * Preview builds matching filter criteria (Wizard Step 1)
     */
    previewBuilds: async (params: PreviewBuildsParams = {}): Promise<PreviewBuildsResponse> => {
        const response = await api.get<PreviewBuildsResponse>("/training-scenarios/preview-builds", {
            params,
        });
        return response.data;
    },

    /**
     * Get dynamic filter options (providers, languages)
     */
    getFilterOptions: async (): Promise<{ providers: { value: string; label: string }[]; languages: { value: string; label: string }[] }> => {
        const response = await api.get<{ providers: { value: string; label: string }[]; languages: { value: string; label: string }[] }>(
            "/training-scenarios/filter-options"
        );
        return response.data;
    },

    /**
     * Get available groups for splitting strategies (Wizard Step 3 - LOO/LTO)
     */
    getSplittingGroups: async (params: SplittingGroupsParams): Promise<SplittingGroupsResponse> => {
        const response = await api.get<SplittingGroupsResponse>("/training-scenarios/splitting-groups", {
            params,
        });
        return response.data;
    },

    /**
     * Get group preview for a scenario's master dataset
     * Used in export page to dynamically configure grouping
     */
    getGroupPreview: async (
        scenarioId: string,
        params: GroupPreviewParams
    ): Promise<SplittingGroupsResponse> => {
        const response = await api.get<SplittingGroupsResponse>(
            `/training-scenarios/${scenarioId}/group-preview`,
            { params }
        );
        return response.data;
    },

    /**
     * List training scenarios
     */
    list: async (params?: {
        skip?: number;
        limit?: number;
        status?: string;
        q?: string;
    }): Promise<TrainingScenarioListResponse> => {
        const response = await api.get<TrainingScenarioListResponse>("/training-scenarios", { params });
        return response.data;
    },

    /**
     * Get scenario by ID
     */
    get: async (scenarioId: string): Promise<TrainingScenarioRecord> => {
        const response = await api.get<TrainingScenarioRecord>(`/training-scenarios/${scenarioId}`);
        return response.data;
    },

    /**
     * Create a new training scenario
     */
    create: async (payload: CreateTrainingScenarioPayload): Promise<TrainingScenarioRecord> => {
        const response = await api.post<TrainingScenarioRecord>("/training-scenarios", payload);
        return response.data;
    },

    /**
     * Delete a training scenario
     */
    delete: async (scenarioId: string): Promise<void> => {
        await api.delete(`/training-scenarios/${scenarioId}`);
    },

    /**
     * Start ingestion phase
     */
    startIngestion: async (scenarioId: string): Promise<{ status: string; message: string }> => {
        const response = await api.post<{ status: string; message: string }>(
            `/training-scenarios/${scenarioId}/ingest`
        );
        return response.data;
    },

    /**
     * Start processing phase
     */
    startProcessing: async (scenarioId: string): Promise<{ status: string; message: string }> => {
        const response = await api.post<{ status: string; message: string }>(
            `/training-scenarios/${scenarioId}/process`
        );
        return response.data;
    },

    /**
     * Generate dataset (split & export)
     */
    generateDataset: async (scenarioId: string): Promise<{ status: string; message: string }> => {
        const response = await api.post<{ status: string; message: string }>(
            `/training-scenarios/${scenarioId}/generate`
        );
        return response.data;
    },

    /**
     * Get generated splits
     */
    getSplits: async (scenarioId: string): Promise<TrainingDatasetSplitRecord[]> => {
        const response = await api.get<TrainingDatasetSplitRecord[]>(
            `/training-scenarios/${scenarioId}/splits`
        );
        return response.data;
    },

    // =========================================================================
    // Build Listing
    // =========================================================================

    /**
     * Get ingestion builds for a scenario (Phase 1)
     */
    getIngestionBuilds: async (
        scenarioId: string,
        params?: { skip?: number; limit?: number; status?: string }
    ): Promise<PaginatedResponse<TrainingIngestionBuildRecord>> => {
        const response = await api.get<PaginatedResponse<TrainingIngestionBuildRecord>>(
            `/training-scenarios/${scenarioId}/ingestion-builds`,
            { params }
        );
        return response.data;
    },

    /**
     * Get enrichment builds for a scenario (Phase 2)
     */
    getEnrichmentBuilds: async (
        scenarioId: string,
        params?: { skip?: number; limit?: number; extraction_status?: string }
    ): Promise<PaginatedResponse<TrainingEnrichmentBuildRecord>> => {
        const response = await api.get<PaginatedResponse<TrainingEnrichmentBuildRecord>>(
            `/training-scenarios/${scenarioId}/enrichment-builds`,
            { params }
        );
        return response.data;
    },

    /**
     * Get enrichment build detail
     */
    getEnrichmentBuildDetail: async (
        scenarioId: string,
        buildId: string
    ): Promise<TrainingEnrichmentBuildDetail> => {
        const response = await api.get<TrainingEnrichmentBuildDetail>(
            `/training-scenarios/${scenarioId}/enrichment-builds/${buildId}`
        );
        return response.data;
    },

    /**
     * Get scan status summary for a scenario
     */
    getScanStatus: async (scenarioId: string): Promise<ScanStatusResponse> => {
        const response = await api.get<ScanStatusResponse>(
            `/training-scenarios/${scenarioId}/scan-status`
        );
        return response.data;
    },

    /**
     * Get commit scans for a scenario (filtered by tool type)
     */
    getCommitScans: async (
        scenarioId: string,
        params?: { skip?: number; limit?: number; tool_type?: "trivy" | "sonarqube" }
    ): Promise<CommitScanListResponse> => {
        const response = await api.get<CommitScanListResponse>(
            `/training-scenarios/${scenarioId}/commit-scans`,
            { params }
        );
        return response.data;
    },

    /**
     * Get commit scan detail
     */
    getCommitScanDetail: async (
        scenarioId: string,
        toolType: "trivy" | "sonarqube",
        scanId: string
    ): Promise<CommitScanRecord> => {
        const response = await api.get<CommitScanRecord>(
            `/training-scenarios/${scenarioId}/commit-scans/${toolType}/${scanId}`
        );
        return response.data;
    },

    /**
     * Retry a specific commit scan
     */
    retryCommitScan: async (
        scenarioId: string,
        commitSha: string,
        toolType: "trivy" | "sonarqube"
    ): Promise<{ status: string }> => {
        const response = await api.post<{ status: string }>(
            `/training-scenarios/${scenarioId}/commit-scans/${commitSha}/retry`,
            null,
            { params: { tool_type: toolType } }
        );
        return response.data;
    },

    // =========================================================================
    // Retry Actions
    // =========================================================================

    /**
     * Retry failed ingestion builds
     */
    retryIngestion: async (scenarioId: string): Promise<{ message: string; retry_count: number }> => {
        const response = await api.post<{ message: string; retry_count: number }>(
            `/training-scenarios/${scenarioId}/retry-ingestion`
        );
        return response.data;
    },

    /**
     * Retry failed processing builds
     */
    retryProcessing: async (scenarioId: string): Promise<{ message: string; retry_count: number }> => {
        const response = await api.post<{ message: string; retry_count: number }>(
            `/training-scenarios/${scenarioId}/retry-processing`
        );
        return response.data;
    },

    /**
     * Retry failed scans for a specific tool type.
     * Dispatches directly to the tool-specific scan task.
     */
    retryFailedScans: async (
        scenarioId: string,
        toolType: "trivy" | "sonarqube"
    ): Promise<{ success: boolean; message: string }> => {
        const response = await api.post<{ success: boolean; message: string }>(
            `/training-scenarios/${scenarioId}/retry-scans`,
            null,
            { params: { tool_type: toolType } }
        );
        return response.data;
    },
};
