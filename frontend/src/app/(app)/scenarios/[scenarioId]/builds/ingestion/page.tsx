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
    ChevronDown,
    RefreshCw,
    Play,
    RotateCcw,
    Loader2,
    CheckCircle2,
    XCircle,
    Clock,
    GitCommit,
    Settings,
    ExternalLink,
} from "lucide-react";
import {
    trainingScenariosApi,
    TrainingIngestionBuildRecord,
    PaginatedResponse,
    TrainingScenarioRecord,
}
    from "@/lib/api/training-scenarios";
import { useSSE } from "@/contexts/sse-context";
import { useToast } from "@/components/ui/use-toast";
import { useDebouncedCallback } from "@/hooks/use-debounced-callback";

import { IngestionStatusBadge, TablePagination, ResourceStatusIndicator } from "@/components/builds";
import { cn, formatTimestamp } from "@/lib/utils";

function IngestionBuildRow({ build }: { build: TrainingIngestionBuildRecord }) {
    const [expanded, setExpanded] = useState(false);
    const hasResources = build.resource_status && Object.keys(build.resource_status).length > 0;

    return (
        <>
            <tr
                className={cn(
                    "hover:bg-slate-50 dark:hover:bg-slate-900/40 transition-colors border-b cursor-pointer",
                    expanded && "bg-slate-50 dark:bg-slate-900/40"
                )}
                onClick={() => setExpanded(!expanded)}
            >
                <td className="px-4 py-3 w-[50px]">
                    <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        onClick={(e) => {
                            e.stopPropagation();
                            setExpanded(!expanded);
                        }}
                    >
                        {expanded ? (
                            <ChevronDown className="h-4 w-4" />
                        ) : (
                            <ChevronRight className="h-4 w-4" />
                        )}
                    </Button>
                </td>
                <td className="px-4 py-3">
                    <span className="font-medium font-mono text-xs">
                        {build.ci_run_id || "—"}
                    </span>
                </td>
                <td className="px-4 py-3">
                    <div className="flex items-center gap-1 font-mono text-xs">
                        <GitCommit className="h-3 w-3" />
                        <span>{build.commit_sha.slice(0, 7)}</span>
                    </div>
                </td>
                <td className="px-4 py-3 font-medium text-sm">{build.repo_full_name}</td>
                <td className="px-4 py-3">
                    <IngestionStatusBadge status={build.status as any} />
                </td>
                <td className="px-4 py-3 text-muted-foreground whitespace-nowrap text-sm">
                    {formatTimestamp(build.created_at)}
                </td>
            </tr>
            {expanded && (
                <tr className="bg-slate-50 dark:bg-slate-900/20 shadow-inner">
                    <td colSpan={6} className="px-4 py-4">
                        <div className="space-y-6">
                            {/* Commit Info & CI Info */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                {/* Commit Info */}
                                <div>
                                    <h4 className="font-medium text-sm text-slate-900 dark:text-slate-100 flex items-center gap-2 mb-2">
                                        <GitCommit className="h-4 w-4" />
                                        Commit Info
                                    </h4>
                                    <div className="space-y-1 text-sm text-muted-foreground">
                                        <div>
                                            <span className="text-muted-foreground">SHA: </span>
                                            <span className="font-mono text-xs text-foreground">{build.commit_sha}</span>
                                        </div>
                                        {/* Missing details placeholders */}
                                        <div>
                                            <span className="text-muted-foreground">Repo: </span>
                                            <span className="text-foreground">{build.repo_full_name}</span>
                                        </div>
                                    </div>
                                </div>

                                {/* CI Build Info */}
                                <div>
                                    <h4 className="font-medium text-sm text-slate-900 dark:text-slate-100 flex items-center gap-2 mb-2">
                                        <Settings className="h-4 w-4" />
                                        CI Build Info
                                    </h4>
                                    <div className="space-y-1 text-sm text-muted-foreground">
                                        <div>
                                            <span className="text-muted-foreground">Run ID: </span>
                                            <span className="text-foreground">{build.ci_run_id}</span>
                                        </div>
                                        <div>
                                            <span className="text-muted-foreground">Provider: </span>
                                            <span className="text-foreground">GitHub Actions</span>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Resources Collected */}
                            {hasResources && (
                                <div>
                                    <h4 className="font-medium text-sm text-slate-900 dark:text-slate-100 mb-2">
                                        Resources Collected
                                    </h4>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                                        {Object.entries(build.resource_status || {}).map(([resourceKey, resourceData]) => (
                                            <ResourceStatusIndicator
                                                key={resourceKey}
                                                resourceName={resourceKey}
                                                status={resourceData.status}
                                                error={resourceData.error}
                                            />
                                        ))}
                                    </div>
                                </div>
                            )}

                            {build.ingestion_error && (
                                <div className="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
                                    <p className="font-medium text-red-600 text-sm">
                                        Ingestion Error:
                                    </p>
                                    <p className="text-red-700 text-xs mt-1">
                                        {build.ingestion_error}
                                    </p>
                                </div>
                            )}
                        </div>
                    </td>
                </tr>
            )}
        </>
    );
}



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

    // Debounced refetch for scenario updates that affect aggregate stats
    const debouncedFetchBuilds = useDebouncedCallback(fetchBuilds, 1000, {
        leading: true,
        trailing: true,
    });

    // SSE subscription - merge delta for individual builds, debounce scenario updates
    useEffect(() => {
        // For scenario-level updates, use debounced refetch (affects stats, not individual rows)
        const unsubscribeScenario = subscribe("SCENARIO.UPDATED", (payload: Partial<TrainingScenarioRecord> & { scenario_id?: string }) => {
            if (payload.scenario_id === scenarioId) {
                // Merge scenario stats directly instead of refetch
                setScenario((prev) =>
                    prev
                        ? {
                            ...prev,
                            ...payload,
                            status: payload.status || prev.status,
                        }
                        : prev
                );
                // Debounced refetch for builds only when status changes
                if (payload.status && ["ingesting", "ingested", "failed"].includes(payload.status)) {
                    debouncedFetchBuilds();
                }
            }
        });

        // For individual ingestion build updates - merge delta into local state
        const unsubscribeIngestion = subscribe("SCENARIO.INGESTION.UPDATED", (payload: {
            scenario_id?: string;
            build_id: string;
            status: string;
            resource_status?: Record<string, { status: string; error?: string }>;
            ci_run_id?: string;
            commit_sha?: string;
            repo_full_name?: string;
        }) => {
            if (payload.scenario_id === scenarioId && payload.build_id) {
                // Merge delta into existing data - no refetch needed!
                setData((prev) => {
                    if (!prev) return prev;
                    const updatedItems = prev.items.map((build) =>
                        build.id === payload.build_id
                            ? {
                                ...build,
                                status: (payload.status as TrainingIngestionBuildRecord["status"]) || build.status,
                                resource_status: payload.resource_status || build.resource_status,
                            }
                            : build
                    );
                    return { ...prev, items: updatedItems };
                });
            }
        });

        return () => {
            unsubscribeScenario();
            unsubscribeIngestion();
        };
    }, [subscribe, scenarioId, debouncedFetchBuilds]);

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
            await trainingScenariosApi.retryIngestion(scenarioId);
            toast({ title: "Retry started" });
            fetchBuilds();
        } catch (err) {
            toast({ variant: "destructive", title: "Failed to retry ingestion" });
        } finally {
            setActionLoading(null);
        }
    };

    const totalPages = data ? Math.ceil(data.total / pageSize) : 0;

    // Calculate failed count (ingestion + extraction + missing resource)
    const failedCount = scenario
        ? (scenario.builds_ingestion_failed || 0) + (scenario.builds_features_extracted_failed || 0) + (scenario.builds_missing_resource || 0)
        : 0;

    // Determine available actions
    const canStartProcessing = scenario?.status === "ingested";
    const canRetry = failedCount > 0;

    return (
        <div className="space-y-4">
            <Card>
                <CardHeader className="space-y-4">
                    <div className="flex flex-row items-center justify-between">
                        <div>
                            <CardTitle>Build Resources</CardTitle>
                            <CardDescription>
                                {data?.total ?? 0} builds found
                            </CardDescription>
                        </div>
                        <div className="flex items-center gap-2">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={fetchBuilds}
                                disabled={loading}
                            >
                                <RefreshCw className={cn("h-4 w-4 mr-1", loading && "animate-spin")} />
                                Refresh
                            </Button>

                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handleRetryIngestion}
                                disabled={actionLoading === "retry" || failedCount === 0}
                                className={cn(
                                    "text-amber-600 border-amber-300 hover:bg-amber-50",
                                    failedCount === 0 && "opacity-50"
                                )}
                            >
                                {actionLoading === "retry" ? (
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                ) : (
                                    <RotateCcw className="h-4 w-4 mr-2" />
                                )}
                                Retry Failed Ingestion {failedCount > 0 && `(${failedCount})`}
                            </Button>

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
                <CardContent className="p-0">
                    <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                            <thead className="bg-slate-50 dark:bg-slate-900/40">
                                <tr>
                                    <th className="w-[50px]"></th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-500">Build ID</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-500">Commit</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-500">Repository</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-500">Status</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-500">Created At</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                                {loading ? (
                                    Array.from({ length: 5 }).map((_, i) => (
                                        <tr key={i}>
                                            <td className="px-4 py-3"><Skeleton className="h-4 w-4" /></td>
                                            <td className="px-4 py-3"><Skeleton className="h-4 w-16" /></td>
                                            <td className="px-4 py-3"><Skeleton className="h-4 w-20" /></td>
                                            <td className="px-4 py-3"><Skeleton className="h-4 w-40" /></td>
                                            <td className="px-4 py-3"><Skeleton className="h-4 w-20" /></td>
                                            <td className="px-4 py-3"><Skeleton className="h-4 w-24" /></td>
                                        </tr>
                                    ))
                                ) : data?.items.length === 0 ? (
                                    <tr>
                                        <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                                            No ingestion builds found
                                        </td>
                                    </tr>
                                ) : (
                                    data?.items.map((build) => (
                                        <IngestionBuildRow key={build.id} build={build} />
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
