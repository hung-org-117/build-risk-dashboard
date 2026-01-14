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
import {
    Loader2,
    Database,
    CheckCircle2,
    AlertCircle,
    XCircle,
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
        { key: "processing", label: "Processing", statuses: ["processing", "processed", "splitting", "completed"] },
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
    const { subscribe } = useSSE();

    const [scenario, setScenario] = useState<TrainingScenarioRecord | null>(null);
    const [loading, setLoading] = useState(true);

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
