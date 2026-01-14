"use client";

import { useParams } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
    ChevronLeft,
    ChevronRight,
    RefreshCw,
    Play,
    RotateCcw,
    Loader2,
} from "lucide-react";
import {
    trainingScenariosApi,
    TrainingIngestionBuildRecord,
    PaginatedResponse,
    TrainingScenarioRecord,
} from "@/lib/api/training-scenarios";
import { useSSE } from "@/contexts/sse-context";
import { useToast } from "@/components/ui/use-toast";

import { IngestionStatusBadge, TablePagination } from "@/components/builds";
import { cn } from "@/lib/utils";

// Removed statusColors in favor of IngestionStatusBadge

export default function IngestionBuildsPage() {
    const params = useParams<{ scenarioId: string }>();
    const scenarioId = params.scenarioId;
    const { subscribe } = useSSE();
    const { toast } = useToast();

    const [data, setData] = useState<PaginatedResponse<TrainingIngestionBuildRecord> | null>(null);
    const [scenario, setScenario] = useState<TrainingScenarioRecord | null>(null);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [actionLoading, setActionLoading] = useState<string | null>(null);
    const pageSize = 20;

    // Fetch scenario to get status
    const fetchScenario = useCallback(async () => {
        try {
            const data = await trainingScenariosApi.get(scenarioId);
            setScenario(data);
        } catch (err) {
            console.error("Failed to fetch scenario:", err);
        }
    }, [scenarioId]);

    // Fetch ingestion builds
    const fetchBuilds = useCallback(async () => {
        setLoading(true);
        try {
            const response = await trainingScenariosApi.getIngestionBuilds(scenarioId, {
                skip: (page - 1) * pageSize,
                limit: pageSize,
            });
            setData(response);
        } catch (err) {
            console.error("Failed to fetch ingestion builds:", err);
        } finally {
            setLoading(false);
        }
    }, [scenarioId, page]);

    useEffect(() => {
        fetchScenario();
        fetchBuilds();
    }, [fetchScenario, fetchBuilds]);

    // SSE subscription - refetch on scenario updates
    useEffect(() => {
        const unsubscribe = subscribe("SCENARIO_UPDATE", (payload: { scenario_id?: string }) => {
            if (payload.scenario_id === scenarioId) {
                fetchScenario();
                fetchBuilds();
            }
        });
        return () => unsubscribe();
    }, [subscribe, scenarioId, fetchScenario, fetchBuilds]);

    // Action handlers
    const handleStartProcessing = async () => {
        setActionLoading("processing");
        try {
            await trainingScenariosApi.startProcessing(scenarioId);
            toast({ title: "Processing started successfully" });
            fetchScenario();
        } catch (err) {
            toast({ variant: "destructive", title: "Failed to start processing" });
        } finally {
            setActionLoading(null);
        }
    };

    const handleRetryIngestion = async () => {
        setActionLoading("retry");
        try {
            const result = await trainingScenariosApi.retryIngestion(scenarioId);
            toast({ title: result.message || "Retry started" });
            fetchBuilds();
        } catch (err) {
            toast({ variant: "destructive", title: "Failed to retry ingestion" });
        } finally {
            setActionLoading(null);
        }
    };

    const totalPages = data ? Math.ceil(data.total / pageSize) : 0;

    // Calculate failed count
    const failedCount = scenario
        ? (scenario.builds_failed || 0) + (scenario.builds_missing_resource || 0)
        : 0;

    // Determine available actions
    const canStartProcessing = scenario?.status === "ingested";
    const canRetry = failedCount > 0 && ["ingested", "processing", "processed"].includes(scenario?.status || "");

    return (
        <div className="space-y-4">
            {/* Action Card */}
            {(canStartProcessing || canRetry) && (
                <Card>
                    <CardHeader className="pb-3">
                        <div className="flex items-center justify-between">
                            <div>
                                <CardTitle className="text-base">Ingestion Actions</CardTitle>
                                <CardDescription>
                                    {canStartProcessing
                                        ? "Ingestion complete. Start processing to extract features."
                                        : `${failedCount} builds failed ingestion`}
                                </CardDescription>
                            </div>
                            <div className="flex gap-2">
                                {canRetry && (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={handleRetryIngestion}
                                        disabled={actionLoading === "retry"}
                                    >
                                        {actionLoading === "retry" ? (
                                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                        ) : (
                                            <RotateCcw className="h-4 w-4 mr-2" />
                                        )}
                                        Retry Failed ({failedCount})
                                    </Button>
                                )}
                                {canStartProcessing && (
                                    <Button
                                        size="sm"
                                        onClick={handleStartProcessing}
                                        disabled={actionLoading === "processing"}
                                    >
                                        {actionLoading === "processing" ? (
                                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                        ) : (
                                            <Play className="h-4 w-4 mr-2" />
                                        )}
                                        Start Processing
                                    </Button>
                                )}
                            </div>
                        </div>
                    </CardHeader>
                </Card>
            )}

            {/* Header with refresh is now part of CardHeader in new design, but we keep Action Card separate */}

            <Card>
                <CardHeader className="space-y-4">
                    <div className="flex flex-row items-center justify-between">
                        <div>
                            <CardTitle>Ingestion Builds</CardTitle>
                            <CardDescription>
                                {data?.total ?? 0} builds found
                            </CardDescription>
                        </div>
                        <Button variant="outline" size="sm" onClick={fetchBuilds} disabled={loading}>
                            <RefreshCw className={cn("h-4 w-4 mr-2", loading && "animate-spin")} />
                            Refresh
                        </Button>
                    </div>
                </CardHeader>
                <CardContent className="p-0">
                    <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                            <thead className="bg-slate-50 dark:bg-slate-900/40">
                                <tr>
                                    <th className="px-4 py-3 text-left font-medium text-slate-500">Repository</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-500">Commit</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-500">CI Run ID</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-500">Status</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-500">Created</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                                {loading ? (
                                    Array.from({ length: 5 }).map((_, i) => (
                                        <tr key={i}>
                                            <td className="px-4 py-3"><Skeleton className="h-4 w-40" /></td>
                                            <td className="px-4 py-3"><Skeleton className="h-4 w-20" /></td>
                                            <td className="px-4 py-3"><Skeleton className="h-4 w-32" /></td>
                                            <td className="px-4 py-3"><Skeleton className="h-4 w-20" /></td>
                                            <td className="px-4 py-3"><Skeleton className="h-4 w-24" /></td>
                                        </tr>
                                    ))
                                ) : data?.items.length === 0 ? (
                                    <tr>
                                        <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                                            No ingestion builds found
                                        </td>
                                    </tr>
                                ) : (
                                    data?.items.map((build) => (
                                        <tr key={build.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/40 transition-colors">
                                            <td className="px-4 py-3 font-medium">{build.repo_full_name}</td>
                                            <td className="px-4 py-3 font-mono text-xs">{build.commit_sha.slice(0, 7)}</td>
                                            <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{build.ci_run_id}</td>
                                            <td className="px-4 py-3">
                                                <IngestionStatusBadge status={build.status as any} />
                                            </td>
                                            <td className="px-4 py-3 text-muted-foreground">
                                                {build.created_at
                                                    ? new Date(build.created_at).toLocaleDateString()
                                                    : "-"}
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                    <TablePagination
                        currentPage={page}
                        totalPages={totalPages}
                        totalItems={data?.total || 0}
                        pageSize={pageSize}
                        onPageChange={setPage}
                        isLoading={loading}
                    />
                </CardContent>
            </Card>
        </div>
    );
}
