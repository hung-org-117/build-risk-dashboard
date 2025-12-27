import { api } from "./client";

export type NormalizationMethod = "none" | "minmax" | "zscore" | "robust" | "log";

export interface NormalizationPreviewRequest {
    method: NormalizationMethod;
    features?: string[];
    sample_size?: number;
}

export interface FeatureStats {
    min: number;
    max: number;
    mean: number;
    std: number;
}

export interface FeaturePreview {
    data_type: string;
    original: {
        sample: number[];
        stats: FeatureStats;
    };
    transformed: {
        sample: number[];
        stats: FeatureStats;
    };
}

export interface NormalizationPreviewResponse {
    method: string;
    version_id: string;
    features: Record<string, FeaturePreview>;
    total_rows: number;
    message?: string;
}

export const preprocessingApi = {
    /**
     * Preview normalization transformation on selected features.
     */
    async previewNormalization(
        datasetId: string,
        versionId: string,
        request: NormalizationPreviewRequest
    ): Promise<NormalizationPreviewResponse> {
        const response = await api.post<NormalizationPreviewResponse>(
            `/datasets/${datasetId}/versions/${versionId}/preprocess/preview`,
            request
        );
        return response.data;
    },
};

export default preprocessingApi;
