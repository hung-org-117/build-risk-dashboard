/**
 * Core API client with axios instance, interceptors, and error handling.
 */

import type {
    RefreshTokenResponse,
} from "@/types";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export const api = axios.create({
    baseURL: API_URL,
    headers: {
        "Content-Type": "application/json",
    },
    withCredentials: true,
});

// Token refresh flag to prevent multiple refresh attempts
let isRefreshing = false;
let failedQueue: Array<{
    resolve: (value?: unknown) => void;
    reject: (reason?: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
    failedQueue.forEach((prom) => {
        if (error) {
            prom.reject(error);
        } else {
            prom.resolve(token);
        }
    });
    failedQueue = [];
};

// Types for standardized API response format
interface ApiSuccessResponse<T = unknown> {
    success: true;
    data: T;
    meta?: {
        request_id?: string;
        duration_ms?: number;
    };
}

interface ApiErrorResponse {
    success: false;
    error: {
        code: string;
        message: string;
        details?: Array<{
            field: string;
            message: string;
            type: string;
        }>;
        request_id?: string;
    };
    timestamp: string;
}

// Custom error class for API errors
export class ApiError extends Error {
    code: string;
    details?: Array<{ field: string; message: string; type: string }>;
    requestId?: string;
    statusCode?: number;

    constructor(
        message: string,
        code: string,
        details?: Array<{ field: string; message: string; type: string }>,
        requestId?: string,
        statusCode?: number
    ) {
        super(message);
        this.name = "ApiError";
        this.code = code;
        this.details = details;
        this.requestId = requestId;
        this.statusCode = statusCode;
    }
}

// Response interceptor to unwrap standardized response format
api.interceptors.response.use(
    (response) => {
        // Check if response is in new wrapped format
        const data = response.data;
        if (data && typeof data === "object" && "success" in data) {
            if (data.success === true && "data" in data) {
                // Unwrap successful response
                response.data = data.data;
            }
        }
        return response;
    },
    async (error) => {
        const originalRequest = error.config;

        // Handle new standardized error format
        if (error.response?.data?.success === false && error.response?.data?.error) {
            const errorData = error.response.data as ApiErrorResponse;
            const apiError = new ApiError(
                errorData.error.message,
                errorData.error.code,
                errorData.error.details,
                errorData.error.request_id,
                error.response.status
            );
            error.apiError = apiError;
        }

        if (
            error.response?.status === 401 &&
            !originalRequest._retry &&
            !originalRequest.url?.includes("/auth/refresh")
        ) {
            const authError = error.response?.headers?.["x-auth-error"];

            if (
                authError === "github_token_expired" ||
                authError === "github_token_revoked" ||
                authError === "github_not_connected"
            ) {
                return Promise.reject(error);
            }

            if (isRefreshing) {
                return new Promise((resolve, reject) => {
                    failedQueue.push({ resolve, reject });
                })
                    .then(() => {
                        return api(originalRequest);
                    })
                    .catch((err) => {
                        return Promise.reject(err);
                    });
            }

            originalRequest._retry = true;
            isRefreshing = true;

            try {
                await api.post<RefreshTokenResponse>("/auth/refresh");
                processQueue(null);
                isRefreshing = false;
                return api(originalRequest);
            } catch (refreshError) {
                processQueue(refreshError, null);
                isRefreshing = false;
                if (typeof window !== "undefined" && window.location.pathname !== "/login") {
                    window.location.href = "/login";
                }
                return Promise.reject(refreshError);
            }
        }

        return Promise.reject(error);
    }
);

// Helper to extract error message from API error
export function getApiErrorMessage(error: unknown): string {
    const err = error as { apiError?: ApiError; response?: { data?: { error?: { message?: string }; detail?: string } }; message?: string };
    if (err.apiError instanceof ApiError) {
        return err.apiError.message;
    }
    if (err.response?.data?.error?.message) {
        return err.response.data.error.message;
    }
    if (err.response?.data?.detail) {
        return err.response.data.detail;
    }
    if (err.message) {
        return err.message;
    }
    return "An unexpected error occurred";
}

// Helper to get field-level validation errors
export function getValidationErrors(
    error: unknown
): Array<{ field: string; message: string }> | null {
    const err = error as { apiError?: ApiError; response?: { data?: { error?: { details?: Array<{ field: string; message: string }> } } } };
    if (err.apiError instanceof ApiError && err.apiError.details) {
        return err.apiError.details.map((d) => ({
            field: d.field,
            message: d.message,
        }));
    }
    if (err.response?.data?.error?.details) {
        return err.response.data.error.details.map((d) => ({
            field: d.field,
            message: d.message,
        }));
    }
    return null;
}
