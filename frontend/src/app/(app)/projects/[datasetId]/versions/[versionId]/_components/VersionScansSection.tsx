"use client";

import { useState, useCallback, useEffect, useRef } from "react";
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
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from "@/components/ui/accordion";
import {
    CheckCircle2,
    XCircle,
    Clock,
    Loader2,
    RefreshCw,
    RotateCcw,
    Shield,
    AlertTriangle,
    ChevronDown,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface CommitScan {
    id: string;
    commit_sha: string;
    repo_full_name: string;
    status: string;
    error_message: string | null;
    builds_affected: number;
    retry_count: number;
    started_at: string | null;
    completed_at: string | null;
}

interface CommitScansResponse {
    trivy: CommitScan[];
    sonarqube: CommitScan[];
}

interface VersionScansSectionProps {
    datasetId: string;
    versionId: string;
}

function formatDuration(startedAt: string | null, completedAt: string | null): string {
    if (!startedAt || !completedAt) return "-";
    const diff = new Date(completedAt).getTime() - new Date(startedAt).getTime();
    if (diff < 1000) return `${diff}ms`;
    return `${(diff / 1000).toFixed(1)}s`;
}

export function VersionScansSection({ datasetId, versionId }: VersionScansSectionProps) {
    const [scans, setScans] = useState<CommitScansResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [retrying, setRetrying] = useState<string | null>(null);
    const pollingRef = useRef<NodeJS.Timeout | null>(null);

    const fetchScans = useCallback(async (silent = false) => {
        if (!silent) setLoading(true);
        try {
            const res = await fetch(
                `${API_BASE}/datasets/${datasetId}/versions/${versionId}/commit-scans`,
                { credentials: "include" }
            );
            if (res.ok) {
                const data = await res.json();
                setScans(data);

                // Continue polling if any scans are running
                const hasRunning = [...(data.trivy || []), ...(data.sonarqube || [])]
                    .some((s: CommitScan) => s.status === "scanning" || s.status === "pending");
                if (hasRunning && !pollingRef.current) {
                    pollingRef.current = setInterval(() => fetchScans(true), 5000);
                } else if (!hasRunning && pollingRef.current) {
                    clearInterval(pollingRef.current);
                    pollingRef.current = null;
                }
            }
        } catch (err) {
            console.error("Failed to fetch scans:", err);
        } finally {
            if (!silent) setLoading(false);
        }
    }, [datasetId, versionId]);

    useEffect(() => {
        if (versionId) fetchScans();
        return () => {
            if (pollingRef.current) clearInterval(pollingRef.current);
        };
    }, [versionId, fetchScans]);

    const handleRetry = async (commitSha: string, toolType: string) => {
        setRetrying(`${toolType}-${commitSha}`);
        try {
            await fetch(
                `${API_BASE}/datasets/${datasetId}/versions/${versionId}/commit-scans/${commitSha}/retry?tool_type=${toolType}`,
                { method: "POST", credentials: "include" }
            );
            await fetchScans();
        } catch (err) {
            console.error("Retry failed:", err);
        } finally {
            setRetrying(null);
        }
    };

    const renderStatus = (status: string) => {
        const config: Record<string, { icon: React.ReactNode; variant: "default" | "destructive" | "secondary" | "outline" }> = {
            completed: { icon: <CheckCircle2 className="h-3 w-3" />, variant: "default" },
            failed: { icon: <XCircle className="h-3 w-3" />, variant: "destructive" },
            scanning: { icon: <Loader2 className="h-3 w-3 animate-spin" />, variant: "secondary" },
            pending: { icon: <Clock className="h-3 w-3" />, variant: "outline" },
        };
        const c = config[status] || config.pending;
        return (
            <Badge variant={c.variant}>
                <span className="flex items-center gap-1">{c.icon} {status}</span>
            </Badge>
        );
    };

    const renderScanTable = (scanList: CommitScan[], toolType: string) => {
        if (!scanList || scanList.length === 0) {
            return <p className="text-sm text-muted-foreground py-4">No scans</p>;
        }

        const stats = {
            total: scanList.length,
            completed: scanList.filter(s => s.status === "completed").length,
            failed: scanList.filter(s => s.status === "failed").length,
            pending: scanList.filter(s => s.status === "pending" || s.status === "scanning").length,
        };

        return (
            <div className="space-y-2">
                <div className="flex gap-2 text-xs text-muted-foreground mb-2">
                    <span>{stats.total} total</span>
                    <span>•</span>
                    <span className="text-green-600">{stats.completed} completed</span>
                    {stats.failed > 0 && <><span>•</span><span className="text-red-600">{stats.failed} failed</span></>}
                    {stats.pending > 0 && <><span>•</span><span>{stats.pending} pending</span></>}
                </div>
                <div className="border rounded-lg overflow-hidden max-h-[200px] overflow-y-auto">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Commit</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Builds</TableHead>
                                <TableHead>Duration</TableHead>
                                <TableHead className="w-16"></TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {scanList.slice(0, 10).map((scan) => (
                                <TableRow key={scan.id}>
                                    <TableCell className="font-mono text-xs">
                                        {scan.commit_sha.substring(0, 7)}
                                    </TableCell>
                                    <TableCell>{renderStatus(scan.status)}</TableCell>
                                    <TableCell>{scan.builds_affected}</TableCell>
                                    <TableCell className="text-xs">
                                        {formatDuration(scan.started_at, scan.completed_at)}
                                    </TableCell>
                                    <TableCell>
                                        {scan.status === "failed" && (
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                disabled={retrying === `${toolType}-${scan.commit_sha}`}
                                                onClick={() => handleRetry(scan.commit_sha, toolType)}
                                            >
                                                {retrying === `${toolType}-${scan.commit_sha}` ? (
                                                    <Loader2 className="h-3 w-3 animate-spin" />
                                                ) : (
                                                    <RotateCcw className="h-3 w-3" />
                                                )}
                                            </Button>
                                        )}
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
                {scanList.length > 10 && (
                    <p className="text-xs text-muted-foreground text-center">
                        Showing 10 of {scanList.length} scans
                    </p>
                )}
            </div>
        );
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin mr-2" />
                <span className="text-muted-foreground">Loading scans...</span>
            </div>
        );
    }

    if (!scans || (scans.sonarqube.length === 0 && scans.trivy.length === 0)) {
        return (
            <div className="text-center py-8 text-muted-foreground">
                No code scans for this version
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex justify-end">
                <Button variant="outline" size="sm" onClick={() => fetchScans()}>
                    <RefreshCw className="h-4 w-4 mr-1" />
                    Refresh
                </Button>
            </div>

            <Accordion type="multiple" defaultValue={["sonarqube", "trivy"]}>
                {scans.sonarqube.length > 0 && (
                    <AccordionItem value="sonarqube">
                        <AccordionTrigger className="text-sm font-medium">
                            <div className="flex items-center gap-2">
                                <Shield className="h-4 w-4 text-blue-600" />
                                SonarQube ({scans.sonarqube.length})
                            </div>
                        </AccordionTrigger>
                        <AccordionContent>
                            {renderScanTable(scans.sonarqube, "sonarqube")}
                        </AccordionContent>
                    </AccordionItem>
                )}
                {scans.trivy.length > 0 && (
                    <AccordionItem value="trivy">
                        <AccordionTrigger className="text-sm font-medium">
                            <div className="flex items-center gap-2">
                                <AlertTriangle className="h-4 w-4 text-amber-600" />
                                Trivy ({scans.trivy.length})
                            </div>
                        </AccordionTrigger>
                        <AccordionContent>
                            {renderScanTable(scans.trivy, "trivy")}
                        </AccordionContent>
                    </AccordionItem>
                )}
            </Accordion>
        </div>
    );
}
