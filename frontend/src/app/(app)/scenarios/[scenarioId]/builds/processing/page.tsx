"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import {
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
    RotateCcw,
    Loader2,
} from "lucide-react";
import {
    trainingScenariosApi,
    TrainingEnrichmentBuildRecord,
    PaginatedResponse,
    TrainingScenarioRecord,
} from "@/lib/api/training-scenarios";
import { useSSE } from "@/contexts/sse-context";
import { useToast } from "@/components/ui/use-toast";

import { ExtractionStatusBadge, TablePagination } from "@/components/builds";
import { cn, formatDateTime } from "@/lib/utils";

// Removed statusColors in favor of ExtractionStatusBadge

export default function ProcessingBuildsPage() {
    const params = useParams<{ scenarioId: string }>();
    const scenarioId = params.scenarioId;
    const { subscribe } = useSSE();
    const { toast } = useToast();
    const router = useRouter();

    const [data, setData] = useState<PaginatedResponse<TrainingEnrichmentBuildRecord> | null>(null);
    const [scenario, setScenario] = useState<TrainingScenarioRecord | null>(null);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [retryLoading, setRetryLoading] = useState(false);
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

    // Fetch enrichment builds
    const fetchBuilds = useCallback(async () => {
        setLoading(true);
        try {
            const response = await trainingScenariosApi.getEnrichmentBuilds(scenarioId, {
                skip: (page - 1) * pageSize,
                limit: pageSize,
            });
            setData(response);
        } catch (err) {
            console.error("Failed to fetch enrichment builds:", err);
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

    // Retry handler
    const handleRetry = async () => {
        setRetryLoading(true);
        try {
            const result = await trainingScenariosApi.retryExtraction(scenarioId);
            toast({ title: result.message || "Retry started" });
            fetchBuilds();
        } catch (err) {
            toast({ variant: "destructive", title: "Failed to retry extraction" });
        } finally {
            setRetryLoading(false);
        }
    };

    const totalPages = data ? Math.ceil(data.total / pageSize) : 0;

    // Calculate failed count checking extraction_status
    const failedBuildsCount = scenario ? (scenario.builds_features_extracted_failed || 0) + (scenario.builds_missing_resource || 0) : 0;
    const hasFailedBuilds = failedBuildsCount > 0;

    return (
        <div className="space-y-4">

            <Card>
                <CardHeader className="space-y-4">
                    <div className="flex flex-row items-center justify-between">
                        <div>
                            <CardTitle>Extracted Features Builds</CardTitle>
                            <CardDescription>
                                {data?.total ?? 0} builds found
                            </CardDescription>
                        </div>
                        <div className="flex items-center gap-2">
                            <Button variant="outline" size="sm" onClick={fetchBuilds} disabled={loading}>
                                <RefreshCw className={cn("h-4 w-4 mr-2", loading && "animate-spin")} />
                                Refresh
                            </Button>

                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handleRetry}
                                disabled={retryLoading || !hasFailedBuilds}
                                className={cn(
                                    "text-amber-600 border-amber-300 hover:bg-amber-50",
                                    !hasFailedBuilds && "opacity-50"
                                )}
                            >
                                <RefreshCw className={cn("h-4 w-4 mr-2", retryLoading && "animate-spin")} />
                                Retry Failed Extraction
                            </Button>
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="p-0">
                    <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                            <thead className="bg-slate-50 dark:bg-slate-900/40">
                                <tr>
                                    <th className="px-4 py-3 text-left font-medium text-slate-900 dark:text-slate-100">Build ID</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-900 dark:text-slate-100">Commit</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-900 dark:text-slate-100">Repository</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-900 dark:text-slate-100">Status</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-900 dark:text-slate-100">Features</th>
                                    <th className="px-4 py-3 text-right font-medium text-slate-900 dark:text-slate-100">Enriched At</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                                {loading ? (
                                    Array.from({ length: 5 }).map((_, i) => (
                                        <tr key={i}>
                                            <td className="px-4 py-3"><Skeleton className="h-4 w-24" /></td>
                                            <td className="px-4 py-3"><Skeleton className="h-4 w-20" /></td>
                                            <td className="px-4 py-3"><Skeleton className="h-4 w-40" /></td>
                                            <td className="px-4 py-3"><Skeleton className="h-4 w-20" /></td>
                                            <td className="px-4 py-3"><Skeleton className="h-4 w-16" /></td>
                                            <td className="px-4 py-3"><Skeleton className="h-4 w-32" /></td>
                                        </tr>
                                    ))
                                ) : data?.items.length === 0 ? (
                                    <tr>
                                        <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                                            No processing builds found
                                        </td>
                                    </tr>
                                ) : (
                                    data?.items.map((build) => (
                                        <tr
                                            key={build.id}
                                            className="hover:bg-slate-50 dark:hover:bg-slate-900/40 transition-colors cursor-pointer"
                                            onClick={() => router.push(`/scenarios/${scenarioId}/builds/processing/${build.id}`)}
                                        >
                                            <td className="px-4 py-3 font-mono text-xs">
                                                {build.ci_run_id}
                                            </td>
                                            <td className="px-4 py-3 font-mono text-xs">
                                                {build.commit_sha?.substring(0, 8)}
                                            </td>
                                            <td className="px-4 py-3 font-medium">
                                                {build.repo_full_name}
                                            </td>
                                            <td className="px-4 py-3">
                                                <ExtractionStatusBadge status={build.extraction_status} />
                                            </td>
                                            <td className="px-4 py-3">
                                                <span className={cn(
                                                    "font-medium",
                                                    build.feature_count !== build.expected_feature_count ? "text-amber-600" : "text-slate-600 dark:text-slate-400"
                                                )}>
                                                    {build.feature_count}
                                                </span>
                                                <span className="text-muted-foreground">/{build.expected_feature_count}</span>
                                            </td>
                                            <td className="px-4 py-3 text-right text-muted-foreground tabular-nums">
                                                {formatDateTime(build.enriched_at)}
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
