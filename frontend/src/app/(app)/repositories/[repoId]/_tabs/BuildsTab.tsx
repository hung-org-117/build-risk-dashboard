"use client";

import {
    CheckCircle2,
    Clock,
    GitCommit,
    Loader2,
    XCircle,
    RefreshCw,
    AlertCircle,
    RotateCcw,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { useDebounce } from "@/hooks/use-debounce";
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
import { useWebSocket } from "@/contexts/websocket-context";
import { buildApi, reposApi } from "@/lib/api";
import { formatTimestamp } from "@/lib/utils";
import type { Build } from "@/types";

import { ExportPanel } from "../builds/_components/ExportPanel";

const PAGE_SIZE = 20;

function StatusBadge({ status }: { status: string }) {
    const s = status.toLowerCase();
    if (s === "success" || s === "passed") {
        return (
            <Badge variant="outline" className="border-green-500 text-green-600 gap-1">
                <CheckCircle2 className="h-3 w-3" /> Passed
            </Badge>
        );
    }
    if (s === "failure" || s === "failed") {
        return (
            <Badge variant="destructive" className="gap-1">
                <XCircle className="h-3 w-3" /> Failed
            </Badge>
        );
    }
    if (s === "cancelled" || s === "canceled") {
        return (
            <Badge variant="secondary" className="gap-1">
                <XCircle className="h-3 w-3" /> Cancelled
            </Badge>
        );
    }
    return <Badge variant="secondary">{status}</Badge>;
}

function ExtractionBadge({ status, hasTrainingData }: { status?: string; hasTrainingData: boolean }) {
    if (!hasTrainingData) {
        return (
            <Badge variant="outline" className="border-slate-400 text-slate-500 gap-1">
                <Clock className="h-3 w-3" /> Not Started
            </Badge>
        );
    }
    const s = (status || "").toLowerCase();
    if (s === "completed") {
        return (
            <Badge variant="outline" className="border-green-500 text-green-600 gap-1">
                <CheckCircle2 className="h-3 w-3" /> Done
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
                <Loader2 className="h-3 w-3 animate-spin" /> Processing
            </Badge>
        );
    }
    return <Badge variant="secondary">{status || "—"}</Badge>;
}

function RiskBadge({ level, confidence }: { level?: string; confidence?: number }) {
    if (!level) return <span className="text-muted-foreground text-xs">—</span>;

    const l = level.toUpperCase();
    const confLabel = confidence ? ` (${(confidence * 100).toFixed(0)}%)` : "";

    if (l === "LOW") {
        return (
            <Badge variant="outline" className="border-green-500 text-green-600 gap-1 whitespace-nowrap">
                <CheckCircle2 className="h-3 w-3" /> Low{confLabel}
            </Badge>
        );
    }
    if (l === "MEDIUM") {
        return (
            <Badge variant="outline" className="border-amber-500 text-amber-600 gap-1 whitespace-nowrap">
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

interface BuildsTabProps {
    repoId: string;
    repoName?: string;
}

export function BuildsTab({ repoId, repoName }: BuildsTabProps) {
    const router = useRouter();
    const [builds, setBuilds] = useState<Build[]>([]);
    const [loading, setLoading] = useState(true);
    const [tableLoading, setTableLoading] = useState(false);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);

    const [searchQuery, setSearchQuery] = useState("");
    const debouncedSearchQuery = useDebounce(searchQuery, 500);

    const [syncing, setSyncing] = useState(false);
    const [reprocessingBuilds, setReprocessingBuilds] = useState<Record<string, boolean>>({});

    const { subscribe } = useWebSocket();

    const loadBuilds = useCallback(
        async (pageNumber = 1, withSpinner = false) => {
            if (withSpinner) setTableLoading(true);
            try {
                const data = await buildApi.getByRepo(repoId, {
                    skip: (pageNumber - 1) * PAGE_SIZE,
                    limit: PAGE_SIZE,
                    q: debouncedSearchQuery || undefined,
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
        [repoId, debouncedSearchQuery]
    );

    const handleSync = async () => {
        setSyncing(true);
        try {
            await reposApi.triggerLazySync(repoId);
        } catch (err) {
            console.error(err);
        } finally {
            setSyncing(false);
        }
    };

    useEffect(() => {
        loadBuilds(1, true);
    }, [loadBuilds]);

    useEffect(() => {
        const unsubscribe = subscribe("BUILD_UPDATE", (data: any) => {
            if (data.repo_id === repoId) {
                loadBuilds(page);
            }
        });
        return () => unsubscribe();
    }, [subscribe, loadBuilds, page, repoId]);

    const totalPages = total > 0 ? Math.ceil(total / PAGE_SIZE) : 1;
    const pageStart = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
    const pageEnd = total === 0 ? 0 : Math.min(page * PAGE_SIZE, total);

    const handlePageChange = (direction: "prev" | "next") => {
        const target = direction === "prev" ? Math.max(1, page - 1) : Math.min(totalPages, page + 1);
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
        <div className="space-y-4">
            {/* Header Actions */}
            <div className="flex items-center justify-between">
                <div className="relative w-64">
                    <Input
                        placeholder="Search builds..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="h-9"
                    />
                </div>
                <div className="flex items-center gap-2">
                    <ExportPanel repoId={repoId} repoName={repoName} />
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleSync}
                        disabled={syncing}
                    >
                        {syncing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                        Sync Builds
                    </Button>
                </div>
            </div>

            {/* Table */}
            <Card>
                <CardHeader>
                    <CardTitle>Build History</CardTitle>
                    <CardDescription>All builds with extracted features</CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                    <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                            <thead className="bg-slate-50 dark:bg-slate-900/40">
                                <tr>
                                    <th className="px-4 py-3 text-left font-medium text-slate-500">Build</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-500">Build ID</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-500">Status</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-500">Commit</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-500">Branch</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-500">Date</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-500">Extraction</th>
                                    <th className="px-4 py-3 text-left font-medium text-slate-500">Risk Prediction</th>
                                    <th className="px-4 py-3" />
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                                {builds.length === 0 ? (
                                    <tr>
                                        <td colSpan={9} className="px-4 py-8 text-center text-muted-foreground">
                                            No builds recorded yet.
                                        </td>
                                    </tr>
                                ) : (
                                    builds.map((build) => (
                                        <tr
                                            key={build.id}
                                            className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-900/40 transition"
                                            onClick={() => router.push(`/repositories/${repoId}/builds/${build.id}`)}
                                        >
                                            <td className="px-4 py-3 font-medium">#{build.build_number || "—"}</td>
                                            <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{build.build_id}</td>
                                            <td className="px-4 py-3">
                                                <StatusBadge status={build.conclusion} />
                                            </td>
                                            <td className="px-4 py-3">
                                                <div className="flex items-center gap-1 font-mono text-xs">
                                                    <GitCommit className="h-3 w-3" />
                                                    {build.commit_sha?.substring(0, 7)}
                                                </div>
                                            </td>
                                            <td className="px-4 py-3 text-muted-foreground text-xs">{build.branch}</td>
                                            <td className="px-4 py-3 text-muted-foreground">{formatTimestamp(build.created_at)}</td>
                                            <td className="px-4 py-3">
                                                <ExtractionBadge status={build.extraction_status} hasTrainingData={build.has_training_data} />
                                            </td>
                                            <td className="px-4 py-3">
                                                <RiskBadge level={build.predicted_label} confidence={build.prediction_confidence} />
                                            </td>
                                            <td className="px-4 py-3">
                                                <div className="flex items-center gap-1">
                                                    <Button
                                                        size="sm"
                                                        variant="ghost"
                                                        onClick={async (e) => {
                                                            e.stopPropagation();
                                                            if (reprocessingBuilds[build.id]) return;
                                                            setReprocessingBuilds((prev) => ({ ...prev, [build.id]: true }));
                                                            try {
                                                                await buildApi.reprocess(repoId, build.id);
                                                            } catch (err) {
                                                                console.error(err);
                                                            } finally {
                                                                setReprocessingBuilds((prev) => ({ ...prev, [build.id]: false }));
                                                            }
                                                        }}
                                                        disabled={reprocessingBuilds[build.id]}
                                                        title="Reprocess"
                                                    >
                                                        {reprocessingBuilds[build.id] ? (
                                                            <Loader2 className="h-4 w-4 animate-spin" />
                                                        ) : (
                                                            <RotateCcw className="h-4 w-4" />
                                                        )}
                                                    </Button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </CardContent>
                {/* Pagination */}
                <div className="flex items-center justify-between border-t px-4 py-3 text-sm text-muted-foreground">
                    <div>
                        {total > 0 ? `Showing ${pageStart}-${pageEnd} of ${total}` : "No builds"}
                    </div>
                    <div className="flex items-center gap-2">
                        {tableLoading && <Loader2 className="h-4 w-4 animate-spin" />}
                        <Button size="sm" variant="outline" onClick={() => handlePageChange("prev")} disabled={page === 1 || tableLoading}>
                            Previous
                        </Button>
                        <span className="text-xs">Page {page} of {totalPages}</span>
                        <Button size="sm" variant="outline" onClick={() => handlePageChange("next")} disabled={page >= totalPages || tableLoading}>
                            Next
                        </Button>
                    </div>
                </div>
            </Card>
        </div>
    );
}
