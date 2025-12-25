"use client";

import { useState, useCallback, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
    CheckCircle,
    XCircle,
    Clock,
    Loader2,
    ChevronDown,
    ChevronRight,
    AlertTriangle,
    SkipForward,
    ChevronLeft,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface FeatureAuditLog {
    id: string;
    status: string;
    started_at: string | null;
    completed_at: string | null;
    duration_ms: number | null;
    feature_count: number;
    nodes_executed: number;
    nodes_succeeded: number;
    nodes_failed: number;
    errors: string[];
    repo?: { full_name?: string };
    build?: { build_number?: number; branch?: string; workflow_name?: string };
}

interface NodeExecutionResult {
    node_name: string;
    status: string;
    duration_ms: number;
    features_extracted: string[];
    feature_values?: Record<string, unknown>;
    resources_used?: string[];
    error?: string;
    skip_reason?: string;
}

interface AuditLogDetail {
    node_results: NodeExecutionResult[];
    features_extracted: string[];
    nodes_skipped: number;
}

interface VersionLogsSectionProps {
    datasetId: string;
    versionId: string;
}

const PAGE_SIZE = 20;

const statusConfig: Record<string, { icon: React.ReactNode; variant: "default" | "destructive" | "secondary" }> = {
    completed: { icon: <CheckCircle className="h-3 w-3" />, variant: "default" },
    failed: { icon: <XCircle className="h-3 w-3" />, variant: "destructive" },
    running: { icon: <Loader2 className="h-3 w-3 animate-spin" />, variant: "secondary" },
    pending: { icon: <Clock className="h-3 w-3" />, variant: "secondary" },
};

const nodeStatusIcons: Record<string, React.ReactNode> = {
    success: <CheckCircle className="h-3.5 w-3.5 text-green-600" />,
    failed: <XCircle className="h-3.5 w-3.5 text-red-600" />,
    skipped: <SkipForward className="h-3.5 w-3.5 text-muted-foreground" />,
};

function formatDuration(ms: number | null | undefined): string {
    if (ms === null || ms === undefined) return "-";
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
}

export function VersionLogsSection({ datasetId, versionId }: VersionLogsSectionProps) {
    const [logs, setLogs] = useState<FeatureAuditLog[]>([]);
    const [loading, setLoading] = useState(false);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [total, setTotal] = useState(0);
    const [expandedLogId, setExpandedLogId] = useState<string | null>(null);
    const [logDetails, setLogDetails] = useState<Record<string, AuditLogDetail>>({});

    // Fetch logs with page-based pagination
    const fetchLogs = useCallback(async (pageNum: number) => {
        setLoading(true);
        try {
            const res = await fetch(
                `${API_BASE}/datasets/${datasetId}/audit-logs?version_id=${versionId}&page=${pageNum}&page_size=${PAGE_SIZE}`,
                { credentials: "include" }
            );
            if (res.ok) {
                const data = await res.json();
                setLogs(data.logs || []);
                setTotalPages(data.total_pages || 1);
                setTotal(data.total || 0);
            }
        } catch (err) {
            console.error("Failed to fetch logs:", err);
        } finally {
            setLoading(false);
        }
    }, [datasetId, versionId]);

    useEffect(() => {
        if (versionId) {
            fetchLogs(1);
            setPage(1);
        }
    }, [versionId, fetchLogs]);

    const handlePageChange = (newPage: number) => {
        setPage(newPage);
        fetchLogs(newPage);
    };

    const handleToggleDetail = async (logId: string) => {
        if (expandedLogId === logId) {
            setExpandedLogId(null);
            return;
        }
        setExpandedLogId(logId);

        if (!logDetails[logId]) {
            try {
                const res = await fetch(
                    `${API_BASE}/datasets/${datasetId}/audit-logs/${logId}`,
                    { credentials: "include" }
                );
                if (res.ok) {
                    const detail = await res.json();
                    setLogDetails((prev) => ({ ...prev, [logId]: detail }));
                }
            } catch (err) {
                console.error("Failed to fetch log detail:", err);
            }
        }
    };

    if (loading && logs.length === 0) {
        return (
            <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin mr-2" />
                <span className="text-muted-foreground">Loading logs...</span>
            </div>
        );
    }

    if (logs.length === 0 && !loading) {
        return (
            <div className="text-center py-8 text-muted-foreground">
                No extraction logs for this version
            </div>
        );
    }

    return (
        <div className="space-y-3">
            <div className="border rounded-lg overflow-hidden">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-8"></TableHead>
                            <TableHead>Repository</TableHead>
                            <TableHead>Build</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead>Features</TableHead>
                            <TableHead>Duration</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {logs.map((log) => (
                            <>
                                <TableRow
                                    key={log.id}
                                    className="cursor-pointer hover:bg-muted/50"
                                    onClick={() => handleToggleDetail(log.id)}
                                >
                                    <TableCell>
                                        {expandedLogId === log.id ? (
                                            <ChevronDown className="h-4 w-4" />
                                        ) : (
                                            <ChevronRight className="h-4 w-4" />
                                        )}
                                    </TableCell>
                                    <TableCell className="font-mono text-xs">
                                        {log.repo?.full_name || "-"}
                                    </TableCell>
                                    <TableCell>
                                        <span className="text-xs">
                                            #{log.build?.build_number || "-"}
                                        </span>
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant={statusConfig[log.status]?.variant || "secondary"}>
                                            <span className="flex items-center gap-1">
                                                {statusConfig[log.status]?.icon}
                                                {log.status}
                                            </span>
                                        </Badge>
                                    </TableCell>
                                    <TableCell>{log.feature_count}</TableCell>
                                    <TableCell className="text-xs">
                                        {formatDuration(log.duration_ms)}
                                    </TableCell>
                                </TableRow>
                                {expandedLogId === log.id && logDetails[log.id] && (
                                    <TableRow>
                                        <TableCell colSpan={6} className="p-0 bg-muted/30">
                                            <NodeResultsPanel detail={logDetails[log.id]} />
                                        </TableCell>
                                    </TableRow>
                                )}
                            </>
                        ))}
                    </TableBody>
                </Table>
            </div>

            {/* Pagination */}
            {total > PAGE_SIZE && (
                <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">
                        Showing {(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, total)} of {total}
                    </span>
                    <div className="flex items-center gap-2">
                        <span className="text-muted-foreground">
                            Page {page} of {totalPages}
                        </span>
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={page <= 1 || loading}
                            onClick={() => handlePageChange(page - 1)}
                        >
                            <ChevronLeft className="h-4 w-4" />
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={page >= totalPages || loading}
                            onClick={() => handlePageChange(page + 1)}
                        >
                            <ChevronRight className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}

function NodeResultsPanel({ detail }: { detail: AuditLogDetail }) {
    const [showAllFeatures, setShowAllFeatures] = useState(false);
    const results = detail.node_results || [];

    // Collect all features from all nodes
    const allFeatures = detail.features_extracted || [];
    const displayFeatures = showAllFeatures ? allFeatures : allFeatures.slice(0, 10);

    return (
        <div className="p-4 space-y-4">
            {/* Features Extracted Summary */}
            {allFeatures.length > 0 && (
                <div className="border rounded-lg p-3 bg-background">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium">Features Extracted ({allFeatures.length})</span>
                        {allFeatures.length > 10 && (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="text-xs h-6"
                                onClick={() => setShowAllFeatures(!showAllFeatures)}
                            >
                                {showAllFeatures ? "Show less" : `Show all`}
                            </Button>
                        )}
                    </div>
                    <div className="max-h-32 overflow-y-auto">
                        <div className="flex flex-wrap gap-1">
                            {displayFeatures.map((feat, idx) => (
                                <Badge key={idx} variant="secondary" className="text-xs">
                                    {feat}
                                </Badge>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            {/* Node Execution Details - All nodes in scrollable container */}
            <div>
                <div className="text-xs text-muted-foreground mb-2">
                    {results.length} nodes executed • {detail.nodes_skipped || 0} skipped
                </div>
                <div className="space-y-1 max-h-80 overflow-y-auto border rounded-lg p-2 bg-muted/20">
                    {results.map((node, idx) => (
                        <Collapsible key={idx}>
                            <CollapsibleTrigger asChild>
                                <div className="flex items-center justify-between p-2 bg-background rounded border text-xs cursor-pointer hover:bg-muted/50">
                                    <div className="flex items-center gap-2">
                                        {nodeStatusIcons[node.status] || <Clock className="h-3.5 w-3.5" />}
                                        <span className="font-mono">{node.node_name}</span>
                                        {node.error && (
                                            <AlertTriangle className="h-3 w-3 text-amber-500" />
                                        )}
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <span className="text-muted-foreground">
                                            {node.features_extracted?.length || 0} features
                                        </span>
                                        <span>{formatDuration(node.duration_ms)}</span>
                                        <ChevronDown className="h-3 w-3 text-muted-foreground" />
                                    </div>
                                </div>
                            </CollapsibleTrigger>
                            <CollapsibleContent>
                                <div className="ml-6 mt-1 p-2 bg-muted/30 rounded text-xs space-y-1">
                                    {node.features_extracted && node.features_extracted.length > 0 && (
                                        <div>
                                            <span className="text-muted-foreground">Features:</span>
                                            <div className="flex flex-wrap gap-1 mt-1">
                                                {node.features_extracted.map((f, i) => (
                                                    <Badge key={i} variant="outline" className="text-xs">
                                                        {f}
                                                    </Badge>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    {node.feature_values && Object.keys(node.feature_values).length > 0 && (
                                        <div className="mt-2">
                                            <span className="text-muted-foreground">Values:</span>
                                            <div className="grid grid-cols-2 gap-1 mt-1">
                                                {Object.entries(node.feature_values).slice(0, 6).map(([k, v]) => (
                                                    <div key={k} className="flex gap-1">
                                                        <span className="text-muted-foreground">{k}:</span>
                                                        <span className="font-mono truncate">
                                                            {typeof v === "object" ? JSON.stringify(v) : String(v)}
                                                        </span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    {node.resources_used && node.resources_used.length > 0 && (
                                        <div className="mt-2">
                                            <span className="text-muted-foreground">Resources Used:</span>
                                            <div className="flex flex-wrap gap-1 mt-1">
                                                {node.resources_used.map((r, i) => (
                                                    <Badge key={i} variant="secondary" className="text-xs bg-purple-100 dark:bg-purple-900/30">
                                                        {r}
                                                    </Badge>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    {node.error && (
                                        <div className="text-red-600 mt-1">
                                            Error: {node.error}
                                        </div>
                                    )}
                                    {node.skip_reason && (
                                        <div className="text-muted-foreground">
                                            Skipped: {node.skip_reason}
                                        </div>
                                    )}
                                </div>
                            </CollapsibleContent>
                        </Collapsible>
                    ))}
                </div>
            </div>
        </div>
    );
}
