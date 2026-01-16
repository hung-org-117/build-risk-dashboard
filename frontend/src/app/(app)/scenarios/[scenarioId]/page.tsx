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
        const unsubscribe = subscribe("SCENARIO.UPDATED", (data: Partial<TrainingScenarioRecord> & { scenario_id?: string }) => {
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

            {/* Configuration Summary */}
            <Card>
                <CardContent className="pt-8">
                    <div className="grid md:grid-cols-4 gap-8">
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

                        {/* Feature Extraction & Dataset Stats */}
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
                            </div>
                        </div>

                        {/* Dataset Stats */}
                        <div className="space-y-3">
                            <h4 className="font-semibold text-sm">Datasets</h4>
                            <div className="flex justify-between p-2 bg-blue-50 dark:bg-blue-950/30 rounded-md">
                                <div className="flex flex-col">
                                    <span className="text-muted-foreground">Datasets</span>
                                </div>
                                <span className="font-bold text-lg text-blue-600">{exportsCount}</span>
                            </div>
                        </div>
                    </div>

                    {/* New Configuration Header & Sections */}
                    <div className="mt-12 pt-8 border-t">
                        <h3 className="text-xl font-bold mb-6">Configuration</h3>
                        <div className="grid md:grid-cols-2 gap-12">
                            {/* Data Source Filters Column */}
                            {(scenario as any).data_source_config && (
                                <div className="space-y-4">
                                    <div className="flex items-center gap-2">
                                        <h4 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider">Filters</h4>
                                    </div>
                                    <div className="space-y-4 text-sm border-l-2 pl-6 border-slate-200 dark:border-slate-800">
                                        <div>
                                            <span className="text-muted-foreground block text-xs mb-1">Languages</span>
                                            <span className="font-medium text-base">
                                                {(scenario as any).data_source_config.languages && (scenario as any).data_source_config.languages.length > 0
                                                    ? (scenario as any).data_source_config.languages.join(", ")
                                                    : "All"}
                                            </span>
                                        </div>
                                        <div>
                                            <span className="text-muted-foreground block text-xs mb-1">Date Range</span>
                                            <span className="font-medium text-base">
                                                {(scenario as any).data_source_config.date_start
                                                    ? `${(scenario as any).data_source_config.date_start} - ${(scenario as any).data_source_config.date_end || "Now"}`
                                                    : "All Time"}
                                            </span>
                                        </div>
                                        <div>
                                            <span className="text-muted-foreground block text-xs mb-1">Conclusions</span>
                                            <div className="flex gap-1.5 flex-wrap mt-1">
                                                {(scenario as any).data_source_config.conclusions && (scenario as any).data_source_config.conclusions.length > 0
                                                    ? (scenario as any).data_source_config.conclusions.map((c: string) => (
                                                        <Badge key={c} variant="secondary" className="px-2 py-0.5">{c}</Badge>
                                                    ))
                                                    : <Badge variant="outline">All</Badge>}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Feature Config Column */}
                            {(scenario as any).feature_config && (
                                <div className="space-y-4">
                                    <div className="flex items-center gap-2">
                                        <h4 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider">Features & Tools</h4>
                                    </div>
                                    <div className="space-y-4 text-sm bg-transparent p-0 border-0 rounded-none dark:border-0 dark:bg-transparent">
                                        <div className="flex justify-between items-center border-b border-slate-200 dark:border-slate-800 pb-3">
                                            <span className="text-muted-foreground text-sm font-medium">DAG Features</span>
                                            <Badge variant="default" className="bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 px-3">
                                                {(scenario as any).feature_config.dag_features?.length || 0}
                                            </Badge>
                                        </div>
                                        <div className="space-y-3 pt-1">
                                            <span className="text-muted-foreground block text-xs font-medium uppercase tracking-tight">Active Scan Tools</span>
                                            <div className="flex gap-2">
                                                {(scenario as any).feature_config.scan_metrics?.sonarqube ? (
                                                    <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 px-3 py-1">SonarQube</Badge>
                                                ) : null}
                                                {(scenario as any).feature_config.scan_metrics?.trivy ? (
                                                    <Badge variant="outline" className="bg-indigo-50 text-indigo-700 border-indigo-200 px-3 py-1">Trivy</Badge>
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
                    </div>
                </CardContent>
            </Card>

            {/* Split Summary (if completed) */}

        </div>
    );
}
