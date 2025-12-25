import type {
    GithubToken,
    TokenCreatePayload,
    TokenListResponse,
    TokenPoolStatus,
    TokenUpdatePayload,
    TokenVerifyResponse,
} from "@/types";
import { api } from "./client";

export const tokensApi = {
    list: async (includeDisabled = false) => {
        const response = await api.get<TokenListResponse>("/tokens/", {
            params: { include_disabled: includeDisabled },
        });
        return response.data;
    },
    getStatus: async () => {
        const response = await api.get<TokenPoolStatus>("/tokens/status");
        return response.data;
    },
    create: async (payload: TokenCreatePayload) => {
        const response = await api.post<GithubToken>("/tokens/", payload);
        return response.data;
    },
    update: async (tokenId: string, payload: TokenUpdatePayload) => {
        const response = await api.patch<GithubToken>(`/tokens/${tokenId}`, payload);
        return response.data;
    },
    delete: async (tokenId: string) => {
        await api.delete(`/tokens/${tokenId}`);
    },
    verify: async (tokenId: string, rawToken: string) => {
        const response = await api.post<TokenVerifyResponse>(`/tokens/${tokenId}/verify`, {
            raw_token: rawToken,
        });
        return response.data;
    },
    refreshAll: async () => {
        const response = await api.post<{
            refreshed: number;
            failed: number;
            results: Array<{
                id: string;
                success: boolean;
                remaining?: number;
                limit?: number;
                error?: string;
            }>;
        }>("/tokens/refresh-all");
        return response.data;
    },
};
