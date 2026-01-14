"use client";

import { useParams } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import {
    Loader2,
    Database,
    CheckCircle2,
    AlertCircle,
    XCircle,
    Activity,
    Filter,
    Cpu,
} from "lucide-react";
import {
    trainingScenariosApi,
    TrainingScenarioRecord,
} from "@/lib/api/training-scenarios";
import { useSSE } from "@/contexts/sse-context";

// Phase stepper component - Only 2 phases (Generate Dataset is separate)
function ScenarioStepper({ status }: { status: string }) {
    const phases = [
        { key: "ingestion", label: "Ingestion", statuses: ["queued", "filtering", "ingesting", "ingested"] },
        { key: "processing", label: "Processing", statuses: ["processing", "processed"] },
    ];

    const getPhaseStatus = (phaseStatuses: string[]) => {
        if (status === "failed") return "failed";

        // Special case: 'ingested' is the terminal state of Ingestion Phase
        if (status === "ingested" && phaseStatuses.includes("ingested")) return "completed";

        // Special case: 'processed' is the terminal state of Processing Phase
        if (status === "processed" && phaseStatuses.includes("processed")) return "completed";

        const idx = phases.findIndex((p) => p.statuses.includes(status));
        const phaseIdx = phases.findIndex((p) => p.statuses === phaseStatuses);

        if (idx > phaseIdx) return "completed";
        if (idx === phaseIdx) return "active";
        return "pending";
    };

    return (
        <div className="max-w-lg mx-auto w-full">
            <div className="flex items-center justify-center gap-4">
                {phases.map((phase, i) => {
                    const phaseStatus = getPhaseStatus(phase.statuses);
                    return (
                        <div key={phase.key} className={`flex items-center gap-2 ${i < phases.length - 1 ? "flex-1" : "flex-none"}`}>
                            <div
                                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${phaseStatus === "completed"
                                    ? "bg-green-500 text-white"
                                    : phaseStatus === "active"
                                        ? "bg-blue-500 text-white"
                                        : phaseStatus === "failed"
                                            ? "bg-red-500 text-white"
                                            : "bg-muted text-muted-foreground"
                                    }`}
                            >
                                {phaseStatus === "completed" ? (
                                    <CheckCircle2 className="h-4 w-4" />
                                ) : phaseStatus === "active" ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    i + 1
                                )}
                            </div>
                            <span
                                className={`text-sm font-medium ${phaseStatus === "active" ? "text-primary" : "text-muted-foreground"
                                    }`}
                            >
                                {phase.label}
                            </span>
                            {i < phases.length - 1 && (
                                <div
                                    className={`flex-1 h-0.5 ${phaseStatus === "completed" ? "bg-green-500" : "bg-muted"
                                        }`}
                                />
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

export default function ScenarioOverviewPage() {
    const params = useParams<{ scenarioId: string }>();
    const scenarioId = params.scenarioId;
    const { subscribe } = useSSE();

    const [scenario, setScenario] = useState<TrainingScenarioRecord | null>(null);
    const [loading, setLoading] = useState(true);
    const [exportsCount, setExportsCount] = useState(0);

    // Fetch scenario
    const fetchScenario = useCallback(async () => {
        try {
            const data = await trainingScenariosApi.get(scenarioId);
            setScenario(data);

            // Fetch exports count
            const exportsData = await trainingScenariosApi.listExports(scenarioId, { limit: 1 });
            setExportsCount(exportsData.total);
        } catch (err) {
            console.error("Failed to fetch scenario:", err);
        } finally {
            setLoading(false);
        }
    }, [scenarioId]);

    useEffect(() => {
        fetchScenario();
    }, [fetchScenario]);

    // SSE subscription
    useEffect(() => {
        const unsubscribe = subscribe("SCENARIO_UPDATE", (data: Partial<TrainingScenarioRecord> & { scenario_id?: string }) => {
            if (data.scenario_id === scenarioId) {
                setScenario((prev) =>
                    prev
                        ? {
                            ...prev,
                            ...data,
                            status: data.status || prev.status,
                        }
                        : prev
                );
            }
        });
        return () => unsubscribe();
    }, [subscribe, scenarioId]);

    // Loading state
    if (loading || !scenario) {
        return (
            <div className="flex min-h-[400px] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    // Calculate progress percentages
    const ingestionProgress =
        scenario.builds_total > 0
            ? Math.round((scenario.builds_ingested / scenario.builds_total) * 100)
            : 0;
    const processingProgress =
        scenario.builds_ingested > 0
            ? Math.round((scenario.builds_features_extracted / scenario.builds_ingested) * 100)
            : 0;
    const scanProgress =
        scenario.scans_total > 0
            ? Math.round((scenario.scans_completed / scenario.scans_total) * 100)
            : 0;

    return (
        <div className="space-y-6">
            {/* Stepper */}
            <Card>
                <CardContent className="pt-6">
                    <ScenarioStepper status={scenario.status} />
                </CardContent>
            </Card>

            {/* Stats Grid */}
            <div className="grid gap-4 grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Total Builds</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{scenario.builds_total}</div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Ingested</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{scenario.builds_ingested}</div>
                        <Progress value={ingestionProgress} className="mt-2" indicatorClassName="bg-green-500" />
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Extracted</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{scenario.builds_features_extracted}</div>
                        <Progress value={processingProgress} className="mt-2" indicatorClassName="bg-purple-500" />
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Scans</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">
                            {scenario.scans_completed}/{scenario.scans_total}
                        </div>
                        <Progress value={scanProgress} className="mt-2" indicatorClassName="bg-orange-500" />
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Datasets</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{exportsCount}</div>
                        <p className="text-xs text-muted-foreground mt-2">Generated datasets</p>
                    </CardContent>
                </Card>
            </div>

            {/* Configuration Summary */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">Configuration</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid md:grid-cols-3 gap-8">
                        {/* Ingestion Stats */}
                        <div className="space-y-3">
                            <h4 className="font-semibold text-sm">Ingestion</h4>
                            <div className="space-y-2 text-sm">
                                <div className="flex justify-between p-2 bg-muted/40 rounded-md">
                                    <span className="text-muted-foreground">Total Builds</span>
                                    <span className="font-medium">{scenario.builds_total || 0}</span>
                                </div>
                                <div className="flex justify-between p-2 bg-green-50 dark:bg-green-950/30 rounded-md">
                                    <span className="text-muted-foreground">Ingested</span>
                                    <span className="font-medium text-green-600">{scenario.builds_ingested || 0}</span>
                                </div>
                                <div className="flex justify-between p-2 bg-red-50 dark:bg-red-950/30 rounded-md">
                                    <span className="text-muted-foreground">Failed</span>
                                    <span className="font-medium text-red-600">{scenario.builds_ingestion_failed || 0}</span>
                                </div>
                                <div className="flex justify-between p-2 bg-yellow-50 dark:bg-yellow-950/30 rounded-md">
                                    <span className="text-muted-foreground">Missing Resource</span>
                                    <span className="font-medium text-yellow-600">{scenario.builds_missing_resource || 0}</span>
                                </div>
                            </div>
                        </div>

                        {/* Feature Extraction Stats */}
                        <div className="space-y-3">
                            <h4 className="font-semibold text-sm">Feature Extraction</h4>
                            <div className="space-y-2 text-sm">
                                <div className="flex justify-between p-2 bg-green-50 dark:bg-green-950/30 rounded-md">
                                    <span className="text-muted-foreground">Extracted</span>
                                    <span className="font-medium text-green-600">{scenario.builds_features_extracted || 0}</span>
                                </div>
                                <div className="flex justify-between p-2 bg-red-50 dark:bg-red-950/30 rounded-md">
                                    <span className="text-muted-foreground">Failed</span>
                                    <span className="font-medium text-red-600">{scenario.builds_features_extracted_failed || 0}</span>
                                </div>
                                <div className="flex justify-between p-2 bg-muted/40 rounded-md">
                                    <span className="text-muted-foreground">Completed</span>
                                    <span className={`font-medium ${scenario.feature_extraction_completed ? 'text-green-600' : 'text-yellow-600'}`}>
                                        {scenario.feature_extraction_completed ? '✓ Yes' : '⏳ In Progress'}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Scan Metrics Stats */}
                        <div className="space-y-3">
                            <h4 className="font-semibold text-sm">Scan Metrics</h4>
                            <div className="space-y-2 text-sm">
                                <div className="flex justify-between p-2 bg-muted/40 rounded-md">
                                    <span className="text-muted-foreground">Total Scans</span>
                                    <span className="font-medium">{scenario.scans_total || 0}</span>
                                </div>
                                <div className="flex justify-between p-2 bg-green-50 dark:bg-green-950/30 rounded-md">
                                    <span className="text-muted-foreground">Completed</span>
                                    <span className="font-medium text-green-600">{scenario.scans_completed || 0}</span>
                                </div>
                                <div className="flex justify-between p-2 bg-red-50 dark:bg-red-950/30 rounded-md">
                                    <span className="text-muted-foreground">Failed</span>
                                    <span className="font-medium text-red-600">{scenario.scans_failed || 0}</span>
                                </div>
                                <div className="flex justify-between p-2 bg-muted/40 rounded-md">
                                    <span className="text-muted-foreground">Completed</span>
                                    <span className={`font-medium ${scenario.scan_extraction_completed ? 'text-green-600' : 'text-yellow-600'}`}>
                                        {scenario.scan_extraction_completed ? '✓ Yes' : (scenario.scans_total > 0 ? '⏳ In Progress' : '—')}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Data Source Filters Column */}
                        {(scenario as any).data_source_config && (
                            <div className="space-y-4">
                                <div className="flex items-center gap-2">
                                    <h4 className="font-semibold">Filters</h4>
                                </div>
                                <div className="space-y-3 text-sm border-l-2 pl-4 border-muted">
                                    <div>
                                        <span className="text-muted-foreground block text-xs">Languages</span>
                                        <span className="font-medium">
                                            {(scenario as any).data_source_config.languages && (scenario as any).data_source_config.languages.length > 0
                                                ? (scenario as any).data_source_config.languages.join(", ")
                                                : "All"}
                                        </span>
                                    </div>
                                    <div>
                                        <span className="text-muted-foreground block text-xs">Date Range</span>
                                        <span className="font-medium">
                                            {(scenario as any).data_source_config.date_start
                                                ? `${(scenario as any).data_source_config.date_start} - ${(scenario as any).data_source_config.date_end || "Now"}`
                                                : "All Time"}
                                        </span>
                                    </div>
                                    <div>
                                        <span className="text-muted-foreground block text-xs">Conclusions</span>
                                        <div className="flex gap-1 flex-wrap mt-1">
                                            {(scenario as any).data_source_config.conclusions && (scenario as any).data_source_config.conclusions.length > 0
                                                ? (scenario as any).data_source_config.conclusions.map((c: string) => (
                                                    <Badge key={c} variant="secondary" className="text-xs px-1 py-0">{c}</Badge>
                                                ))
                                                : <Badge variant="outline" className="text-xs">All</Badge>}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Feature Config Column */}
                        {(scenario as any).feature_config && (
                            <div className="space-y-4">
                                <div className="flex items-center gap-2">
                                    <h4 className="font-semibold">Features & Tools</h4>
                                </div>
                                <div className="space-y-3 text-sm bg-muted/20 p-4 rounded-lg">
                                    <div className="flex justify-between items-center border-b pb-2">
                                        <span className="text-muted-foreground">DAG Features</span>
                                        <Badge variant="default">{(scenario as any).feature_config.dag_features?.length || 0}</Badge>
                                    </div>
                                    <div className="space-y-2 pt-1">
                                        <span className="text-muted-foreground block text-xs">Active Scan Tools</span>
                                        <div className="flex gap-2">
                                            {(scenario as any).feature_config.scan_metrics?.sonarqube ? (
                                                <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">SonarQube</Badge>
                                            ) : null}
                                            {(scenario as any).feature_config.scan_metrics?.trivy ? (
                                                <Badge variant="outline" className="bg-indigo-50 text-indigo-700 border-indigo-200">Trivy</Badge>
                                            ) : null}
                                            {!(scenario as any).feature_config.scan_metrics?.sonarqube && !(scenario as any).feature_config.scan_metrics?.trivy && (
                                                <span className="text-muted-foreground text-xs italic">No scan tools enabled</span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>

            {/* Split Summary (if completed) */}

        </div>
    );
}
