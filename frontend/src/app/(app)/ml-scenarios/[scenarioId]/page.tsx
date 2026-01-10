"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
    ArrowLeft,
    Beaker,
    Download,
    FileCode,
    Loader2,
    Play,
    RefreshCw,
    Trash2,
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
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "@/components/ui/use-toast";
import { useSSE } from "@/contexts/sse-context";
import {
    mlScenariosApi,
    type MLScenarioRecord,
    type MLDatasetSplitRecord,
} from "@/lib/api";
import { formatDateTime } from "@/lib/utils";

// Status badge component
function ScenarioStatusBadge({ status }: { status: string }) {
    const config: Record<string, { className: string; label: string }> = {
        queued: { className: "border-slate-400 text-slate-500", label: "Queued" },
        filtering: { className: "border-blue-500 text-blue-600", label: "Filtering..." },
        ingesting: { className: "border-blue-500 text-blue-600", label: "Ingesting..." },
        processing: { className: "border-purple-500 text-purple-600", label: "Processing..." },
        splitting: { className: "border-orange-500 text-orange-600", label: "Splitting..." },
        completed: { className: "border-green-500 text-green-600", label: "Completed" },
        failed: { className: "bg-red-100 text-red-700 border-red-300", label: "Failed" },
    };

    const { className, label } = config[status] || config.queued;

    return (
        <Badge variant="outline" className={className}>
            {label}
        </Badge>
    );
}

function formatBytes(bytes: number) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function ScenarioDetailPage() {
    const params = useParams();
    const router = useRouter();
    const { subscribe } = useSSE();
    const scenarioId = params.scenarioId as string;

    const [scenario, setScenario] = useState<MLScenarioRecord | null>(null);
    const [yamlConfig, setYamlConfig] = useState<string>("");
    const [splits, setSplits] = useState<MLDatasetSplitRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    const loadScenario = useCallback(async (showSpinner = false) => {
        if (showSpinner) setRefreshing(true);
        try {
            const [scenarioData, configData, splitsData] = await Promise.all([
                mlScenariosApi.get(scenarioId),
                mlScenariosApi.getConfig(scenarioId),
                mlScenariosApi.getSplits(scenarioId).catch(() => ({ splits: [] })),
            ]);

            setScenario(scenarioData);
            setYamlConfig(configData.yaml_config);
            setSplits(splitsData.splits || []);
        } catch (err) {
            console.error(err);
            toast({
                title: "Error",
                description: "Failed to load scenario",
                variant: "destructive",
            });
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, [scenarioId]);

    useEffect(() => {
        loadScenario();
    }, [loadScenario]);

    // Subscribe to SSE for real-time updates (replaces polling)
    useEffect(() => {
        const unsubscribe = subscribe("SCENARIO_UPDATE", (data: any) => {
            if (data.scenario_id === scenarioId) {
                // Update scenario with real-time data
                setScenario((prev) =>
                    prev
                        ? {
                            ...prev,
                            status: data.status || prev.status,
                            builds_total: data.builds_total ?? prev.builds_total,
                            builds_ingested: data.builds_ingested ?? prev.builds_ingested,
                            builds_features_extracted: data.builds_features_extracted ?? prev.builds_features_extracted,
                            builds_failed: data.builds_failed ?? prev.builds_failed,
                            scans_total: data.scans_total ?? prev.scans_total,
                            scans_completed: data.scans_completed ?? prev.scans_completed,
                            scans_failed: data.scans_failed ?? prev.scans_failed,
                            train_count: data.train_count ?? prev.train_count,
                            val_count: data.val_count ?? prev.val_count,
                            test_count: data.test_count ?? prev.test_count,
                            feature_extraction_completed:
                                data.feature_extraction_completed ?? prev.feature_extraction_completed,
                            scan_extraction_completed:
                                data.scan_extraction_completed ?? prev.scan_extraction_completed,
                        }
                        : prev
                );
            }
        });
        return () => unsubscribe();
    }, [subscribe, scenarioId]);

    const handleStartGeneration = async () => {
        try {
            const result = await mlScenariosApi.startGeneration(scenarioId);
            toast({
                title: "Started",
                description: result.message,
            });
            loadScenario(true);
        } catch (err) {
            console.error(err);
            toast({
                title: "Error",
                description: "Failed to start generation",
                variant: "destructive",
            });
        }
    };

    const handleDelete = async () => {
        if (!confirm(`Delete scenario "${scenario?.name}"? This cannot be undone.`)) {
            return;
        }
        try {
            await mlScenariosApi.delete(scenarioId);
            toast({ title: "Deleted", description: "Scenario deleted successfully" });
            router.push("/ml-scenarios");
        } catch (err) {
            console.error(err);
            toast({
                title: "Error",
                description: "Failed to delete scenario",
                variant: "destructive",
            });
        }
    };

    if (loading) {
        return (
            <div className="flex min-h-[60vh] items-center justify-center">
                <Card className="w-full max-w-md">
                    <CardHeader>
                        <CardTitle>Loading scenario...</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                    </CardContent>
                </Card>
            </div>
        );
    }

    if (!scenario) {
        return (
            <div className="space-y-4">
                <Button variant="ghost" onClick={() => router.push("/ml-scenarios")}>
                    <ArrowLeft className="h-4 w-4 mr-2" />
                    Back to Scenarios
                </Button>
                <Card>
                    <CardContent className="py-12 text-center text-muted-foreground">
                        Scenario not found
                    </CardContent>
                </Card>
            </div>
        );
    }

    const isProcessing = ["filtering", "ingesting", "processing", "splitting"].includes(scenario.status);

    return (
        <div className="space-y-6">
            {/* Back Button */}
            <Button
                variant="ghost"
                onClick={() => router.push("/ml-scenarios")}
                className="gap-2"
            >
                <ArrowLeft className="h-4 w-4" />
                Back to Scenarios
            </Button>

            {/* Header */}
            <Card>
                <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <CardTitle className="flex items-center gap-2">
                            <Beaker className="h-5 w-5" />
                            {scenario.name}
                        </CardTitle>
                        <CardDescription>
                            {scenario.description || "No description"}
                        </CardDescription>
                        <div className="mt-2 flex items-center gap-2">
                            <ScenarioStatusBadge status={scenario.status} />
                            {scenario.splitting_strategy && (
                                <Badge variant="secondary">
                                    {scenario.splitting_strategy.replace(/_/g, " ")}
                                </Badge>
                            )}
                            {scenario.group_by && (
                                <Badge variant="outline">
                                    by {scenario.group_by.replace(/_/g, " ")}
                                </Badge>
                            )}
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => loadScenario(true)}
                            disabled={refreshing}
                        >
                            <RefreshCw className={`h-4 w-4 mr-1 ${refreshing ? "animate-spin" : ""}`} />
                            Refresh
                        </Button>
                        {scenario.status === "queued" && (
                            <Button
                                size="sm"
                                onClick={handleStartGeneration}
                                className="gap-2"
                            >
                                <Play className="h-4 w-4" />
                                Start Generation
                            </Button>
                        )}
                        <Button
                            variant="destructive"
                            size="sm"
                            onClick={handleDelete}
                            disabled={isProcessing}
                        >
                            <Trash2 className="h-4 w-4 mr-1" />
                            Delete
                        </Button>
                    </div>
                </CardHeader>
            </Card>

            {/* Error Message */}
            {scenario.error_message && (
                <Card className="border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950">
                    <CardContent className="py-4 text-red-700 dark:text-red-300">
                        <strong>Error:</strong> {scenario.error_message}
                    </CardContent>
                </Card>
            )}

            {/* Statistics */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                <Card>
                    <CardContent className="pt-4 text-center">
                        <p className="text-2xl font-bold">{scenario.builds_total.toLocaleString()}</p>
                        <p className="text-xs text-muted-foreground">Total Builds</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 text-center">
                        <p className="text-2xl font-bold text-green-600">{scenario.builds_features_extracted.toLocaleString()}</p>
                        <p className="text-xs text-muted-foreground">Processed</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 text-center">
                        <p className="text-2xl font-bold text-blue-600">{scenario.train_count.toLocaleString()}</p>
                        <p className="text-xs text-muted-foreground">Train</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 text-center">
                        <p className="text-2xl font-bold text-purple-600">{scenario.val_count.toLocaleString()}</p>
                        <p className="text-xs text-muted-foreground">Validation</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 text-center">
                        <p className="text-2xl font-bold text-orange-600">{scenario.test_count.toLocaleString()}</p>
                        <p className="text-xs text-muted-foreground">Test</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 text-center">
                        <p className="text-2xl font-bold text-red-600">{scenario.builds_failed.toLocaleString()}</p>
                        <p className="text-xs text-muted-foreground">Failed</p>
                    </CardContent>
                </Card>
            </div>

            {/* Progress Section - Only show during processing */}
            {isProcessing && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium">Feature Extraction</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <Progress
                                value={
                                    scenario.builds_total > 0
                                        ? (scenario.builds_features_extracted / scenario.builds_total) * 100
                                        : 0
                                }
                                className="h-2"
                            />
                            <p className="text-xs mt-2 text-muted-foreground">
                                {scenario.builds_features_extracted}/{scenario.builds_total} builds processed
                                {scenario.feature_extraction_completed && (
                                    <span className="text-green-600 ml-2">✓ Complete</span>
                                )}
                            </p>
                        </CardContent>
                    </Card>

                    {scenario.scans_total > 0 && (
                        <Card>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium">Security Scans</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <Progress
                                    value={
                                        scenario.scans_total > 0
                                            ? (scenario.scans_completed / scenario.scans_total) * 100
                                            : 0
                                    }
                                    className="h-2"
                                />
                                <p className="text-xs mt-2 text-muted-foreground">
                                    {scenario.scans_completed}/{scenario.scans_total} scans
                                    {scenario.scans_failed > 0 && (
                                        <span className="text-red-500 ml-2">
                                            ({scenario.scans_failed} failed)
                                        </span>
                                    )}
                                    {scenario.scan_extraction_completed && (
                                        <span className="text-green-600 ml-2">✓ Complete</span>
                                    )}
                                </p>
                            </CardContent>
                        </Card>
                    )}
                </div>
            )}

            {/* Tabs */}
            <Tabs defaultValue="splits" className="w-full">
                <TabsList>
                    <TabsTrigger value="splits">Splits</TabsTrigger>
                    <TabsTrigger value="config">Configuration</TabsTrigger>
                </TabsList>

                {/* Splits Tab */}
                <TabsContent value="splits">
                    <Card>
                        <CardHeader>
                            <CardTitle>Generated Splits</CardTitle>
                            <CardDescription>
                                Download train/validation/test dataset files
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {splits.length === 0 ? (
                                <div className="py-8 text-center text-muted-foreground">
                                    {scenario.status === "completed"
                                        ? "No splits generated"
                                        : "Splits will appear here after generation completes"}
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {splits.map((split) => (
                                        <div
                                            key={split.id}
                                            className="flex items-center justify-between rounded-lg border p-4"
                                        >
                                            <div>
                                                <p className="font-medium capitalize">
                                                    {split.split_type} Split
                                                </p>
                                                <p className="text-sm text-muted-foreground">
                                                    {split.record_count.toLocaleString()} records • {split.feature_count} features • {formatBytes(split.file_size_bytes)}
                                                </p>
                                                {split.class_distribution && (
                                                    <div className="mt-1 flex gap-2">
                                                        {Object.entries(split.class_distribution).map(([label, count]) => (
                                                            <Badge key={label} variant="outline" className="text-xs">
                                                                Label {label}: {count}
                                                            </Badge>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => {
                                                    window.open(
                                                        mlScenariosApi.getDownloadUrl(scenarioId, split.split_type),
                                                        "_blank"
                                                    );
                                                }}
                                            >
                                                <Download className="h-4 w-4 mr-2" />
                                                Download
                                            </Button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Config Tab */}
                <TabsContent value="config">
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <FileCode className="h-5 w-5" />
                                YAML Configuration
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <pre className="bg-slate-50 dark:bg-slate-900 p-4 rounded-lg overflow-x-auto text-sm font-mono">
                                {yamlConfig || "No configuration available"}
                            </pre>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>

            {/* Timestamps */}
            <Card>
                <CardContent className="py-4">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                            <p className="text-muted-foreground">Created</p>
                            <p>{formatDateTime(scenario.created_at)}</p>
                        </div>
                        {scenario.filtering_completed_at && (
                            <div>
                                <p className="text-muted-foreground">Filtering Completed</p>
                                <p>{formatDateTime(scenario.filtering_completed_at)}</p>
                            </div>
                        )}
                        {scenario.processing_completed_at && (
                            <div>
                                <p className="text-muted-foreground">Processing Completed</p>
                                <p>{formatDateTime(scenario.processing_completed_at)}</p>
                            </div>
                        )}
                        {scenario.splitting_completed_at && (
                            <div>
                                <p className="text-muted-foreground">Splitting Completed</p>
                                <p>{formatDateTime(scenario.splitting_completed_at)}</p>
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
