"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useWebSocket } from "@/contexts/websocket-context";
import {
    SystemStatsCard,
    PipelineRunsTable,
    BackgroundJobsTable,
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
    total: number;
}

interface BackgroundJobsResponse {
    exports: any[];
    scans: any[];
    enrichments: any[];
    summary: {
        active_exports: number;
        active_scans: number;
        active_enrichments: number;
    };
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

    // Pipeline runs
    const [pipelineRuns, setPipelineRuns] = useState<PipelineRunsResponse>({
        runs: [],
        total: 0,
    });
    const [isLoadingRuns, setIsLoadingRuns] = useState(true);

    // Background jobs
    const [backgroundJobs, setBackgroundJobs] =
        useState<BackgroundJobsResponse | null>(null);
    const [isLoadingJobs, setIsLoadingJobs] = useState(true);

    // Logs
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [isLoadingLogs, setIsLoadingLogs] = useState(false);
    const [isPaused, setIsPaused] = useState(false);
    const [containerFilter, setContainerFilter] = useState("all");
    const [levelFilter, setLevelFilter] = useState("all");
    const [searchQuery, setSearchQuery] = useState("");

    // WebSocket for live updates
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

    // Fetch pipeline runs
    const fetchPipelineRuns = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/monitoring/pipeline-runs?limit=20`, {
                credentials: "include",
            });
            if (res.ok) {
                const data = await res.json();
                setPipelineRuns(data);
            }
        } catch (error) {
            console.error("Failed to fetch pipeline runs:", error);
        } finally {
            setIsLoadingRuns(false);
        }
    }, []);

    // Fetch background jobs
    const fetchBackgroundJobs = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/monitoring/jobs`, {
                credentials: "include",
            });
            if (res.ok) {
                const data = await res.json();
                setBackgroundJobs(data);
            }
        } catch (error) {
            console.error("Failed to fetch background jobs:", error);
        } finally {
            setIsLoadingJobs(false);
        }
    }, []);

    // Generate mock logs for demo (in production, this would come from Loki)
    const fetchLogs = useCallback(async () => {
        setIsLoadingLogs(true);
        try {
            // Build query params
            const params = new URLSearchParams();
            if (containerFilter !== "all") {
                params.set("query", `{container_name="${containerFilter}"}`);
            }
            if (levelFilter !== "all") {
                params.set("query", `{level="${levelFilter}"}`);
            }
            params.set("limit", "100");

            const res = await fetch(`${API_BASE}/logs?${params.toString()}`, {
                credentials: "include",
            });

            if (res.ok) {
                const data = await res.json();
                // Parse Loki response format
                if (data.data?.result) {
                    const parsedLogs: LogEntry[] = [];
                    for (const stream of data.data.result) {
                        const container = stream.stream?.container_name || "unknown";
                        for (const [ts, msg] of stream.values || []) {
                            // Parse timestamp (nanoseconds to readable)
                            const date = new Date(parseInt(ts) / 1000000);
                            const timestamp = date.toISOString().replace("T", " ").split(".")[0];

                            // Try to extract level from message
                            const levelMatch = msg.match(/\[(INFO|WARNING|ERROR|DEBUG)\]/);
                            const level = levelMatch ? levelMatch[1] : "INFO";

                            parsedLogs.push({
                                timestamp,
                                level,
                                message: msg,
                                container,
                            });
                        }
                    }
                    setLogs(parsedLogs);
                }
            }
        } catch (error) {
            console.error("Failed to fetch logs:", error);
            // Set demo logs if Loki is not available
            setLogs([
                {
                    timestamp: new Date().toISOString().replace("T", " ").split(".")[0],
                    level: "INFO",
                    message: "Loki is not configured. Enable monitoring stack in docker-compose.yml",
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
        fetchBackgroundJobs();
        fetchLogs();
    }, [fetchSystemStats, fetchPipelineRuns, fetchBackgroundJobs, fetchLogs]);

    // Auto-refresh every 10 seconds
    useEffect(() => {
        if (isPaused) return;

        const interval = setInterval(() => {
            fetchSystemStats();
            fetchPipelineRuns();
            fetchBackgroundJobs();
        }, 10000);

        return () => clearInterval(interval);
    }, [isPaused, fetchSystemStats, fetchPipelineRuns, fetchBackgroundJobs]);

    // Subscribe to WebSocket events
    useEffect(() => {
        const unsubscribePipeline = subscribe("PIPELINE_RUN_UPDATE", () => {
            fetchPipelineRuns();
        });

        const unsubscribeRepo = subscribe("REPO_UPDATE", () => {
            fetchPipelineRuns();
            fetchBackgroundJobs();
        });

        const unsubscribeBuild = subscribe("BUILD_UPDATE", () => {
            fetchPipelineRuns();
        });

        return () => {
            unsubscribePipeline();
            unsubscribeRepo();
            unsubscribeBuild();
        };
    }, [subscribe, fetchPipelineRuns, fetchBackgroundJobs]);

    const handleRefreshAll = () => {
        setIsLoadingStats(true);
        setIsLoadingRuns(true);
        setIsLoadingJobs(true);
        fetchSystemStats();
        fetchPipelineRuns();
        fetchBackgroundJobs();
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
                        className={`h-2 w-2 rounded-full ${isConnected ? "bg-green-500" : "bg-red-500"
                            }`}
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

            {/* Pipeline Runs and Background Jobs */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <PipelineRunsTable
                    runs={pipelineRuns.runs}
                    total={pipelineRuns.total}
                    isLoading={isLoadingRuns}
                />
                <BackgroundJobsTable jobs={backgroundJobs} isLoading={isLoadingJobs} />
            </div>

            {/* Logs Viewer */}
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
