import type {
    Build,
    DashboardSummaryResponse,
    WidgetDefinition,
} from "@/types";
import { api } from "./client";

// Types
interface DashboardLayoutResponse {
    widgets: Array<{
        widget_id: string;
        widget_type: string;
        title: string;
        enabled: boolean;
        x: number;
        y: number;
        w: number;
        h: number;
    }>;
}

interface DashboardLayoutUpdateRequest {
    widgets: Array<{
        widget_id: string;
        widget_type: string;
        title: string;
        enabled: boolean;
        x: number;
        y: number;
        w: number;
        h: number;
    }>;
}

export const dashboardApi = {
    getSummary: async () => {
        const response = await api.get<DashboardSummaryResponse>(
            "/dashboard/summary"
        );
        return response.data;
    },
    getRecentBuilds: async (limit: number = 10) => {
        const response = await api.get<Build[]>("/dashboard/recent-builds", {
            params: { limit },
        });
        return response.data;
    },
    getLayout: async (): Promise<DashboardLayoutResponse> => {
        const response = await api.get<DashboardLayoutResponse>("/dashboard/layout");
        return response.data;
    },
    saveLayout: async (layout: DashboardLayoutUpdateRequest): Promise<DashboardLayoutResponse> => {
        const response = await api.put<DashboardLayoutResponse>("/dashboard/layout", layout);
        return response.data;
    },
    getAvailableWidgets: async (): Promise<WidgetDefinition[]> => {
        const response = await api.get<WidgetDefinition[]>("/dashboard/available-widgets");
        return response.data;
    },
};
