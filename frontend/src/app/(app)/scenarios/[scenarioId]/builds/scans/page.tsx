"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useSearchParams, useRouter, usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn, formatDateTime } from "@/lib/utils";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useSSE } from "@/contexts/sse-context";
import {
    CheckCircle2,
    ChevronDown,
    ChevronRight,
    ChevronLeft,
    ChevronRight as ChevronNext, // Renamed to avoid conflict
    Loader2,
    XCircle,
    Clock,
    RefreshCw,
    RotateCcw,
    Shield,
    BarChart3,
    FileJson,
    Activity
} from "lucide-react";
import { useDebouncedCallback } from "@/hooks/use-debounced-callback";

import {
    trainingScenariosApi,
    CommitScanRecord,
    PaginatedResponse
} from "@/lib/api/training-scenarios";
import { TablePagination } from "@/components/builds";

const ITEMS_PER_PAGE = 10;

function formatDuration(startedAt: string | undefined, completedAt: string | undefined): string {
    if (!startedAt || !completedAt) return "-";
    const diff = new Date(completedAt).getTime() - new Date(startedAt).getTime();
    if (diff < 1000) return `${diff}ms`;
    return `${(diff / 1000).toFixed(1)}s`;
}

export default function ScansPage() {
    const params = useParams<{ scenarioId: string }>();
    const scenarioId = params.scenarioId;
    const searchParams = useSearchParams();
    const router = useRouter();
    const pathname = usePathname();
    const { subscribe } = useSSE();

    const activeTab = searchParams.get("tab") || "sonarqube";

    const [trivyData, setTrivyData] = useState<PaginatedResponse<CommitScanRecord> | null>(null);
    const [sonarData, setSonarData] = useState<PaginatedResponse<CommitScanRecord> | null>(null);
    const [loading, setLoading] = useState(true);
    const [retrying, setRetrying] = useState<string | null>(null);
    const [sonarPage, setSonarPage] = useState(1);
    const [trivyPage, setTrivyPage] = useState(1);
    // Scan progress tracking
    const [scanProgress, setScanProgress] = useState<{
        scans_total: number;
        scans_completed: number;
        scans_failed: number;
        scan_extraction_completed: boolean;
    } | null>(null);
    const pollingRef = useRef<NodeJS.Timeout | null>(null);

    // Expandable row state
    const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

    const toggleRow = (id: string) => {
        const newExpanded = new Set(expandedRows);
        if (newExpanded.has(id)) {
            newExpanded.delete(id);
        } else {
            newExpanded.add(id);
        }
        setExpandedRows(newExpanded);
    };

    const handleTabChange = (value: string) => {
        const params = new URLSearchParams(searchParams.toString());
        params.set("tab", value);
        router.push(`${pathname}?${params.toString()}`);
    };

    const fetchScans = useCallback(async (silent = false) => {
        if (!silent) setLoading(true);

        try {
            let currentItems: CommitScanRecord[] = [];

            if (activeTab === "trivy") {
                const response = await trainingScenariosApi.getCommitScans(scenarioId, {
                    tool_type: "trivy",
                    skip: (trivyPage - 1) * ITEMS_PER_PAGE,
                    limit: ITEMS_PER_PAGE,
                });
                if (response.trivy) {
                    setTrivyData(response.trivy);
                    currentItems = response.trivy.items;
                }
            } else {
                const response = await trainingScenariosApi.getCommitScans(scenarioId, {
                    tool_type: "sonarqube",
                    skip: (sonarPage - 1) * ITEMS_PER_PAGE,
                    limit: ITEMS_PER_PAGE,
                });
                if (response.sonarqube) {
                    setSonarData(response.sonarqube);
                    currentItems = response.sonarqube.items;
                }
            }

            // Check for running scans for polling
            const hasRunning = currentItems.some(
                (s) => s.status === "scanning" || s.status === "pending"
            );

            if (hasRunning && !pollingRef.current) {
                pollingRef.current = setInterval(() => fetchScans(true), 5000);
            } else if (!hasRunning && pollingRef.current) {
                clearInterval(pollingRef.current);
                pollingRef.current = null;
            }
        } catch (err) {
            console.error("Failed to fetch scans:", err);
        } finally {
            if (!silent) setLoading(false);
        }
    }, [scenarioId, trivyPage, sonarPage, activeTab]);

    // Fetch scenario to initialize scan progress
    const fetchScenario = useCallback(async () => {
        try {
            const scenario = await trainingScenariosApi.get(scenarioId);
            setScanProgress({
                scans_total: scenario.scans_total ?? 0,
                scans_completed: scenario.scans_completed ?? 0,
                scans_failed: scenario.scans_failed ?? 0,
                scan_extraction_completed: scenario.scan_extraction_completed ?? false,
            });
        } catch (err) {
            console.error("Failed to fetch scenario:", err);
        }
    }, [scenarioId]);

    useEffect(() => {
        if (scenarioId) {
            fetchScenario();
            fetchScans();
        }
        return () => {
            if (pollingRef.current) clearInterval(pollingRef.current);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [scenarioId, trivyPage, sonarPage, activeTab]);

    // Debounced refetch for scan updates
    const debouncedFetchScans = useDebouncedCallback(
        () => fetchScans(true),
        500,
        { leading: true, trailing: true }
    );

    // Helper to merge a single scan update into local state
    const mergeScanUpdate = (payload: {
        scan_id: string;
        commit_sha: string;
        tool_type: string;
        status: "completed" | "failed" | "pending" | "scanning";
        error?: string;
        metrics?: Record<string, any>;
    }) => {
        const updateScanInList = (items: CommitScanRecord[] | undefined) => {
            if (!items) return items;
            return items.map((scan) =>
                scan.id === payload.scan_id
                    ? {
                        ...scan,
                        status: payload.status as CommitScanRecord["status"],
                        error_message: payload.error || scan.error_message,
                        metrics: payload.metrics || scan.metrics,
                    }
                    : scan
            );
        };

        if (payload.tool_type === "trivy") {
            setTrivyData((prev) =>
                prev ? { ...prev, items: updateScanInList(prev.items) || [] } : prev
            );
        } else if (payload.tool_type === "sonarqube") {
            setSonarData((prev) =>
                prev ? { ...prev, items: updateScanInList(prev.items) || [] } : prev
            );
        }
    };

    // Listen for real-time SCENARIO.SCAN.UPDATED events via SSE - merge delta
    useEffect(() => {
        const unsubscribeScan = subscribe("SCENARIO.SCAN.UPDATED", (payload: {
            scenario_id?: string;
            scan_id: string;
            commit_sha: string;
            tool_type: string;
            status: "completed" | "failed" | "pending" | "scanning";
            error?: string;
            metrics?: Record<string, any>;
        }) => {
            if (payload.scenario_id === scenarioId) {
                // Merge delta into local state instead of full refetch
                mergeScanUpdate(payload as any);

                // If scan completed or failed, update progress counts
                if (payload.status === "completed" || payload.status === "failed") {
                    setScanProgress((prev) => {
                        if (!prev) return prev;
                        return {
                            ...prev,
                            scans_completed:
                                payload.status === "completed"
                                    ? prev.scans_completed + 1
                                    : prev.scans_completed,
                            scans_failed:
                                payload.status === "failed"
                                    ? prev.scans_failed + 1
                                    : prev.scans_failed,
                        };
                    });
                }
            }
        });

        return () => {
            unsubscribeScan();
        };
    }, [subscribe, scenarioId]);

    // Subscribe to SSE for scenario scan progress - merge stats directly
    useEffect(() => {
        const unsubscribeScenario = subscribe("SCENARIO.UPDATED", (data: any) => {
            if (data.scenario_id === scenarioId) {
                // Merge scan progress stats directly
                setScanProgress({
                    scans_total: data.scans_total ?? 0,
                    scans_completed: data.scans_completed ?? 0,
                    scans_failed: data.scans_failed ?? 0,
                    scan_extraction_completed: data.scan_extraction_completed ?? false,
                });
            }
        });

        return () => {
            unsubscribeScenario();
        };
    }, [subscribe, scenarioId]);

    // Listen for SCAN_ERROR events - merge error into local state
    useEffect(() => {
        const handleScanError = (event: CustomEvent<{
            scenario_id?: string;
            scan_id: string;
            commit_sha: string;
            tool_type: string;
            error: string;
            retry_count: number;
        }>) => {
            if (event.detail.scenario_id === scenarioId) {
                mergeScanUpdate({
                    ...event.detail,
                    status: "failed",
                });
            }
        };

        window.addEventListener("SCAN_ERROR", handleScanError as EventListener);
        return () => {
            window.removeEventListener("SCAN_ERROR", handleScanError as EventListener);
        };
    }, [scenarioId]);

    const handleRetry = async (commitSha: string, toolType: "trivy" | "sonarqube") => {
        setRetrying(`${toolType}-${commitSha}`);
        try {
            await trainingScenariosApi.retryCommitScan(scenarioId, commitSha, toolType);
            await fetchScans(true);
        } catch (err) {
            console.error("Retry failed:", err);
        } finally {
            setRetrying(null);
        }
    };

    // Calculate failed counts
    const trivyFailedCount = trivyData?.items?.filter(s => s.status === "failed").length || 0;
    const sonarFailedCount = sonarData?.items?.filter(s => s.status === "failed").length || 0;

    // Tool-specific retry state
    const [retryingTool, setRetryingTool] = useState<"trivy" | "sonarqube" | null>(null);

    // Retry failed scans for a specific tool
    const handleRetryTool = async (toolType: "trivy" | "sonarqube") => {
        setRetryingTool(toolType);
        try {
            await trainingScenariosApi.retryFailedScans(scenarioId, toolType);
            await fetchScans(true);
        } catch (err) {
            console.error(`Retry ${toolType} failed:`, err);
        } finally {
            setRetryingTool(null);
        }
    };

    const renderStatus = (status: string) => {
        const config: Record<string, { icon: React.ReactNode; color: string }> = {
            completed: { icon: <CheckCircle2 className="h-3 w-3" />, color: "text-green-600 border-green-600/20 bg-green-50" },
            failed: { icon: <XCircle className="h-3 w-3" />, color: "text-destructive border-destructive/20 bg-destructive/10" },
            scanning: { icon: <Loader2 className="h-3 w-3 animate-spin" />, color: "text-secondary-foreground" },
            pending: { icon: <Clock className="h-3 w-3" />, color: "text-muted-foreground" },
        };
        const c = config[status] || config.pending;
        return (
            <Badge variant="outline" className={cn("font-medium", c.color)}>
                <span className="flex items-center gap-1">{c.icon} {status}</span>
            </Badge>
        );
    };

    const renderScanTable = (
        scanData: PaginatedResponse<CommitScanRecord> | null,
        toolType: "trivy" | "sonarqube",
        currentPage: number,
        setPage: (page: number) => void
    ) => {
        if (loading) {
            return (
                <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-5 w-5 animate-spin mr-2" />
                    <span className="text-sm text-muted-foreground">Loading scans...</span>
                </div>
            );
        }

        if (!scanData || scanData.items.length === 0) {
            return (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                    <div className="p-3 rounded-full bg-muted mb-3">
                        {toolType === "trivy" ? (
                            <Shield className="h-6 w-6 text-muted-foreground" />
                        ) : (
                            <BarChart3 className="h-6 w-6 text-muted-foreground" />
                        )}
                    </div>
                    <p className="text-muted-foreground font-medium">No {toolType === "trivy" ? "Trivy" : "SonarQube"} scans yet</p>
                    <p className="text-xs text-muted-foreground mt-1">
                        Scans will be dispatched when you click &quot;Start Processing&quot;.
                    </p>
                </div>
            );
        }

        const { items, total } = scanData;
        const totalPages = Math.ceil(total / ITEMS_PER_PAGE);

        const stats = {
            total: total,
            completed: items.filter(s => s.status === "completed").length,
            failed: items.filter(s => s.status === "failed").length,
            pending: items.filter(s => s.status === "pending" || s.status === "scanning").length,
        };

        return (
            <div className="space-y-4">
                <div className="flex gap-2 text-xs text-muted-foreground mb-2">
                    <span>{stats.total} total</span>
                    <span>•</span>
                    <span className="text-green-600">{stats.completed} completed (page)</span>
                    {stats.failed > 0 && <><span>•</span><span className="text-red-600">{stats.failed} failed (page)</span></>}
                    {stats.pending > 0 && <><span>•</span><span>{stats.pending} pending (page)</span></>}
                </div>
                <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
                    <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                        <thead className="bg-slate-50 dark:bg-slate-900/40">
                            <tr>
                                <th className="px-3 py-3 w-[40px]"></th>
                                <th className="px-3 py-3 text-left font-medium text-slate-500 w-[80px]">Commit</th>
                                <th className="px-3 py-3 text-left font-medium text-slate-500 w-[200px]">Repository</th>
                                <th className="px-3 py-3 text-left font-medium text-slate-500 w-[100px]">Status</th>
                                <th className="px-3 py-3 text-left font-medium text-slate-500 w-[60px]">Builds</th>
                                <th className="px-3 py-3 text-left font-medium text-slate-500 w-[80px]">Duration</th>
                                <th className="px-3 py-3 text-right font-medium text-slate-500 w-[130px]">Completed At</th>
                                <th className="px-3 py-3 w-12"></th>
                            </tr>
                        </thead>
                        {items.map((scan) => {
                            const isExpanded = expandedRows.has(scan.id);
                            const hasDetails = (scan.metrics && Object.keys(scan.metrics).length > 0) ||
                                (scan.scan_config && Object.keys(scan.scan_config).length > 0);

                            return (
                                <Collapsible
                                    key={scan.id}
                                    asChild
                                    open={isExpanded}
                                    onOpenChange={() => toggleRow(scan.id)}
                                >
                                    <tbody className="divide-y divide-slate-200 dark:divide-slate-800 hover:bg-slate-50 dark:hover:bg-slate-900/40 transition-colors">
                                        <tr
                                            className="group cursor-pointer"
                                            onClick={(e) => {
                                                // Don't navigate if clicking the toggle button or retry button
                                                if ((e.target as HTMLElement).closest('button')) return;
                                                router.push(`/commit-scans/${scenarioId}/${toolType}/${scan.id}`);
                                            }}
                                        >
                                            <td className="px-3 py-3">
                                                {hasDetails && (
                                                    <CollapsibleTrigger asChild>
                                                        <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
                                                            {isExpanded ? (
                                                                <ChevronDown className="h-4 w-4" />
                                                            ) : (
                                                                <ChevronRight className="h-4 w-4" />
                                                            )}
                                                        </Button>
                                                    </CollapsibleTrigger>
                                                )}
                                            </td>
                                            <td className="px-3 py-3 font-mono text-xs">
                                                {scan.commit_sha.substring(0, 7)}
                                            </td>
                                            <td className="px-3 py-3 text-xs text-muted-foreground truncate max-w-[200px]" title={scan.repo_full_name}>
                                                {scan.repo_full_name}
                                            </td>
                                            <td className="px-3 py-3">{renderStatus(scan.status)}</td>
                                            <td className="px-3 py-3 text-center">{scan.builds_affected}</td>
                                            <td className="px-3 py-3 text-xs">
                                                {formatDuration(scan.started_at, scan.completed_at)}
                                            </td>
                                            <td className="px-3 py-3 text-xs text-right text-muted-foreground">
                                                {formatDateTime(scan.completed_at)}
                                            </td>
                                            <td className="px-3 py-3">
                                                {scan.status === "failed" && (
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        disabled={retrying === `${toolType}-${scan.commit_sha}`}
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            handleRetry(scan.commit_sha, toolType);
                                                        }}
                                                        className="h-8 w-8 p-0"
                                                    >
                                                        {retrying === `${toolType}-${scan.commit_sha}` ? (
                                                            <Loader2 className="h-3 w-3 animate-spin" />
                                                        ) : (
                                                            <RotateCcw className="h-3 w-3" />
                                                        )}
                                                    </Button>
                                                )}
                                            </td>
                                        </tr>
                                        <CollapsibleContent asChild>
                                            <tr>
                                                <td colSpan={8} className="p-0 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/20">
                                                    <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-6">
                                                        {/* Metrics Panel */}
                                                        {scan.metrics && (
                                                            <div className="space-y-2">
                                                                <div className="flex items-center gap-2 mb-2">
                                                                    <Activity className="h-4 w-4 text-muted-foreground" />
                                                                    <h4 className="text-sm font-semibold">Scan Metrics</h4>
                                                                </div>
                                                                <div className="bg-white dark:bg-slate-950 rounded-md border text-xs">
                                                                    <table className="w-full">
                                                                        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                                                            {Object.entries(scan.metrics).map(([key, value]) => (
                                                                                <tr key={key}>
                                                                                    <td className="px-3 py-2 font-medium text-slate-500">{key}</td>
                                                                                    <td className="px-3 py-2 text-right font-mono">
                                                                                        {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                                                                                    </td>
                                                                                </tr>
                                                                            ))}
                                                                        </tbody>
                                                                    </table>
                                                                </div>
                                                            </div>
                                                        )}

                                                        {/* Config Panel */}
                                                        {scan.scan_config && (
                                                            <div className="space-y-2">
                                                                <div className="flex items-center gap-2 mb-2">
                                                                    <FileJson className="h-4 w-4 text-muted-foreground" />
                                                                    <h4 className="text-sm font-semibold">Scan Configuration</h4>
                                                                </div>
                                                                <div className="bg-white dark:bg-slate-950 rounded-md border p-3 text-xs font-mono overflow-auto max-h-[200px]">
                                                                    <pre>{JSON.stringify(scan.scan_config, null, 2)}</pre>
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                </td>
                                            </tr>
                                        </CollapsibleContent>
                                    </tbody>
                                </Collapsible>
                            );
                        })}
                    </table>
                </div>
                <TablePagination
                    currentPage={currentPage}
                    totalPages={totalPages}
                    totalItems={total}
                    pageSize={ITEMS_PER_PAGE}
                    onPageChange={setPage}
                    isLoading={loading}
                />
            </div>
        );
    };

    const hasTrivyScans = trivyData && trivyData.total > 0;
    const hasSonarScans = sonarData && sonarData.total > 0;

    return (
        <div className="space-y-4">
            <Card>
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="text-base">Integration Scans</CardTitle>
                            <CardDescription>
                                SonarQube and Trivy security scans
                            </CardDescription>
                        </div>
                        <div className="flex items-center gap-2">
                            <Button variant="outline" size="sm" onClick={() => fetchScans()}>
                                <RefreshCw className="h-4 w-4 mr-2" />
                                Refresh
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleRetryTool(activeTab as "trivy" | "sonarqube")}
                                disabled={retryingTool !== null || (scanProgress?.scans_failed || 0) === 0}
                                className={cn(
                                    "transition-colors",
                                    (scanProgress?.scans_failed || 0) > 0
                                        ? "text-amber-600 border-amber-300 hover:bg-amber-50"
                                        : "text-muted-foreground border-slate-200"
                                )}
                            >
                                <RefreshCw className={cn("h-4 w-4 mr-2", retryingTool && "animate-spin")} />
                                Retry Failed Scans
                            </Button>
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    <Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
                        <TabsList className="mb-4">
                            <TabsTrigger value="sonarqube" className="flex items-center gap-2">
                                <BarChart3 className="h-4 w-4 text-blue-600" />
                                SonarQube
                            </TabsTrigger>
                            <TabsTrigger value="trivy" className="flex items-center gap-2">
                                <Shield className="h-4 w-4 text-green-600" />
                                Trivy
                            </TabsTrigger>
                        </TabsList>

                        <TabsContent value="sonarqube">
                            {renderScanTable(sonarData, "sonarqube", sonarPage, setSonarPage)}
                        </TabsContent>
                        <TabsContent value="trivy">
                            {renderScanTable(trivyData, "trivy", trivyPage, setTrivyPage)}
                        </TabsContent>
                    </Tabs>
                </CardContent>
            </Card>
        </div>
    );
}
