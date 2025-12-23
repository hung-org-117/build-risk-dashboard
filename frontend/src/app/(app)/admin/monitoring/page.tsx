"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useWebSocket } from "@/contexts/websocket-context";
import {
    SystemStatsCard,
    PipelineTracingTable,
    FeatureAuditLogsTable,
    LogsViewer,
} from "@/components/monitoring";
import { Button } from "@/components/ui/button";
import { RefreshCw, Activity } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface SystemStats {
    celery: {
        workers: any[];
        worker_count: number;
        queues: Record<string, number>;
        status: string;
    };
    redis: {
        connected: boolean;
        version?: string;
        memory_used?: string;
        connected_clients?: number;
        error?: string;
    };
    mongodb: {
        connected: boolean;
        version?: string;
        connections?: { current: number; available: number };
        collections?: number;
        error?: string;
    };
    timestamp: string;
}

interface PipelineRunsResponse {
    runs: any[];
    next_cursor: string | null;
    has_more: boolean;
}

interface AuditLogsResponse {
    logs: any[];
    next_cursor: string | null;
    has_more: boolean;
}

interface LogEntry {
    timestamp: string;
    level: string;
    message: string;
    container?: string;
}

export default function MonitoringPage() {
    // System stats
    const [systemStats, setSystemStats] = useState<SystemStats | null>(null);
    const [isLoadingStats, setIsLoadingStats] = useState(true);

    // Pipeline runs (high-level)
    const [pipelineRuns, setPipelineRuns] = useState<PipelineRunsResponse>({
        runs: [],
        next_cursor: null,
        has_more: false,
    });
    const [isLoadingPipelineRuns, setIsLoadingPipelineRuns] = useState(true);
    const [isLoadingMorePipelineRuns, setIsLoadingMorePipelineRuns] = useState(false);

    // Feature audit logs (per-build)
    const [auditLogs, setAuditLogs] = useState<AuditLogsResponse>({
        logs: [],
        next_cursor: null,
        has_more: false,
    });
    const [isLoadingAuditLogs, setIsLoadingAuditLogs] = useState(true);
    const [isLoadingMoreAuditLogs, setIsLoadingMoreAuditLogs] = useState(false);

    // System logs
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [isLoadingLogs, setIsLoadingLogs] = useState(false);
    const [isPaused, setIsPaused] = useState(false);
    const [containerFilter, setContainerFilter] = useState("all");
    const [levelFilter, setLevelFilter] = useState("all");
    const [searchQuery, setSearchQuery] = useState("");

    // WebSocket
    const { subscribe, isConnected } = useWebSocket();

    // Fetch system stats
    const fetchSystemStats = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/monitoring/system`, {
                credentials: "include",
            });
            if (res.ok) {
                const data = await res.json();
                setSystemStats(data);
            }
        } catch (error) {
            console.error("Failed to fetch system stats:", error);
        } finally {
            setIsLoadingStats(false);
        }
    }, []);

    // Fetch pipeline runs (high-level)
    const fetchPipelineRuns = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/monitoring/pipeline-runs/cursor?limit=20`, {
                credentials: "include",
            });
            if (res.ok) {
                const data = await res.json();
                setPipelineRuns(data);
            }
        } catch (error) {
            console.error("Failed to fetch pipeline runs:", error);
        } finally {
            setIsLoadingPipelineRuns(false);
        }
    }, []);

    const loadMorePipelineRuns = useCallback(async () => {
        if (!pipelineRuns.has_more || !pipelineRuns.next_cursor || isLoadingMorePipelineRuns) return;

        setIsLoadingMorePipelineRuns(true);
        try {
            const res = await fetch(
                `${API_BASE}/monitoring/pipeline-runs/cursor?limit=20&cursor=${pipelineRuns.next_cursor}`,
                { credentials: "include" }
            );
            if (res.ok) {
                const data = await res.json();
                setPipelineRuns((prev) => ({
                    runs: [...prev.runs, ...data.runs],
                    next_cursor: data.next_cursor,
                    has_more: data.has_more,
                }));
            }
        } catch (error) {
            console.error("Failed to load more pipeline runs:", error);
        } finally {
            setIsLoadingMorePipelineRuns(false);
        }
    }, [pipelineRuns.has_more, pipelineRuns.next_cursor, isLoadingMorePipelineRuns]);

    // Fetch audit logs (per-build)
    const fetchAuditLogs = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/monitoring/audit-logs/cursor?limit=20`, {
                credentials: "include",
            });
            if (res.ok) {
                const data = await res.json();
                setAuditLogs(data);
            }
        } catch (error) {
            console.error("Failed to fetch audit logs:", error);
        } finally {
            setIsLoadingAuditLogs(false);
        }
    }, []);

    const loadMoreAuditLogs = useCallback(async () => {
        if (!auditLogs.has_more || !auditLogs.next_cursor || isLoadingMoreAuditLogs) return;

        setIsLoadingMoreAuditLogs(true);
        try {
            const res = await fetch(
                `${API_BASE}/monitoring/audit-logs/cursor?limit=20&cursor=${auditLogs.next_cursor}`,
                { credentials: "include" }
            );
            if (res.ok) {
                const data = await res.json();
                setAuditLogs((prev) => ({
                    logs: [...prev.logs, ...data.logs],
                    next_cursor: data.next_cursor,
                    has_more: data.has_more,
                }));
            }
        } catch (error) {
            console.error("Failed to load more audit logs:", error);
        } finally {
            setIsLoadingMoreAuditLogs(false);
        }
    }, [auditLogs.has_more, auditLogs.next_cursor, isLoadingMoreAuditLogs]);

    // Fetch system logs
    const fetchLogs = useCallback(async () => {
        setIsLoadingLogs(true);
        try {
            const params = new URLSearchParams();
            if (levelFilter !== "all") params.set("level", levelFilter.toUpperCase());
            if (containerFilter !== "all") params.set("source", containerFilter);
            params.set("limit", "100");

            const res = await fetch(`${API_BASE}/monitoring/logs?${params.toString()}`, {
                credentials: "include",
            });

            if (res.ok) {
                const data = await res.json();
                if (data.logs && Array.isArray(data.logs)) {
                    const parsedLogs: LogEntry[] = data.logs.map((log: any) => ({
                        timestamp: log.timestamp || new Date().toISOString(),
                        level: log.level || "INFO",
                        message: log.message || "",
                        container: log.source || "unknown",
                    }));
                    setLogs(parsedLogs);
                }
            }
        } catch (error) {
            console.error("Failed to fetch logs:", error);
            setLogs([
                {
                    timestamp: new Date().toISOString().replace("T", " ").split(".")[0],
                    level: "INFO",
                    message: "System logs will appear here when activity is logged.",
                    container: "system",
                },
            ]);
        } finally {
            setIsLoadingLogs(false);
        }
    }, [containerFilter, levelFilter]);

    // Initial fetch
    useEffect(() => {
        fetchSystemStats();
        fetchPipelineRuns();
        fetchAuditLogs();
        fetchLogs();
    }, [fetchSystemStats, fetchPipelineRuns, fetchAuditLogs, fetchLogs]);

    // Auto-refresh every 10 seconds
    useEffect(() => {
        if (isPaused) return;

        const interval = setInterval(() => {
            fetchSystemStats();
            fetchPipelineRuns();
            fetchAuditLogs();
        }, 10000);

        return () => clearInterval(interval);
    }, [isPaused, fetchSystemStats, fetchPipelineRuns, fetchAuditLogs]);

    // WebSocket subscriptions
    useEffect(() => {
        const unsubscribePipeline = subscribe("PIPELINE_RUN_UPDATE", () => {
            fetchPipelineRuns();
            fetchAuditLogs();
        });

        const unsubscribeRepo = subscribe("REPO_UPDATE", () => {
            fetchPipelineRuns();
            fetchAuditLogs();
        });

        const unsubscribeBuild = subscribe("BUILD_UPDATE", () => {
            fetchPipelineRuns();
            fetchAuditLogs();
        });

        return () => {
            unsubscribePipeline();
            unsubscribeRepo();
            unsubscribeBuild();
        };
    }, [subscribe, fetchPipelineRuns, fetchAuditLogs]);

    const handleRefreshAll = () => {
        setIsLoadingStats(true);
        setIsLoadingPipelineRuns(true);
        setIsLoadingAuditLogs(true);
        fetchSystemStats();
        fetchPipelineRuns();
        fetchAuditLogs();
        fetchLogs();
    };

    return (
        <div className="container mx-auto py-6 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Activity className="h-8 w-8" />
                    <div>
                        <h1 className="text-2xl font-bold">System Monitoring</h1>
                        <p className="text-muted-foreground text-sm">
                            Real-time system stats, pipeline runs, and logs
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <span
                        className={`h-2 w-2 rounded-full ${isConnected ? "bg-green-500" : "bg-red-500"}`}
                        title={isConnected ? "WebSocket connected" : "WebSocket disconnected"}
                    />
                    <Button variant="outline" onClick={handleRefreshAll}>
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Refresh All
                    </Button>
                </div>
            </div>

            {/* System Stats */}
            <SystemStatsCard stats={systemStats} isLoading={isLoadingStats} />

            {/* Pipeline Runs (High-level) */}
            <PipelineTracingTable
                runs={pipelineRuns.runs}
                hasMore={pipelineRuns.has_more}
                isLoading={isLoadingPipelineRuns}
                isLoadingMore={isLoadingMorePipelineRuns}
                onLoadMore={loadMorePipelineRuns}
            />

            {/* Feature Audit Logs (Per-build) */}
            <FeatureAuditLogsTable
                logs={auditLogs.logs}
                hasMore={auditLogs.has_more}
                isLoading={isLoadingAuditLogs}
                isLoadingMore={isLoadingMoreAuditLogs}
                onLoadMore={loadMoreAuditLogs}
            />

            {/* System Logs */}
            <LogsViewer
                logs={logs}
                isLoading={isLoadingLogs}
                onRefresh={fetchLogs}
                isPaused={isPaused}
                onTogglePause={() => setIsPaused(!isPaused)}
                containerFilter={containerFilter}
                onContainerFilterChange={setContainerFilter}
                levelFilter={levelFilter}
                onLevelFilterChange={setLevelFilter}
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
            />
        </div>
    );
}
