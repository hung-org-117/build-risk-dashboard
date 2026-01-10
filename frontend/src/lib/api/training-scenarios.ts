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

    // Split counts
    train_count: number;
    val_count: number;
    test_count: number;

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
    run_started_at?: string;
    duration_seconds?: number;
}

export interface PreviewBuildStats {
    total_builds: number;
    total_repos: number;
    outcome_distribution: {
        success: number;
        failure: number;
        other: number;
    };
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

// Create scenario payload
export interface CreateTrainingScenarioPayload {
    name: string;
    description?: string;
    yaml_config?: string;  // Optional - use if importing from YAML
    data_source_config?: {
        filter_by?: string;
        languages?: string[];
        repo_names?: string[];
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
        exclude?: string[];
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
     * List training scenarios
     */
    list: async (params?: {
        skip?: number;
        limit?: number;
        status?: string;
        q?: string;
    }): Promise<TrainingScenarioRecord[]> => {
        const response = await api.get<TrainingScenarioRecord[]>("/training-scenarios", { params });
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
};
