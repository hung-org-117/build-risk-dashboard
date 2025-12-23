"use client";

import React, { useRef, useCallback, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { formatDistanceToNow } from "date-fns";
import {
    CheckCircle,
    XCircle,
    Clock,
    Loader2,
    AlertCircle,
    Database,
    GitBranch,
    RefreshCw,
    Layers,
} from "lucide-react";

interface PhaseResult {
    phase_name: string;
    status: "pending" | "running" | "completed" | "failed" | "skipped";
    processed_items?: number;
    total_items?: number;
    failed_items?: number;
    duration_seconds?: number;
}

interface PipelineRun {
    correlation_id: string;
    pipeline_type: "dataset_validation" | "dataset_enrichment" | "model_ingestion" | "model_processing";
    status: "pending" | "running" | "completed" | "partial" | "failed" | "cancelled";
    started_at: string | null;
    completed_at: string | null;
    duration_seconds: number | null;
    total_repos: number;
    processed_repos: number;
    total_builds: number;
    processed_builds: number;
    failed_builds: number;
    phases: PhaseResult[];
    error_message?: string;
    triggered_by?: string;
}

interface PipelineTracingTableProps {
    runs: PipelineRun[];
    hasMore: boolean;
    isLoading: boolean;
    isLoadingMore: boolean;
    onLoadMore: () => void;
}

const statusConfig: Record<
    string,
    { icon: React.ReactNode; variant: "default" | "destructive" | "secondary" | "outline"; label: string }
> = {
    completed: {
        icon: <CheckCircle className="h-3 w-3" />,
        variant: "default",
        label: "Completed",
    },
    partial: {
        icon: <AlertCircle className="h-3 w-3" />,
        variant: "secondary",
        label: "Partial",
    },
    failed: {
        icon: <XCircle className="h-3 w-3" />,
        variant: "destructive",
        label: "Failed",
    },
    running: {
        icon: <Loader2 className="h-3 w-3 animate-spin" />,
        variant: "secondary",
        label: "Running",
    },
    pending: {
        icon: <Clock className="h-3 w-3" />,
        variant: "outline",
        label: "Pending",
    },
    cancelled: {
        icon: <XCircle className="h-3 w-3" />,
        variant: "outline",
        label: "Cancelled",
    },
};

const pipelineTypeConfig: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
    dataset_validation: {
        icon: <Database className="h-3 w-3" />,
        label: "Validation",
        color: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
    },
    dataset_enrichment: {
        icon: <RefreshCw className="h-3 w-3" />,
        label: "Enrichment",
        color: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
    },
    model_ingestion: {
        icon: <GitBranch className="h-3 w-3" />,
        label: "Ingestion",
        color: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
    },
    model_processing: {
        icon: <Layers className="h-3 w-3" />,
        label: "Processing",
        color: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300",
    },
};

export function PipelineTracingTable({
    runs,
    hasMore,
    isLoading,
    isLoadingMore,
    onLoadMore,
}: PipelineTracingTableProps) {
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const loadMoreTriggerRef = useRef<HTMLDivElement>(null);

    const handleObserver = useCallback(
        (entries: IntersectionObserverEntry[]) => {
            const [entry] = entries;
            if (entry.isIntersecting && hasMore && !isLoadingMore && !isLoading) {
                onLoadMore();
            }
        },
        [hasMore, isLoadingMore, isLoading, onLoadMore]
    );

    useEffect(() => {
        const element = loadMoreTriggerRef.current;
        if (!element) return;

        const observer = new IntersectionObserver(handleObserver, {
            root: scrollContainerRef.current,
            rootMargin: "100px",
            threshold: 0.1,
        });

        observer.observe(element);
        return () => observer.disconnect();
    }, [handleObserver]);

    const formatDuration = (seconds: number | null): string => {
        if (!seconds) return "-";
        if (seconds < 60) return `${seconds.toFixed(1)}s`;
        if (seconds < 3600) return `${(seconds / 60).toFixed(1)}m`;
        return `${(seconds / 3600).toFixed(1)}h`;
    };

    const getProgressPercent = (run: PipelineRun): number => {
        if (run.total_builds === 0) return 0;
        return Math.round((run.processed_builds / run.total_builds) * 100);
    };

    const getPhasesSummary = (phases: PhaseResult[]): { completed: number; total: number; hasFailed: boolean } => {
        const total = phases.length;
        const completed = phases.filter((p) => p.status === "completed").length;
        const hasFailed = phases.some((p) => p.status === "failed");
        return { completed, total, hasFailed };
    };

    if (isLoading && runs.length === 0) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">Pipeline Runs</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="animate-pulse space-y-2">
                        {[1, 2, 3, 4, 5].map((i) => (
                            <div key={i} className="h-12 bg-muted rounded" />
                        ))}
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">Pipeline Runs</CardTitle>
                    <Badge variant="outline">{runs.length} loaded</Badge>
                </div>
            </CardHeader>
            <CardContent ref={scrollContainerRef} className="max-h-[400px] overflow-y-auto">
                <Table>
                    <TableHeader className="sticky top-0 bg-background z-10">
                        <TableRow>
                            <TableHead className="w-[100px]">Status</TableHead>
                            <TableHead className="w-[100px]">Type</TableHead>
                            <TableHead>Progress</TableHead>
                            <TableHead className="w-[90px]">Phases</TableHead>
                            <TableHead className="w-[80px]">Duration</TableHead>
                            <TableHead className="w-[100px]">Started</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {runs.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={6} className="text-center text-muted-foreground">
                                    No pipeline runs found
                                </TableCell>
                            </TableRow>
                        ) : (
                            runs.map((run) => {
                                const statusCfg = statusConfig[run.status] || statusConfig.pending;
                                const typeCfg = pipelineTypeConfig[run.pipeline_type] || pipelineTypeConfig.dataset_validation;
                                const phasesSummary = getPhasesSummary(run.phases);
                                const progressPercent = getProgressPercent(run);

                                return (
                                    <TableRow key={run.correlation_id}>
                                        <TableCell>
                                            <Badge variant={statusCfg.variant} className="gap-1">
                                                {statusCfg.icon}
                                                {statusCfg.label}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="outline" className={`gap-1 ${typeCfg.color}`}>
                                                {typeCfg.icon}
                                                {typeCfg.label}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex flex-col gap-1 min-w-[120px]">
                                                <div className="flex items-center gap-2">
                                                    <Progress value={progressPercent} className="h-2 flex-1" />
                                                    <span className="text-xs text-muted-foreground w-12 text-right">
                                                        {progressPercent}%
                                                    </span>
                                                </div>
                                                <div className="text-xs text-muted-foreground">
                                                    <span className="text-foreground font-medium">
                                                        {run.processed_builds}
                                                    </span>
                                                    /{run.total_builds} builds
                                                    {run.failed_builds > 0 && (
                                                        <span className="text-red-600 ml-1">
                                                            ({run.failed_builds} failed)
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex items-center gap-1">
                                                <span className={phasesSummary.hasFailed ? "text-red-600" : "text-green-600"}>
                                                    {phasesSummary.completed}
                                                </span>
                                                <span className="text-muted-foreground">
                                                    /{phasesSummary.total}
                                                </span>
                                                {phasesSummary.hasFailed && (
                                                    <AlertCircle className="h-3 w-3 text-red-600" />
                                                )}
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-sm">
                                            {formatDuration(run.duration_seconds)}
                                        </TableCell>
                                        <TableCell className="text-xs text-muted-foreground">
                                            {run.started_at
                                                ? formatDistanceToNow(new Date(run.started_at), {
                                                    addSuffix: true,
                                                })
                                                : "-"}
                                        </TableCell>
                                    </TableRow>
                                );
                            })
                        )}
                    </TableBody>
                </Table>

                <div ref={loadMoreTriggerRef} className="h-4" />

                {isLoadingMore && (
                    <div className="flex items-center justify-center py-4">
                        <Loader2 className="h-5 w-5 animate-spin mr-2" />
                        <span className="text-sm text-muted-foreground">Loading more...</span>
                    </div>
                )}

                {!hasMore && runs.length > 0 && (
                    <div className="text-center py-2 text-xs text-muted-foreground">
                        All {runs.length} runs loaded
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
