"use client";

import {
    AlertCircle,
    CheckCircle2,
    ChevronDown,
    ChevronRight,
    Clock,
    GitCommit,
    Loader2,
    RotateCcw,
    XCircle,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
    SearchFilterBar,
    PROCESSING_STATUS_OPTIONS,
    ExtractionStatusBadge,
    TablePagination,
} from "@/components/builds";
import { useWebSocket } from "@/contexts/websocket-context";
import { buildApi } from "@/lib/api";
import { formatTimestamp, cn } from "@/lib/utils";
import type { TrainingBuild } from "@/types";

const PAGE_SIZE = 20;

// Mini status indicator for pipeline steps
function StatusDot({ status }: { status: string }) {
    const s = (status || "pending").toLowerCase();

    if (s === "completed") {
        return <CheckCircle2 className="h-4 w-4 text-green-600" />;
    }
    if (s === "partial") {
        return <AlertCircle className="h-4 w-4 text-amber-500" />;
    }
    if (s === "failed") {
        return <XCircle className="h-4 w-4 text-red-500" />;
    }
    if (s === "in_progress") {
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
    }
    // pending or unknown
    return <Clock className="h-4 w-4 text-slate-400" />;
}

// Pipeline status showing both extraction and prediction in a mini stepper
function PipelineStatusBadge({
    extractionStatus,
    predictionStatus,
}: {
    extractionStatus: string;
    predictionStatus?: string;
}) {
    const extStatus = (extractionStatus || "pending").toLowerCase();
    const predStatus = (predictionStatus || "pending").toLowerCase();

    // Determine prediction display status
    const showPrediction = extStatus === "completed" || extStatus === "partial";

    return (
        <div className="flex items-center gap-1.5">
            {/* Extraction step */}
            <div className="flex items-center gap-1" title={`Extraction: ${extractionStatus}`}>
                <StatusDot status={extractionStatus} />
                <span className="text-xs text-muted-foreground">Ext</span>
            </div>

            {/* Arrow connector */}
            <span className="text-slate-300 dark:text-slate-600">→</span>

            {/* Prediction step */}
            <div
                className={cn(
                    "flex items-center gap-1",
                    !showPrediction && "opacity-40"
                )}
                title={showPrediction ? `Prediction: ${predictionStatus || "pending"}` : "Waiting for extraction"}
            >
                <StatusDot status={showPrediction ? (predictionStatus || "pending") : "pending"} />
                <span className="text-xs text-muted-foreground">Pred</span>
            </div>
        </div>
    );
}

// Keep LocalExtractionStatusBadge for expanded row details
function LocalExtractionStatusBadge({ status }: { status: string }) {
    // Use shared badge but with local styling for inline display
    const s = (status || "pending").toLowerCase();
    if (s === "completed") {
        return (
            <Badge variant="outline" className="border-green-500 text-green-600 gap-1">
                <CheckCircle2 className="h-3 w-3" /> Completed
            </Badge>
        );
    }
    if (s === "partial") {
        return (
            <Badge variant="outline" className="border-amber-500 text-amber-600 gap-1">
                <AlertCircle className="h-3 w-3" /> Partial
            </Badge>
        );
    }
    if (s === "failed") {
        return (
            <Badge variant="destructive" className="gap-1">
                <XCircle className="h-3 w-3" /> Failed
            </Badge>
        );
    }
    if (s === "pending") {
        return (
            <Badge variant="secondary" className="gap-1">
                <Clock className="h-3 w-3" /> Pending
            </Badge>
        );
    }
    if (s === "in_progress") {
        return (
            <Badge variant="secondary" className="gap-1">
                <Loader2 className="h-3 w-3 animate-spin" /> Processing
            </Badge>
        );
    }
    return <Badge variant="secondary">{status || "—"}</Badge>;
}

function RiskBadge({
    level,
    confidence,
    uncertainty,
}: {
    level?: string;
    confidence?: number;
    uncertainty?: number;
}) {
    if (!level) return <span className="text-muted-foreground text-xs">—</span>;

    const l = level.toUpperCase();
    const confLabel = confidence ? ` (${(confidence * 100).toFixed(0)}%)` : "";

    if (l === "LOW") {
        return (
            <Badge
                variant="outline"
                className="border-green-500 text-green-600 gap-1 whitespace-nowrap"
            >
                <CheckCircle2 className="h-3 w-3" /> Low{confLabel}
            </Badge>
        );
    }
    if (l === "MEDIUM") {
        return (
            <Badge
                variant="outline"
                className="border-amber-500 text-amber-600 gap-1 whitespace-nowrap"
            >
                <AlertCircle className="h-3 w-3" /> Medium{confLabel}
            </Badge>
        );
    }
    if (l === "HIGH") {
        return (
            <Badge variant="destructive" className="gap-1 whitespace-nowrap">
                <XCircle className="h-3 w-3" /> High{confLabel}
            </Badge>
        );
    }
    return <Badge variant="secondary">{level}</Badge>;
}

interface ProcessingBuildsTableProps {
    repoId: string;
    onRetryAllFailed?: () => void;
    retryAllLoading?: boolean;
    totalFailedCount?: number;
}

export function ProcessingBuildsTable({
    repoId,
    onRetryAllFailed,
    retryAllLoading,
    totalFailedCount = 0,
}: ProcessingBuildsTableProps) {
    const router = useRouter();
    const [builds, setBuilds] = useState<TrainingBuild[]>([]);
    const [loading, setLoading] = useState(true);
    const [tableLoading, setTableLoading] = useState(false);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

    // Search and filter state
    const [searchQuery, setSearchQuery] = useState("");
    const [statusFilter, setStatusFilter] = useState("all");

    const { subscribe } = useWebSocket();

    const loadBuilds = useCallback(
        async (pageNumber = 1, withSpinner = false) => {
            if (withSpinner) setTableLoading(true);
            try {
                const data = await buildApi.getTrainingBuilds(repoId, {
                    skip: (pageNumber - 1) * PAGE_SIZE,
                    limit: PAGE_SIZE,
                    q: searchQuery || undefined,
                    extraction_status: statusFilter !== "all" ? statusFilter : undefined,
                });
                setBuilds(data.items);
                setTotal(data.total);
                setPage(pageNumber);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
                setTableLoading(false);
            }
        },
        [repoId, searchQuery, statusFilter]
    );

    useEffect(() => {
        loadBuilds(1, true);
    }, [loadBuilds]);

    // Search handler - reset to page 1
    const handleSearch = useCallback((query: string) => {
        setSearchQuery(query);
        setPage(1);
    }, []);

    // Status filter handler - reset to page 1
    const handleStatusFilter = useCallback((status: string) => {
        setStatusFilter(status);
        setPage(1);
    }, []);

    useEffect(() => {
        const unsubscribe = subscribe("BUILD_UPDATE", (data: any) => {
            if (data.repo_id === repoId) {
                loadBuilds(page);
            }
        });
        return () => unsubscribe();
    }, [subscribe, loadBuilds, page, repoId]);

    const toggleRow = (id: string) => {
        setExpandedRows((prev) => {
            const next = new Set(prev);
            if (next.has(id)) {
                next.delete(id);
            } else {
                next.add(id);
            }
            return next;
        });
    };

    const totalPages = total > 0 ? Math.ceil(total / PAGE_SIZE) : 1;

    const handlePageChange = (direction: "prev" | "next") => {
        const target =
            direction === "prev"
                ? Math.max(1, page - 1)
                : Math.min(totalPages, page + 1);
        if (target !== page) loadBuilds(target, true);
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <Card>
            <CardHeader className="space-y-4">
                <div className="flex flex-row items-center justify-between">
                    <div>
                        <CardTitle>Processing Builds</CardTitle>
                        <CardDescription>
                            Feature extraction and risk prediction results
                        </CardDescription>
                    </div>
                    {/* Retry Failed button - always visible, disabled when no failed builds */}
                    {onRetryAllFailed && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={onRetryAllFailed}
                            disabled={retryAllLoading || totalFailedCount === 0}
                            className={cn(
                                "text-amber-600 border-amber-300 hover:bg-amber-50 dark:hover:bg-amber-950/30",
                                totalFailedCount === 0 && "opacity-50 cursor-not-allowed"
                            )}
                        >
                            {retryAllLoading ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                                <RotateCcw className="mr-2 h-4 w-4" />
                            )}
                            Retry Failed ({totalFailedCount})
                        </Button>
                    )}
                </div>
                {/* Search and Filter Bar */}
                <SearchFilterBar
                    placeholder="Search by commit SHA or build number..."
                    statusOptions={PROCESSING_STATUS_OPTIONS}
                    onSearch={handleSearch}
                    onStatusFilter={handleStatusFilter}
                    isLoading={tableLoading}
                />
            </CardHeader>
            <CardContent className="p-0">
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                        <thead className="bg-slate-50 dark:bg-slate-900/40">
                            <tr>
                                <th className="px-4 py-3" />
                                <th className="px-4 py-3 text-left font-medium text-slate-500">
                                    Build
                                </th>
                                <th className="px-4 py-3 text-left font-medium text-slate-500">
                                    Commit
                                </th>
                                <th className="px-4 py-3 text-left font-medium text-slate-500">
                                    Pipeline Status
                                </th>
                                <th className="px-4 py-3 text-left font-medium text-slate-500">
                                    Features
                                </th>
                                <th className="px-4 py-3 text-left font-medium text-slate-500">
                                    Risk
                                </th>
                                <th className="px-4 py-3 text-left font-medium text-slate-500">
                                    Uncertainty
                                </th>
                                <th className="px-4 py-3 text-left font-medium text-slate-500">
                                    Date
                                </th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                            {builds.length === 0 ? (
                                <tr>
                                    <td
                                        colSpan={8}
                                        className="px-4 py-8 text-center text-muted-foreground"
                                    >
                                        No processing builds found.
                                    </td>
                                </tr>
                            ) : (
                                builds.map((build) => {
                                    const isExpanded = expandedRows.has(build.id);
                                    const hasIssues =
                                        build.extraction_error ||
                                        (build.missing_resources?.length || 0) > 0 ||
                                        (build.skipped_features?.length || 0) > 0;

                                    return (
                                        <Collapsible
                                            key={build.id}
                                            open={isExpanded}
                                            onOpenChange={() => toggleRow(build.id)}
                                            asChild
                                        >
                                            <>
                                                <tr
                                                    className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-900/40 transition"
                                                    onClick={() =>
                                                        router.push(
                                                            `/build/${repoId}/${build.id}`
                                                        )
                                                    }
                                                >
                                                    <td
                                                        className="px-4 py-3"
                                                        onClick={(e) => e.stopPropagation()}
                                                    >
                                                        {hasIssues && (
                                                            <CollapsibleTrigger asChild>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="sm"
                                                                    className="h-6 w-6 p-0"
                                                                >
                                                                    {isExpanded ? (
                                                                        <ChevronDown className="h-4 w-4" />
                                                                    ) : (
                                                                        <ChevronRight className="h-4 w-4" />
                                                                    )}
                                                                </Button>
                                                            </CollapsibleTrigger>
                                                        )}
                                                    </td>
                                                    <td className="px-4 py-3 font-medium">
                                                        #{build.build_number || "—"}
                                                    </td>
                                                    <td className="px-4 py-3">
                                                        <div className="flex items-center gap-1 font-mono text-xs">
                                                            <GitCommit className="h-3 w-3" />
                                                            {build.commit_sha?.substring(0, 7)}
                                                        </div>
                                                    </td>
                                                    <td className="px-4 py-3">
                                                        <PipelineStatusBadge
                                                            extractionStatus={build.extraction_status}
                                                            predictionStatus={build.prediction_status}
                                                        />
                                                    </td>
                                                    <td className="px-4 py-3 text-muted-foreground">
                                                        {build.feature_count || 0}
                                                    </td>
                                                    <td className="px-4 py-3">
                                                        <RiskBadge
                                                            level={build.predicted_label}
                                                            confidence={build.prediction_confidence}
                                                            uncertainty={build.prediction_uncertainty}
                                                        />
                                                    </td>
                                                    <td className="px-4 py-3 text-muted-foreground">
                                                        {build.prediction_uncertainty
                                                            ? `±${(build.prediction_uncertainty * 100).toFixed(1)}%`
                                                            : "—"}
                                                    </td>
                                                    <td className="px-4 py-3 text-muted-foreground">
                                                        {formatTimestamp(build.created_at)}
                                                    </td>
                                                </tr>
                                                {hasIssues && (
                                                    <CollapsibleContent asChild>
                                                        <tr className="bg-amber-50 dark:bg-amber-900/10">
                                                            <td colSpan={8} className="px-4 py-3">
                                                                <div className="space-y-2 text-sm">
                                                                    {build.extraction_error && (
                                                                        <div>
                                                                            <p className="font-medium text-red-600">
                                                                                Error:
                                                                            </p>
                                                                            <p className="text-muted-foreground">
                                                                                {build.extraction_error}
                                                                            </p>
                                                                        </div>
                                                                    )}
                                                                    {(build.missing_resources?.length || 0) > 0 && (
                                                                        <div>
                                                                            <p className="font-medium text-amber-600">
                                                                                Missing Resources:
                                                                            </p>
                                                                            <p className="text-muted-foreground font-mono text-xs">
                                                                                {build.missing_resources?.join(", ")}
                                                                            </p>
                                                                        </div>
                                                                    )}
                                                                    {(build.skipped_features?.length || 0) > 0 && (
                                                                        <div>
                                                                            <p className="font-medium text-amber-600">
                                                                                Skipped Features:
                                                                            </p>
                                                                            <p className="text-muted-foreground font-mono text-xs">
                                                                                {build.skipped_features?.join(", ")}
                                                                            </p>
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    </CollapsibleContent>
                                                )}
                                            </>
                                        </Collapsible>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>
                {/* Pagination */}
                <TablePagination
                    currentPage={page}
                    totalPages={totalPages}
                    totalItems={total}
                    pageSize={PAGE_SIZE}
                    onPageChange={(newPage) => loadBuilds(newPage, true)}
                    isLoading={tableLoading}
                />
            </CardContent>
        </Card>
    );
}
