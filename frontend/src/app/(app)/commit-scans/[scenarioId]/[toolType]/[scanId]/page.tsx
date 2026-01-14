"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
    ArrowLeft,
    CheckCircle2,
    GitCommit,
    Loader2,
    XCircle,
    Activity,
    Shield,
    BarChart3,
    RotateCcw,
    ExternalLink
} from "lucide-react";

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
    trainingScenariosApi,
    CommitScanRecord
} from "@/lib/api/training-scenarios";
import { formatDateTime } from "@/lib/utils";

function ScanStatusBadge({ status }: { status: string }) {
    const s = status.toLowerCase();

    if (s === "completed") {
        return (
            <Badge variant="outline" className="border-green-500 text-green-600 gap-1">
                <CheckCircle2 className="h-3 w-3" /> Completed
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
    if (s === "scanning" || s === "pending") {
        return (
            <Badge variant="secondary" className="gap-1">
                <Loader2 className="h-3 w-3 animate-spin" /> {s === "scanning" ? "Scanning" : "Pending"}
            </Badge>
        );
    }
    return <Badge variant="secondary">{status}</Badge>;
}

function formatDuration(startStr?: string, endStr?: string): string {
    if (!startStr || !endStr) return "—";
    const ms = new Date(endStr).getTime() - new Date(startStr).getTime();
    if (ms < 1000) return `${ms}ms`;
    const seconds = ms / 1000;
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
}

export default function ScanDetailPage() {
    const params = useParams();
    const router = useRouter();
    const scenarioId = params.scenarioId as string;
    const toolType = params.toolType as "trivy" | "sonarqube";
    const scanId = params.scanId as string;

    const [scan, setScan] = useState<CommitScanRecord | null>(null);
    const [loading, setLoading] = useState(true);
    const [retrying, setRetrying] = useState(false);

    const loadScan = async () => {
        setLoading(true);
        try {
            const data = await trainingScenariosApi.getCommitScanDetail(scenarioId, toolType, scanId);
            setScan(data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (scenarioId && scanId && toolType) {
            loadScan();
        }
    }, [scenarioId, scanId, toolType]);

    const handleRetry = async () => {
        if (!scan) return;
        setRetrying(true);
        try {
            await trainingScenariosApi.retryCommitScan(scenarioId, scan.commit_sha, scan.tool_type);
            setTimeout(loadScan, 1000);
        } catch (err) {
            console.error(err);
        } finally {
            setRetrying(false);
        }
    };

    if (loading) {
        return (
            <div className="flex min-h-[60vh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (!scan) {
        return (
            <div className="space-y-6">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => router.push(`/scenarios/${scenarioId}/builds/scans`)}
                    className="gap-2"
                >
                    <ArrowLeft className="h-4 w-4" />
                    Back to Scans
                </Button>
                <Card className="border-amber-200 bg-amber-50/60 dark:border-amber-800 dark:bg-amber-900/20">
                    <CardHeader>
                        <CardTitle className="text-amber-700 dark:text-amber-300">
                            Scan Not Found
                        </CardTitle>
                        <CardDescription>The requested scan could not be loaded.</CardDescription>
                    </CardHeader>
                </Card>
            </div>
        );
    }

    const toolIcon = toolType === "trivy"
        ? <Shield className="h-5 w-5 text-green-600" />
        : <BarChart3 className="h-5 w-5 text-blue-600" />;

    const toolName = toolType === "trivy" ? "Trivy Security" : "SonarQube Analysis";

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => router.push(`/scenarios/${scenarioId}/builds/scans`)}
                    className="gap-2"
                >
                    <ArrowLeft className="h-4 w-4" />
                    Back to Integration Scans
                </Button>
                <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                        {toolIcon}
                        <h1 className="text-2xl font-bold tracking-tight">
                            {toolName}
                        </h1>
                    </div>
                    <p className="text-muted-foreground text-sm flex items-center gap-2">
                        Commit <span className="font-mono">{scan.commit_sha.substring(0, 7)}</span>
                        {scan.builds_affected > 0 && ` • ${scan.builds_affected} builds affected`}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <ScanStatusBadge status={scan.status} />
                    {scan.status === "failed" && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleRetry}
                            disabled={retrying}
                        >
                            {retrying ? (
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            ) : (
                                <RotateCcw className="h-4 w-4 mr-2" />
                            )}
                            Retry Scan
                        </Button>
                    )}
                </div>
            </div>

            {/* Scan Information */}
            <Card>
                <CardHeader>
                    <CardTitle>Scan Information</CardTitle>
                    <CardDescription>Details about the scan execution</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Commit Info */}
                    <div className="rounded-lg border p-4 space-y-3">
                        <div className="flex items-center gap-2 text-sm">
                            <GitCommit className="h-4 w-4 text-muted-foreground" />
                            <span className="font-mono text-sm">{scan.commit_sha}</span>
                        </div>
                        {scan.error_message && (
                            <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 p-2 rounded">
                                Error: {scan.error_message}
                            </div>
                        )}
                    </div>

                    {/* Metadata Grid */}
                    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                        <div className="rounded-lg border p-4">
                            <p className="text-xs text-muted-foreground">Retry Count</p>
                            <p className="font-mono text-sm mt-1">
                                {scan.retry_count}
                            </p>
                        </div>
                        <div className="rounded-lg border p-4">
                            <p className="text-xs text-muted-foreground">Duration</p>
                            <p className="font-medium mt-1">
                                {formatDuration(scan.started_at, scan.completed_at)}
                            </p>
                        </div>
                        <div className="rounded-lg border p-4">
                            <p className="text-xs text-muted-foreground">Created At</p>
                            <p className="font-medium mt-1 text-sm">
                                {formatDateTime(scan.started_at)}
                            </p>
                        </div>
                        <div className="rounded-lg border p-4">
                            <p className="text-xs text-muted-foreground">Completed At</p>
                            <p className="font-medium mt-1 text-sm">
                                {formatDateTime(scan.completed_at)}
                            </p>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Builds Covered */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        Builds Covered
                    </CardTitle>
                    <CardDescription>
                        Builds associated with this commit
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {scan.builds && scan.builds.length > 0 ? (
                        <div className="rounded-md border">
                            <table className="w-full text-sm">
                                <thead className="bg-slate-50 dark:bg-slate-900/40">
                                    <tr className="border-b">
                                        <th className="px-4 py-3 text-left font-medium text-slate-500">Build ID</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y">
                                    {scan.builds.map((build) => (
                                        <tr key={build.id}>
                                            <td className="px-4 py-3 font-mono">{build.ci_run_id}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div className="text-center py-6 text-muted-foreground">
                            No builds info available.
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Scan Metrics */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Activity className="h-5 w-5" />
                        Scan Metrics
                    </CardTitle>
                    <CardDescription>Risk metrics collected by the tool</CardDescription>
                </CardHeader>
                <CardContent>
                    {scan.metrics && Object.keys(scan.metrics).length > 0 ? (
                        <div className="rounded-md border text-sm">
                            <table className="w-full">
                                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                    {Object.entries(scan.metrics).map(([key, value]) => (
                                        <tr key={key}>
                                            <td className="px-4 py-3 font-medium text-slate-500 w-[50%]">{key}</td>
                                            <td className="px-4 py-3 text-right font-mono text-foreground">
                                                {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div className="rounded-lg border border-slate-200 bg-slate-50 p-6 text-center dark:border-slate-800 dark:bg-slate-900/50">
                            <p className="text-muted-foreground">No metrics collected.</p>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
