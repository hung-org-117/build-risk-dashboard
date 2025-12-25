import type {
    FeatureDAGResponse,
    FeatureListResponse,
} from "@/types";
import { api } from "./client";

export const featuresApi = {
    list: async (params?: {
        category?: string;
        source?: string;
        extractor_node?: string;
        is_active?: boolean;
    }) => {
        const response = await api.get<FeatureListResponse>("/features", { params });
        return response.data;
    },
    getDAG: async (selectedFeatures?: string[]) => {
        const params = selectedFeatures?.length
            ? { selected_features: selectedFeatures.join(",") }
            : undefined;
        const response = await api.get<FeatureDAGResponse>("/features/dag", { params });
        return response.data;
    },
    getConfig: async () => {
        const response = await api.get<{
            languages: string[];
            frameworks: string[];
            frameworks_by_language: Record<string, string[]>;
            ci_providers: Array<{ value: string; label: string }>;
        }>("/features/config");
        return response.data;
    },
    getConfigRequirements: async (selectedFeatures: string[]) => {
        const response = await api.post<{
            fields: Array<{
                name: string;
                type: string;
                scope: string;
                required: boolean;
                description: string;
                default: unknown;
                options: string[] | null;
            }>;
        }>("/features/config-requirements", { selected_features: selectedFeatures });
        return response.data;
    },
};

// Deprecated stubs - scanning now done via pipeline
export const sonarApi = {
    listFailedScans: async (_repoId: string): Promise<{ items: [] }> => ({ items: [] }),
    updateFailedScanConfig: async (_scanId: string, _config: string): Promise<void> => { },
    listResults: async (_repoId: string): Promise<{ items: [] }> => ({ items: [] }),
    getConfig: async (_repoId: string): Promise<{ content: string }> => ({ content: '' }),
    updateConfig: async (_repoId: string, _content: string): Promise<void> => { },
};
