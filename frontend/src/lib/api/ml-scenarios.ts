/**
 * ML Scenarios API client - Frontend API for ML Dataset Scenario Builder
 */

import { api } from "./client";

// =============================================================================
// Types
// =============================================================================

export interface MLScenarioRecord {
    id: string;
    name: string;
    description?: string;
    version: string;
    status: MLScenarioStatus;
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
    // Config summaries
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

export type MLScenarioStatus =
    | "queued"
    | "filtering"
    | "ingesting"
    | "processing"
    | "splitting"
    | "completed"
    | "failed";

export interface MLScenarioListResponse {
    items: MLScenarioRecord[];
    total: number;
    skip: number;
    limit: number;
}

export interface MLDatasetSplitRecord {
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

export interface CreateScenarioPayload {
    name: string;
    yaml_config: string;
    description?: string;
}

export interface UpdateScenarioPayload {
    name?: string;
    description?: string;
    yaml_config?: string;
}

// Import Build (Ingestion Phase)
export interface MLScenarioImportBuildRecord {
    id: string;
    scenario_id: string;
    raw_repo_id: string;
    raw_build_run_id: string;
    ci_run_id: string;
    commit_sha: string;
    repo_full_name: string;
    github_repo_id?: number;
    status: "pending" | "queued" | "ingesting" | "ingested" | "failed";
    ingestion_error?: string;
    resource_status?: Record<string, { status: string; error?: string }>;
    created_at?: string;
    ingested_at?: string;
}

// Enrichment Build (Processing Phase)
export interface MLScenarioEnrichmentBuildRecord {
    id: string;
    scenario_id: string;
    scenario_import_build_id?: string;
    raw_repo_id: string;
    raw_build_run_id?: string;
    ci_run_id: string;
    commit_sha: string;
    repo_full_name: string;
    outcome: number;
    extraction_status: "pending" | "in_progress" | "completed" | "partial" | "failed";
    extraction_error?: string;
    feature_vector_id?: string;
    split_assignment?: string;
    created_at?: string;
    processing_completed_at?: string;
}

export interface MLScenarioBuildsListResponse<T> {
    items: T[];
    total: number;
    skip: number;
    limit: number;
}

export interface MLScenarioBuildStats {
    import_builds: Record<string, number>;
    enrichment_builds: Record<string, number>;
    split_assignment: Record<string, number>;
}

// =============================================================================
// API Methods
// =============================================================================

export const mlScenariosApi = {
    /**
     * List ML scenarios with optional filters
     */
    list: async (params?: {
        skip?: number;
        limit?: number;
        status_filter?: MLScenarioStatus;
        q?: string;
    }) => {
        const response = await api.get<MLScenarioListResponse>("/ml-scenarios", { params });
        return response.data;
    },

    /**
     * Get scenario details by ID
     */
    get: async (scenarioId: string) => {
        const response = await api.get<MLScenarioRecord>(`/ml-scenarios/${scenarioId}`);
        return response.data;
    },

    /**
     * Create a new scenario from YAML config (form data)
     */
    create: async (payload: CreateScenarioPayload) => {
        const formData = new FormData();
        formData.append("name", payload.name);
        formData.append("yaml_config", payload.yaml_config);
        if (payload.description) {
            formData.append("description", payload.description);
        }

        const response = await api.post<MLScenarioRecord>("/ml-scenarios", formData, {
            headers: { "Content-Type": "multipart/form-data" },
        });
        return response.data;
    },

    /**
     * Upload a YAML file to create a scenario
     */
    upload: async (file: File, name: string, description?: string) => {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("name", name);
        if (description) {
            formData.append("description", description);
        }

        const response = await api.post<MLScenarioRecord>("/ml-scenarios/upload", formData, {
            headers: { "Content-Type": "multipart/form-data" },
        });
        return response.data;
    },

    /**
     * Update scenario fields
     */
    update: async (scenarioId: string, payload: UpdateScenarioPayload) => {
        const formData = new FormData();
        if (payload.name) formData.append("name", payload.name);
        if (payload.description !== undefined) formData.append("description", payload.description);
        if (payload.yaml_config) formData.append("yaml_config", payload.yaml_config);

        const response = await api.patch<MLScenarioRecord>(`/ml-scenarios/${scenarioId}`, formData, {
            headers: { "Content-Type": "multipart/form-data" },
        });
        return response.data;
    },

    /**
     * Delete a scenario
     */
    delete: async (scenarioId: string) => {
        await api.delete(`/ml-scenarios/${scenarioId}`);
    },

    /**
     * Get the raw YAML config for a scenario
     */
    getConfig: async (scenarioId: string) => {
        const response = await api.get<{
            scenario_id: string;
            yaml_config: string;
        }>(`/ml-scenarios/${scenarioId}/config`);
        return response.data;
    },

    /**
     * Start dataset generation for a scenario
     */
    startGeneration: async (scenarioId: string) => {
        const response = await api.post<{
            scenario_id: string;
            task_id: string;
            status: string;
            message: string;
        }>(`/ml-scenarios/${scenarioId}/generate`);
        return response.data;
    },

    /**
     * Get all generated splits for a scenario
     */
    getSplits: async (scenarioId: string) => {
        const response = await api.get<{
            scenario_id: string;
            splits: MLDatasetSplitRecord[];
        }>(`/ml-scenarios/${scenarioId}/splits`);
        return response.data;
    },

    /**
     * Get download URL for a split file
     */
    getDownloadUrl: (scenarioId: string, splitType: string) => {
        return `/api/ml-scenarios/${scenarioId}/splits/${splitType}/download`;
    },

    // =========================================================================
    // YAML Validation & Documentation
    // =========================================================================

    /**
     * Validate YAML configuration without creating a scenario
     */
    validateYaml: async (yamlConfig: string) => {
        const formData = new FormData();
        formData.append("yaml_config", yamlConfig);

        const response = await api.post<{
            valid: boolean;
            errors: Array<{
                field: string;
                message: string;
                expected?: string;
                got?: string;
            }>;
            warnings: string[];
        }>("/ml-scenarios/validate", formData, {
            headers: { "Content-Type": "multipart/form-data" },
        });
        return response.data;
    },

    /**
     * List available sample YAML templates
     */
    getSampleTemplates: async () => {
        const response = await api.get<{
            templates: Array<{
                filename: string;
                name: string;
                description: string;
                strategy: string;
                group_by: string;
            }>;
            count: number;
        }>("/ml-scenarios/sample-templates");
        return response.data;
    },

    /**
     * Get content of a specific sample template
     */
    getSampleTemplate: async (filename: string) => {
        const response = await api.get<{
            filename: string;
            content: string;
        }>(`/ml-scenarios/sample-templates/${filename}`);
        return response.data;
    },

    /**
     * Get YAML schema documentation
     */
    getYamlSchemaDocs: async () => {
        const response = await api.get<{
            sections: Array<{
                name: string;
                required: boolean;
                description: string;
                fields: Array<{
                    name: string;
                    type: string;
                    required: boolean | string;
                    default?: unknown;
                    values?: string[];
                    description: string;
                    example?: unknown;
                }>;
            }>;
            strategies: Record<
                string,
                {
                    description: string;
                    required_config: string[];
                }
            >;
        }>("/ml-scenarios/docs/yaml-schema");
        return response.data;
    },

    // =========================================================================
    // BUILDS API (Ingestion & Processing Phases)
    // =========================================================================

    /**
     * List import builds for a scenario (ingestion phase)
     */
    getImportBuilds: async (
        scenarioId: string,
        params?: {
            skip?: number;
            limit?: number;
            status_filter?: string;
            q?: string;
        }
    ) => {
        const response = await api.get<MLScenarioBuildsListResponse<MLScenarioImportBuildRecord>>(
            `/ml-scenarios/${scenarioId}/builds/import`,
            { params }
        );
        return response.data;
    },

    /**
     * List enrichment builds for a scenario (processing phase)
     */
    getEnrichmentBuilds: async (
        scenarioId: string,
        params?: {
            skip?: number;
            limit?: number;
            status_filter?: string;
            split_filter?: string;
            q?: string;
        }
    ) => {
        const response = await api.get<MLScenarioBuildsListResponse<MLScenarioEnrichmentBuildRecord>>(
            `/ml-scenarios/${scenarioId}/builds/enrichment`,
            { params }
        );
        return response.data;
    },

    /**
     * Get build stats for a scenario
     */
    getBuildStats: async (scenarioId: string) => {
        const response = await api.get<MLScenarioBuildStats>(
            `/ml-scenarios/${scenarioId}/builds/stats`
        );
        return response.data;
    },
};

export default mlScenariosApi;

