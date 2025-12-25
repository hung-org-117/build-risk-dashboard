import type {
    Build,
    BuildDetail,
    BuildListResponse,
} from "@/types";
import { api } from "./client";

export const buildApi = {
    getByRepo: async (
        repoId: string,
        params?: {
            skip?: number;
            limit?: number;
            q?: string;
        }
    ) => {
        const response = await api.get<BuildListResponse>(`/repos/${repoId}/builds`, {
            params,
        });
        return response.data;
    },

    getById: async (repoId: string, buildId: string) => {
        const response = await api.get<BuildDetail>(
            `/repos/${repoId}/builds/${buildId}`
        );
        return response.data;
    },

    reprocess: async (repoId: string, buildId: string) => {
        const response = await api.post<{ status: string; build_id: string; message: string }>(
            `/repos/${repoId}/builds/${buildId}/reprocess`
        );
        return response.data;
    },
};
