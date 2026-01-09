"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
    AlertTriangle,
    ArrowLeft,
    CheckCircle2,
    Clock,
    ExternalLink,
    GitCommit,
    Loader2,
    Search,
    XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { buildApi } from "@/lib/api";
import type { BuildDetail } from "@/types";

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
    return (
        <Badge variant="secondary" className="gap-1">
            <Clock className="h-3 w-3" /> {status}
        </Badge>
    );
}

function ExtractionStatusBadge({ status }: { status: string }) {
    const s = status.toLowerCase();
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
                <AlertTriangle className="h-3 w-3" /> Partial
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
                <Loader2 className="h-3 w-3 animate-spin" /> Pending
            </Badge>
        );
    }
    return <Badge variant="secondary">{status}</Badge>;
}

function formatDateTime(value?: string | null): string {
    if (!value) return "—";
    try {
        return new Intl.DateTimeFormat(undefined, {
            dateStyle: "medium",
            timeStyle: "short",
        }).format(new Date(value));
    } catch {
        return value;
    }
}

function formatDuration(seconds?: number | null): string {
    if (!seconds) return "—";
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
}

function RiskBadge({ level, confidence }: { level: string; confidence?: number }) {
    const l = level.toUpperCase();
    const confLabel = confidence ? ` (${(confidence * 100).toFixed(0)}%)` : "";

    if (l === "LOW") {
        return (
            <Badge variant="outline" className="border-green-500 text-green-600 gap-1">
                <CheckCircle2 className="h-3 w-3" /> Low Risk{confLabel}
            </Badge>
        );
    }
    if (l === "MEDIUM") {
        return (
            <Badge variant="outline" className="border-amber-500 text-amber-600 gap-1">
                <AlertTriangle className="h-3 w-3" /> Medium Risk{confLabel}
            </Badge>
        );
    }
    if (l === "HIGH") {
        return (
            <Badge variant="destructive" className="gap-1">
                <XCircle className="h-3 w-3" /> High Risk{confLabel}
            </Badge>
        );
    }
    return <Badge variant="secondary">{level}</Badge>;
}

export default function UserBuildDetailPage() {
    const params = useParams();
    const router = useRouter();
    const repoId = params.id as string;
    const buildId = params.buildId as string;

    const [build, setBuild] = useState<BuildDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [featureSearch, setFeatureSearch] = useState("");

    useEffect(() => {
        const loadBuild = async () => {
            setLoading(true);
            setError(null);
            try {
                const data = await buildApi.getById(repoId, buildId);
                setBuild(data);
            } catch (err) {
                console.error(err);
                setError("Unable to load build details.");
            } finally {
                setLoading(false);
            }
        };
        loadBuild();
    }, [repoId, buildId]);

    const featureEntries = useMemo(() => {
        if (!build?.features) return [];
        return Object.entries(build.features)
            .sort(([a], [b]) => a.localeCompare(b))
            .filter(([key]) =>
                featureSearch === "" ||
                key.toLowerCase().includes(featureSearch.toLowerCase())
            );
    }, [build?.features, featureSearch]);

    if (loading) {
        return (
            <div className="flex min-h-[60vh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (error || !build) {
        return (
            <div className="space-y-6">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => router.push(`/repos/${repoId}/builds`)}
                    className="gap-2"
                >
                    <ArrowLeft className="h-4 w-4" />
                    Back to Builds
                </Button>
                <Card className="border-red-200 bg-red-50/60 dark:border-red-800 dark:bg-red-900/20">
                    <CardHeader>
                        <CardTitle className="text-red-700 dark:text-red-300">Error</CardTitle>
                        <CardDescription>{error || "Build not found"}</CardDescription>
                    </CardHeader>
                </Card>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => router.push(`/my-repos/${repoId}/builds`)}
                    className="gap-2"
                >
                    <ArrowLeft className="h-4 w-4" />
                    Back to Builds
                </Button>
                <div className="flex-1">
                    <h1 className="text-2xl font-bold tracking-tight">
                        Build #{build.build_number || "—"}
                    </h1>
                    <p className="text-muted-foreground text-sm">
                        {build.commit_sha.substring(0, 7)} on {build.branch}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <StatusBadge status={build.conclusion} />
                    {build.web_url && (
                        <a
                            href={build.web_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1 text-sm text-blue-600 hover:underline"
                        >
                            <ExternalLink className="h-4 w-4" />
                            View on CI
                        </a>
                    )}
                </div>
            </div>

            {/* Build Info */}
            <Card>
                <CardHeader>
                    <CardTitle>Build Information</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="rounded-lg border p-4 space-y-2">
                        <div className="flex items-center gap-2 text-sm">
                            <GitCommit className="h-4 w-4 text-muted-foreground" />
                            <span className="font-mono text-sm">{build.commit_sha}</span>
                            <Badge variant="secondary">{build.branch}</Badge>
                        </div>
                        {build.commit_author && (
                            <p className="text-sm text-muted-foreground">
                                Author: <span className="text-foreground">{build.commit_author}</span>
                            </p>
                        )}
                        {build.commit_message && (
                            <p className="text-sm text-muted-foreground">{build.commit_message}</p>
                        )}
                    </div>

                    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                        <div className="rounded-lg border p-4">
                            <p className="text-xs text-muted-foreground">Duration</p>
                            <p className="font-medium mt-1">{formatDuration(build.duration_seconds)}</p>
                        </div>
                        <div className="rounded-lg border p-4">
                            <p className="text-xs text-muted-foreground">Created</p>
                            <p className="font-medium mt-1 text-sm">{formatDateTime(build.created_at)}</p>
                        </div>
                        <div className="rounded-lg border p-4">
                            <p className="text-xs text-muted-foreground">Completed</p>
                            <p className="font-medium mt-1 text-sm">{formatDateTime(build.completed_at)}</p>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Risk Prediction */}
            {build.has_training_data && (build.predicted_label || build.prediction_status || build.prediction_error) && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            Risk Prediction
                            <div className="flex gap-2">
                                {build.predicted_label && (
                                    <RiskBadge
                                        level={build.predicted_label}
                                        confidence={build.prediction_confidence ?? undefined}
                                    />
                                )}
                                {build.prediction_status && build.prediction_status !== 'completed' && (
                                    <Badge
                                        variant={build.prediction_status === 'failed' ? 'destructive' : 'outline'}
                                        className="capitalize"
                                    >
                                        {build.prediction_status}
                                    </Badge>
                                )}
                            </div>
                        </CardTitle>
                        <CardDescription>ML model prediction for this build</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {build.prediction_error ? (
                            <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900/50 dark:bg-red-950/50">
                                <div className="flex items-start gap-3">
                                    <div className="p-1 bg-red-100 dark:bg-red-900/40 rounded-full shrink-0">
                                        <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
                                    </div>
                                    <div className="space-y-1">
                                        <p className="font-medium text-sm text-red-900 dark:text-red-200">Prediction Failed</p>
                                        <p className="text-sm text-red-800/90 dark:text-red-300/90 leading-relaxed font-mono text-xs">
                                            {build.prediction_error}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        ) : !build.predicted_label ? (
                            <div className="rounded-lg border border-slate-200 bg-slate-50 p-6 text-center dark:border-slate-800 dark:bg-slate-900/50">
                                <p className="text-muted-foreground">Prediction pending or in progress...</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                                <div className="rounded-lg border p-4">
                                    <p className="text-xs text-muted-foreground">Risk Level</p>
                                    <p className="font-medium mt-1">{build.predicted_label}</p>
                                </div>
                                <div className="rounded-lg border p-4">
                                    <p className="text-xs text-muted-foreground">Confidence</p>
                                    <p className="font-medium mt-1">
                                        {build.prediction_confidence
                                            ? `${(build.prediction_confidence * 100).toFixed(1)}%`
                                            : "—"}
                                    </p>
                                </div>
                                <div className="rounded-lg border p-4">
                                    <p className="text-xs text-muted-foreground">Uncertainty</p>
                                    <p className="font-medium mt-1">
                                        {build.prediction_uncertainty
                                            ? build.prediction_uncertainty.toFixed(3)
                                            : "—"}
                                    </p>
                                </div>
                                <div className="rounded-lg border p-4">
                                    <p className="text-xs text-muted-foreground">Predicted At</p>
                                    <p className="font-medium mt-1 text-sm">{formatDateTime(build.predicted_at)}</p>
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Extracted Features */}
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="flex items-center gap-2">
                                Extracted Features
                                {build.has_training_data && (
                                    <ExtractionStatusBadge status={build.extraction_status || "unknown"} />
                                )}
                            </CardTitle>
                            <CardDescription>{build.feature_count} features extracted</CardDescription>
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    {!build.has_training_data ? (
                        <div className="rounded-lg border bg-slate-50 p-6 text-center dark:bg-slate-900/50">
                            <p className="text-muted-foreground">Feature extraction not started yet.</p>
                        </div>
                    ) : build.extraction_status === "failed" ? (
                        <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-900/20">
                            <p className="text-sm text-red-700 dark:text-red-300">
                                Extraction failed: {build.extraction_error || "Unknown error"}
                            </p>
                        </div>
                    ) : build.extraction_status === "pending" ? (
                        <div className="rounded-lg border bg-slate-50 p-6 text-center dark:bg-slate-900/50">
                            <Loader2 className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                            <p className="text-muted-foreground mt-2">Extraction in progress...</p>
                        </div>
                    ) : featureEntries.length > 0 ? (
                        <div className="space-y-4">
                            <div className="relative max-w-sm">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                <Input
                                    placeholder="Search features..."
                                    value={featureSearch}
                                    onChange={(e) => setFeatureSearch(e.target.value)}
                                    className="pl-9"
                                />
                            </div>

                            <div className="max-h-[500px] overflow-y-auto rounded-lg border">
                                <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                                    <thead className="bg-slate-50 dark:bg-slate-900/50 sticky top-0">
                                        <tr>
                                            <th className="px-4 py-3 text-left font-semibold text-muted-foreground">
                                                Feature Name
                                            </th>
                                            <th className="px-4 py-3 text-right font-semibold text-muted-foreground">
                                                Value
                                            </th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                        {featureEntries.map(([key, value]) => (
                                            <tr key={key} className="hover:bg-slate-50 dark:hover:bg-slate-900/30">
                                                <td className="px-4 py-3 font-mono text-sm">{key}</td>
                                                <td className="px-4 py-3 text-right font-mono text-sm">
                                                    {value === null || value === undefined
                                                        ? <span className="text-muted-foreground">null</span>
                                                        : typeof value === "boolean"
                                                            ? value ? "true" : "false"
                                                            : String(value)}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    ) : (
                        <div className="rounded-lg border bg-slate-50 p-6 text-center dark:bg-slate-900/50">
                            <p className="text-muted-foreground">No features extracted.</p>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
