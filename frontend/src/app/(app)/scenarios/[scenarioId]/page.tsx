"use client";

import { useParams } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
    Loader2,
    Database,
    CheckCircle2,
    AlertCircle,
    Play,
    RefreshCw,
    FileDown,
} from "lucide-react";
import {
    trainingScenariosApi,
    TrainingScenarioRecord,
} from "@/lib/api/training-scenarios";
import { useToast } from "@/components/ui/use-toast";
import { useSSE } from "@/contexts/sse-context";

// Phase stepper component
function ScenarioStepper({ status }: { status: string }) {
    const phases = [
        { key: "ingestion", label: "Ingestion", statuses: ["queued", "filtering", "ingesting", "ingested"] },
        { key: "processing", label: "Processing", statuses: ["processing", "processed"] },
        { key: "generation", label: "Generate", statuses: ["splitting", "completed"] },
    ];

    const getPhaseStatus = (phaseStatuses: string[]) => {
        if (status === "failed") return "failed";
        const idx = phases.findIndex((p) => p.statuses.includes(status));
        const phaseIdx = phases.findIndex((p) => p.statuses === phaseStatuses);

        if (idx > phaseIdx) return "completed";
        if (idx === phaseIdx) return "active";
        return "pending";
    };

    return (
        <div className="max-w-2xl mx-auto w-full">
            <div className="flex items-center justify-between gap-4">
                {phases.map((phase, i) => {
                    const phaseStatus = getPhaseStatus(phase.statuses);
                    return (
                        <div key={phase.key} className="flex items-center gap-2 flex-1">
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
    const { toast } = useToast();
    const { subscribe } = useSSE();

    const [scenario, setScenario] = useState<TrainingScenarioRecord | null>(null);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState<string | null>(null);

    // Fetch scenario
    const fetchScenario = useCallback(async () => {
        try {
            const data = await trainingScenariosApi.get(scenarioId);
            setScenario(data);
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

    // Action handlers
    const handleStartIngestion = async () => {
        setActionLoading("ingestion");
        try {
            await trainingScenariosApi.startIngestion(scenarioId);
            toast({ title: "Ingestion started" });
            fetchScenario();
        } catch (err) {
            toast({ variant: "destructive", title: "Failed to start ingestion" });
        } finally {
            setActionLoading(null);
        }
    };

    const handleStartProcessing = async () => {
        setActionLoading("processing");
        try {
            await trainingScenariosApi.startProcessing(scenarioId);
            toast({ title: "Processing started" });
            fetchScenario();
        } catch (err) {
            toast({ variant: "destructive", title: "Failed to start processing" });
        } finally {
            setActionLoading(null);
        }
    };

    const handleGenerateDataset = async () => {
        setActionLoading("generate");
        try {
            await trainingScenariosApi.generateDataset(scenarioId);
            toast({ title: "Dataset generation started" });
            fetchScenario();
        } catch (err) {
            toast({ variant: "destructive", title: "Failed to generate dataset" });
        } finally {
            setActionLoading(null);
        }
    };

    const handleRetryIngestion = async () => {
        setActionLoading("retry-ingestion");
        try {
            const result = await trainingScenariosApi.retryIngestion(scenarioId);
            toast({ title: result.message });
            fetchScenario();
        } catch (err) {
            toast({ variant: "destructive", title: "Failed to retry ingestion" });
        } finally {
            setActionLoading(null);
        }
    };

    const handleRetryProcessing = async () => {
        setActionLoading("retry-processing");
        try {
            const result = await trainingScenariosApi.retryProcessing(scenarioId);
            toast({ title: result.message });
            fetchScenario();
        } catch (err) {
            toast({ variant: "destructive", title: "Failed to retry processing" });
        } finally {
            setActionLoading(null);
        }
    };

    if (loading || !scenario) {
        return (
            <div className="flex min-h-[400px] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    // Calculate progress
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

    // Determine which actions are available
    const canStartIngestion = scenario.status === "queued";
    const canStartProcessing = scenario.status === "ingested";
    const canGenerateDataset = scenario.status === "processed";
    const hasFailedIngestion = scenario.builds_missing_resource > 0 || scenario.builds_failed > 0;
    const canRetryIngestion = hasFailedIngestion && ["ingested", "processing", "processed"].includes(scenario.status);
    const canRetryProcessing = scenario.status === "processed" && scenario.builds_features_extracted < scenario.builds_ingested;

    return (
        <div className="space-y-6">
            {/* Stepper */}
            <Card>
                <CardContent className="pt-6">
                    <ScenarioStepper status={scenario.status} />
                </CardContent>
            </Card>

            {/* Stats Grid */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Total Builds</CardTitle>
                        <Database className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{scenario.builds_total}</div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Ingested</CardTitle>
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{scenario.builds_ingested}</div>
                        <Progress value={ingestionProgress} className="mt-2" indicatorClassName="bg-green-500" />
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Extracted</CardTitle>
                        <CheckCircle2 className="h-4 w-4 text-purple-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{scenario.builds_features_extracted}</div>
                        <Progress value={processingProgress} className="mt-2" indicatorClassName="bg-purple-500" />
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Scans</CardTitle>
                        <AlertCircle className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">
                            {scenario.scans_completed}/{scenario.scans_total}
                        </div>
                        <Progress value={scanProgress} className="mt-2" />
                    </CardContent>
                </Card>
            </div>

            {/* Split Summary (if completed) */}

        </div>
    );
}
