"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    ChevronDown,
    ChevronUp,
    RefreshCw,
    AlertCircle,
    CheckCircle2,
    Clock,
    Loader2,
    GitCommit,
} from "lucide-react";
import { toast } from "@/components/ui/use-toast";
import { cn, formatDateTime } from "@/lib/utils";
import {
    mlScenariosApi,
    type MLScenarioImportBuildRecord,
} from "@/lib/api";

const ITEMS_PER_PAGE = 20;

/** Status config for import builds */
function getImportStatusConfig(status: string) {
    switch (status) {
        case "ingested":
            return { color: "bg-green-500/15 text-green-600", icon: CheckCircle2 };
        case "ingesting":
            return { color: "bg-blue-500/15 text-blue-600", icon: Loader2 };
        case "queued":
            return { color: "bg-yellow-500/15 text-yellow-600", icon: Clock };
        case "pending":
            return { color: "bg-gray-500/15 text-gray-600", icon: Clock };
        case "failed":
            return { color: "bg-red-500/15 text-red-600", icon: AlertCircle };
        default:
            return { color: "bg-gray-500/15 text-gray-600", icon: Clock };
    }
}

export default function IngestionPage() {
    const params = useParams();
    const scenarioId = params.scenarioId as string;

    const [builds, setBuilds] = useState<MLScenarioImportBuildRecord[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(0);
    const [loading, setLoading] = useState(true);
    const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

    const fetchBuilds = useCallback(async () => {
        try {
            setLoading(true);
            const response = await mlScenariosApi.getImportBuilds(scenarioId, {
                skip: page * ITEMS_PER_PAGE,
                limit: ITEMS_PER_PAGE,
            });
            setBuilds(response.items);
            setTotal(response.total);
        } catch (error) {
            console.error("Failed to fetch builds:", error);
            toast({
                title: "Error",
                description: "Failed to load import builds",
                variant: "destructive",
            });
        } finally {
            setLoading(false);
        }
    }, [scenarioId, page]);

    useEffect(() => {
        fetchBuilds();
    }, [fetchBuilds]);

    const toggleExpand = (buildId: string) => {
        setExpandedIds((prev) => {
            const next = new Set(prev);
            if (next.has(buildId)) {
                next.delete(buildId);
            } else {
                next.add(buildId);
            }
            return next;
        });
    };

    const totalPages = Math.ceil(total / ITEMS_PER_PAGE);

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between">
                <div>
                    <CardTitle>Import Builds</CardTitle>
                    <CardDescription>
                        {total} builds in ingestion phase
                    </CardDescription>
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={fetchBuilds}
                    disabled={loading}
                >
                    <RefreshCw className={cn("h-4 w-4 mr-2", loading && "animate-spin")} />
                    Refresh
                </Button>
            </CardHeader>
            <CardContent>
                {loading && builds.length === 0 ? (
                    <div className="flex items-center justify-center py-12">
                        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                    </div>
                ) : builds.length === 0 ? (
                    <div className="text-center py-12 text-muted-foreground">
                        No import builds found
                    </div>
                ) : (
                    <>
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead className="w-8"></TableHead>
                                    <TableHead>Repository</TableHead>
                                    <TableHead>Commit</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead>Created</TableHead>
                                    <TableHead>Ingested</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {builds.map((build) => {
                                    const statusConfig = getImportStatusConfig(build.status);
                                    const StatusIcon = statusConfig.icon;
                                    const isExpanded = expandedIds.has(build.id);

                                    return (
                                        <>
                                            <TableRow
                                                key={build.id}
                                                className="cursor-pointer hover:bg-muted/50"
                                                onClick={() => toggleExpand(build.id)}
                                            >
                                                <TableCell>
                                                    {isExpanded ? (
                                                        <ChevronUp className="h-4 w-4" />
                                                    ) : (
                                                        <ChevronDown className="h-4 w-4" />
                                                    )}
                                                </TableCell>
                                                <TableCell className="font-medium">
                                                    {build.repo_full_name}
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex items-center gap-1 font-mono text-xs">
                                                        <GitCommit className="h-3 w-3" />
                                                        {build.commit_sha?.slice(0, 8) || "—"}
                                                    </div>
                                                </TableCell>
                                                <TableCell>
                                                    <Badge className={cn("gap-1", statusConfig.color)}>
                                                        <StatusIcon className={cn(
                                                            "h-3 w-3",
                                                            build.status === "ingesting" && "animate-spin"
                                                        )} />
                                                        {build.status}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell className="text-sm text-muted-foreground">
                                                    {build.created_at ? formatDateTime(build.created_at) : "—"}
                                                </TableCell>
                                                <TableCell className="text-sm text-muted-foreground">
                                                    {build.ingested_at ? formatDateTime(build.ingested_at) : "—"}
                                                </TableCell>
                                            </TableRow>
                                            {isExpanded && (
                                                <TableRow key={`${build.id}-expanded`}>
                                                    <TableCell colSpan={6} className="bg-muted/30 p-4">
                                                        <div className="space-y-2 text-sm">
                                                            <div className="grid grid-cols-2 gap-4">
                                                                <div>
                                                                    <span className="text-muted-foreground">CI Run ID:</span>{" "}
                                                                    <span className="font-mono">{build.ci_run_id || "—"}</span>
                                                                </div>
                                                                <div>
                                                                    <span className="text-muted-foreground">GitHub Repo ID:</span>{" "}
                                                                    <span className="font-mono">{build.github_repo_id || "—"}</span>
                                                                </div>
                                                            </div>
                                                            {build.ingestion_error && (
                                                                <div className="p-2 bg-red-500/10 rounded text-red-600">
                                                                    <strong>Error:</strong> {build.ingestion_error}
                                                                </div>
                                                            )}
                                                            {build.resource_status && Object.keys(build.resource_status).length > 0 && (
                                                                <div className="mt-2">
                                                                    <div className="font-medium mb-1">Resource Status:</div>
                                                                    <div className="flex flex-wrap gap-2">
                                                                        {Object.entries(build.resource_status).map(([key, value]: [string, { status: string; error?: string }]) => (
                                                                            <Badge
                                                                                key={key}
                                                                                variant="outline"
                                                                                className={cn(
                                                                                    value.status === "completed" && "border-green-500 text-green-600",
                                                                                    value.status === "failed" && "border-red-500 text-red-600",
                                                                                    value.status === "in_progress" && "border-blue-500 text-blue-600"
                                                                                )}
                                                                            >
                                                                                {key}: {value.status}
                                                                            </Badge>
                                                                        ))}
                                                                    </div>
                                                                </div>
                                                            )}
                                                        </div>
                                                    </TableCell>
                                                </TableRow>
                                            )}
                                        </>
                                    );
                                })}
                            </TableBody>
                        </Table>

                        {/* Pagination */}
                        {totalPages > 1 && (
                            <div className="flex items-center justify-between mt-4">
                                <div className="text-sm text-muted-foreground">
                                    Showing {page * ITEMS_PER_PAGE + 1} - {Math.min((page + 1) * ITEMS_PER_PAGE, total)} of {total}
                                </div>
                                <div className="flex gap-2">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => setPage((p) => Math.max(0, p - 1))}
                                        disabled={page === 0}
                                    >
                                        Previous
                                    </Button>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                                        disabled={page >= totalPages - 1}
                                    >
                                        Next
                                    </Button>
                                </div>
                            </div>
                        )}
                    </>
                )}
            </CardContent>
        </Card>
    );
}
