import { api } from "./client";

// Types
export interface ExportPreviewResponse {
    total_rows: number;
    use_async_recommended: boolean;
    async_threshold: number;
    sample_rows: Record<string, unknown>[];
    available_features: string[];
    feature_count: number;
}

export interface ExportJobResponse {
    job_id: string;
    status: "pending" | "processing" | "completed" | "failed";
    format: "csv" | "json";
    total_rows: number;
    processed_rows: number;
    progress_percent: number;
    file_size?: number;
    file_size_mb?: number;
    error_message?: string;
    created_at: string;
    completed_at?: string;
    download_url?: string;
}

export interface ExportAsyncResponse {
    job_id: string;
    status: string;
    estimated_rows: number;
    format: string;
    poll_url: string;
    message: string;
}

export interface ExportJobListItem {
    job_id: string;
    status: string;
    format: string;
    total_rows: number;
    file_size: number | null;
    created_at: string;
    completed_at: string | null;
    download_url: string | null;
}

export const exportApi = {
    preview: async (
        repoId: string,
        params?: {
            features?: string;
            start_date?: string;
            end_date?: string;
            build_status?: string;
        }
    ): Promise<ExportPreviewResponse> => {
        const response = await api.get<ExportPreviewResponse>(
            `/repos/${repoId}/export/preview`,
            { params }
        );
        return response.data;
    },

    getStreamUrl: (
        repoId: string,
        format: "csv" | "json" = "csv",
        params?: {
            features?: string;
            start_date?: string;
            end_date?: string;
            build_status?: string;
        }
    ): string => {
        const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
        const searchParams = new URLSearchParams();
        searchParams.set("format", format);
        if (params?.features) searchParams.set("features", params.features);
        if (params?.start_date) searchParams.set("start_date", params.start_date);
        if (params?.end_date) searchParams.set("end_date", params.end_date);
        if (params?.build_status) searchParams.set("build_status", params.build_status);
        return `${baseUrl}/repos/${repoId}/export?${searchParams.toString()}`;
    },

    downloadStream: async (
        repoId: string,
        format: "csv" | "json" = "csv",
        params?: {
            features?: string;
            start_date?: string;
            end_date?: string;
            build_status?: string;
        }
    ): Promise<Blob> => {
        const response = await api.get(`/repos/${repoId}/export`, {
            params: { format, ...params },
            responseType: "blob",
        });
        return response.data;
    },

    createAsyncJob: async (
        repoId: string,
        format: "csv" | "json" = "csv",
        params?: {
            features?: string;
            start_date?: string;
            end_date?: string;
            build_status?: string;
        }
    ): Promise<ExportAsyncResponse> => {
        const response = await api.post<ExportAsyncResponse>(
            `/repos/${repoId}/export/async`,
            null,
            { params: { format, ...params } }
        );
        return response.data;
    },

    getJobStatus: async (jobId: string): Promise<ExportJobResponse> => {
        const response = await api.get<ExportJobResponse>(`/repos/export/jobs/${jobId}`);
        return response.data;
    },

    downloadJob: async (jobId: string): Promise<Blob> => {
        const response = await api.get(`/repos/export/jobs/${jobId}/download`, {
            responseType: "blob",
        });
        return response.data;
    },

    listJobs: async (
        repoId: string,
        limit: number = 10
    ): Promise<{ items: ExportJobListItem[]; count: number }> => {
        const response = await api.get<{ items: ExportJobListItem[]; count: number }>(
            `/repos/${repoId}/export/jobs`,
            { params: { limit } }
        );
        return response.data;
    },
};
