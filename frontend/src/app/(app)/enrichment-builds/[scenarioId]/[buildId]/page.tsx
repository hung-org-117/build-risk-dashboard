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
    Box,
    FileJson
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
import {
    trainingScenariosApi,
    TrainingEnrichmentBuildDetail
} from "@/lib/api/training-scenarios";
import { cn, formatDateTime } from "@/lib/utils";

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
    if (s === "pending" || s === "extracting") {
        return (
            <Badge variant="secondary" className="gap-1">
                <Loader2 className="h-3 w-3 animate-spin" /> {s === "pending" ? "Pending" : "Extracting"}
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

function FeatureValue({ value }: { value: unknown }) {
    if (value === null || value === undefined) {
        return <span className="text-muted-foreground italic">null</span>;
    }

    if (typeof value === "boolean") {
        return (
            <Badge variant={value ? "default" : "secondary"} className="font-mono">
                {value ? "true" : "false"}
            </Badge>
        );
    }

    if (typeof value === "number") {
        return <span className="font-mono">{value}</span>;
    }

    if (typeof value === "object") {
        const jsonStr = JSON.stringify(value, null, 2);
        return (
            <div className="max-w-[400px] overflow-x-auto">
                <pre className="font-mono text-xs whitespace-pre bg-slate-50 dark:bg-slate-900/50 rounded px-2 py-1">
                    {jsonStr}
                </pre>
            </div>
        );
    }

    const strValue = String(value);

    if (strValue.length > 60 || strValue.includes("#")) {
        return (
            <div className="max-w-[400px] overflow-x-auto">
                <code className="font-mono text-xs whitespace-nowrap bg-slate-50 dark:bg-slate-900/50 rounded px-2 py-1 block">
                    {strValue}
                </code>
            </div>
        );
    }

    return <span className="font-mono">{strValue}</span>;
}

export default function EnrichmentBuildDetailPage() {
    const params = useParams();
    const router = useRouter();
    const scenarioId = params.scenarioId as string;
    const buildId = params.buildId as string;

    const [detail, setDetail] = useState<TrainingEnrichmentBuildDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [featureSearch, setFeatureSearch] = useState("");

    useEffect(() => {
        const loadDetail = async () => {
            setLoading(true);
            try {
                const data = await trainingScenariosApi.getEnrichmentBuildDetail(scenarioId, buildId);
                setDetail(data);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        if (scenarioId && buildId) {
            loadDetail();
        }
    }, [scenarioId, buildId]);

    const featureEntries = useMemo(() => {
        if (!detail?.enrichment_build.features) return [];
        return Object.entries(detail.enrichment_build.features)
            .sort(([a], [b]) => a.localeCompare(b))
            .filter(([key]) =>
                featureSearch === "" ||
                key.toLowerCase().includes(featureSearch.toLowerCase())
            );
    }, [detail, featureSearch]);

    if (loading) {
        return (
            <div className="flex min-h-[60vh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (!detail) {
        return (
            <div className="space-y-6">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => router.back()}
                    className="gap-2"
                >
                    <ArrowLeft className="h-4 w-4" />
                    Back
                </Button>
                <Card className="border-amber-200 bg-amber-50/60 dark:border-amber-800 dark:bg-amber-900/20">
                    <CardHeader>
                        <CardTitle className="text-amber-700 dark:text-amber-300">
                            Build Not Found
                        </CardTitle>
                        <CardDescription>The requested enrichment build could not be loaded.</CardDescription>
                    </CardHeader>
                </Card>
            </div>
        );
    }

    const { enrichment_build, raw_build_run, audit_log } = detail;

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => router.push(`/scenarios/${scenarioId}/builds/processing`)}
                    className="gap-2"
                >
                    <ArrowLeft className="h-4 w-4" />
                    Back to Feature Extraction
                </Button>
                <div className="flex-1">
                    <h1 className="text-2xl font-bold tracking-tight">
                        Feature Extraction Detail
                    </h1>
                    <p className="text-muted-foreground text-sm">
                        Build <span className="font-mono">{raw_build_run.ci_run_id}</span> • {raw_build_run.commit_sha.substring(0, 7)}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <ExtractionStatusBadge status={enrichment_build.extraction_status} />
                    {raw_build_run.web_url && (
                        <a
                            href={raw_build_run.web_url}
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

            {/* Build Run Information */}
            <Card>
                <CardHeader>
                    <CardTitle>Build Context</CardTitle>
                    <CardDescription>Source build and environment</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Commit Info */}
                    <div className="rounded-lg border p-4 space-y-3">
                        <div className="flex items-center gap-2 text-sm">
                            <GitCommit className="h-4 w-4 text-muted-foreground" />
                            <span className="font-mono text-sm">{raw_build_run.commit_sha}</span>
                            <Badge variant="secondary">{raw_build_run.branch}</Badge>
                        </div>
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Box className="h-4 w-4" />
                            <span className="font-medium text-foreground">{raw_build_run.repo_name}</span>
                        </div>
                    </div>

                    {/* Metadata Grid */}
                    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                        <div className="rounded-lg border p-4">
                            <p className="text-xs text-muted-foreground">CI Build ID</p>
                            <p className="font-mono text-sm mt-1 truncate" title={raw_build_run.ci_run_id}>
                                {raw_build_run.ci_run_id}
                            </p>
                        </div>
                        <div className="rounded-lg border p-4">
                            <p className="text-xs text-muted-foreground">Provider</p>
                            <p className="font-medium mt-1 capitalize">
                                {raw_build_run.provider.replace("_", " ")}
                            </p>
                        </div>
                        <div className="rounded-lg border p-4">
                            <p className="text-xs text-muted-foreground">Extracted At</p>
                            <p className="font-medium mt-1 text-sm">
                                {formatDateTime(enrichment_build.enriched_at)}
                            </p>
                        </div>
                        <div className="rounded-lg border p-4">
                            <p className="text-xs text-muted-foreground">CI Conclusion</p>
                            <p className="font-medium mt-1 capitalize">
                                {raw_build_run.conclusion}
                            </p>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Audit Log / Node Performance */}
            {audit_log && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Clock className="h-5 w-5" />
                            Extraction Performance
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 mb-6">
                            <div className="rounded-lg border p-4">
                                <p className="text-xs text-muted-foreground">Total Duration</p>
                                <p className="font-medium mt-1">{audit_log.duration_ms}ms</p>
                            </div>
                            <div className="rounded-lg border p-4">
                                <p className="text-xs text-muted-foreground">Nodes Success</p>
                                <p className="font-medium mt-1 text-green-600">{audit_log.nodes_succeeded}</p>
                            </div>
                            <div className="rounded-lg border p-4">
                                <p className="text-xs text-muted-foreground">Nodes Failed</p>
                                <p className="font-medium mt-1 text-red-600">{audit_log.nodes_failed}</p>
                            </div>
                            <div className="rounded-lg border p-4">
                                <p className="text-xs text-muted-foreground">Skipped</p>
                                <p className="font-medium mt-1 text-amber-600">{audit_log.nodes_skipped}</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Extraction Issues */}
            {((enrichment_build.missing_resources && enrichment_build.missing_resources.length > 0) ||
                (enrichment_build.skipped_features && enrichment_build.skipped_features.length > 0)) && (
                    <Card className="border-amber-200 bg-amber-50/50 dark:border-amber-900 dark:bg-amber-900/10">
                        <CardHeader>
                            <CardTitle className="text-amber-800 dark:text-amber-500 flex items-center gap-2">
                                <AlertTriangle className="h-5 w-5" />
                                Extraction Issues
                            </CardTitle>
                            <CardDescription>
                                Issues encountered during feature extraction
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            {enrichment_build.missing_resources && enrichment_build.missing_resources.length > 0 && (
                                <div>
                                    <h4 className="font-medium text-sm mb-2 text-amber-800 dark:text-amber-500">
                                        Missing Resources
                                    </h4>
                                    <p className="text-xs text-muted-foreground mb-2">
                                        The following resources were unavailable, preventing some features from being extracted.
                                    </p>
                                    <div className="flex flex-wrap gap-2">
                                        {enrichment_build.missing_resources.map((res) => (
                                            <Badge
                                                key={res}
                                                variant="outline"
                                                className="border-amber-300 text-amber-700 bg-amber-100 dark:border-amber-800 dark:bg-amber-900/50"
                                            >
                                                {res}
                                            </Badge>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {enrichment_build.skipped_features && enrichment_build.skipped_features.length > 0 && (
                                <div>
                                    <h4 className="font-medium text-sm mb-2 text-amber-800 dark:text-amber-500">
                                        Skipped Features
                                    </h4>
                                    <p className="text-xs text-muted-foreground mb-2">
                                        The following features could not be computed due to missing resources or errors.
                                    </p>
                                    <div className="flex flex-wrap gap-2">
                                        {enrichment_build.skipped_features.map((feat) => (
                                            <Badge
                                                key={feat}
                                                variant="outline"
                                                className="border-slate-300 text-slate-600 bg-slate-100 dark:border-slate-700 dark:bg-slate-800"
                                            >
                                                {feat}
                                            </Badge>
                                        ))}
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
                            </CardTitle>
                            <CardDescription>
                                {enrichment_build.feature_count} features found
                                {enrichment_build.expected_feature_count > 0 && ` / ${enrichment_build.expected_feature_count} expected`}
                            </CardDescription>
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    {enrichment_build.extraction_error ? (
                        <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-900/20">
                            <p className="text-sm text-red-700 dark:text-red-300">
                                Extraction failed: {enrichment_build.extraction_error}
                            </p>
                        </div>
                    ) : enrichment_build.feature_count > 0 ? (
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
                            {featureEntries.length > 0 ? (
                                <div className="rounded-lg border overflow-hidden max-h-[500px] overflow-y-auto relative">
                                    <table className="w-full text-sm relative">
                                        <thead className="sticky top-0 z-10">
                                            <tr className="bg-slate-50 dark:bg-slate-900/50 border-b border-slate-200 dark:border-slate-800">
                                                <th className="w-[280px] min-w-[280px] px-4 py-3 text-left font-semibold text-muted-foreground border-r border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900">
                                                    Feature Name
                                                </th>
                                                <th className="px-4 py-3 text-left font-semibold text-muted-foreground bg-slate-50 dark:bg-slate-900">
                                                    Value
                                                </th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                            {featureEntries.map(([key, value]) => (
                                                <tr key={key} className="hover:bg-slate-50 dark:hover:bg-slate-900/30">
                                                    <td className="w-[280px] min-w-[280px] px-4 py-3 font-mono text-sm border-r border-slate-100 dark:border-slate-800 align-top">
                                                        {key}
                                                    </td>
                                                    <td className="px-4 py-3 align-top">
                                                        <FeatureValue value={value} />
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <div className="rounded-lg border border-slate-200 bg-slate-50 p-6 text-center dark:border-slate-800 dark:bg-slate-900/50">
                                    <p className="text-muted-foreground">No features match "{featureSearch}"</p>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="rounded-lg border border-slate-200 bg-slate-50 p-6 text-center dark:border-slate-800 dark:bg-slate-900/50">
                            <p className="text-muted-foreground">No features extracted.</p>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
