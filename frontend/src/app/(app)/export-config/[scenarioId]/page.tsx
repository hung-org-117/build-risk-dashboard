"use client";

import { useParams, useRouter } from "next/navigation";
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
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { ChevronLeft, Loader2, Play, AlertTriangle, Settings } from "lucide-react";
import {
    trainingScenariosApi,
    TrainingScenarioRecord,
    TrainingExportCreateDTO,
} from "@/lib/api/training-scenarios";
import { toast } from "@/components/ui/use-toast";
import {
    ExportConfig,
    DEFAULT_CONFIG,
    STRATEGY,
    requiresGroupBy as checkRequiresGroupBy,
    STRATEGY_OPTIONS,
} from "../../scenarios/[scenarioId]/export/_components/types";
import { PreprocessingSection } from "../../scenarios/[scenarioId]/export/_components/PreprocessingSection";
import { SplittingStrategySection } from "../../scenarios/[scenarioId]/export/_components/SplittingStrategySection";
import { OutputFormatSection } from "../../scenarios/[scenarioId]/export/_components/OutputFormatSection";

// =============================================================================
// Helper Component for Data Availability
// =============================================================================

function DataAvailabilityIndicator({
    className,
    dataAvailability
}: {
    className?: string;
    dataAvailability: {
        features: { total: number; completed: number; coverage_pct: number; ready: boolean };
        trivy: { total: number; completed: number; coverage_pct: number; ready: boolean };
        sonarqube: { total: number; completed: number; coverage_pct: number; ready: boolean };
        all_complete: boolean;
    } | null;
}) {
    if (!dataAvailability) return null;

    const getScoreColor = (score: number | undefined | null) => {
        const val = score ?? 0;
        if (val >= 90) return 'text-green-600 dark:text-green-500';
        if (val >= 70) return 'text-yellow-600 dark:text-yellow-500';
        return 'text-red-600 dark:text-red-500';
    };

    return (
        <div className={`flex flex-wrap items-center gap-6 text-sm ${className}`}>
            <div className="flex items-center gap-2">
                <span className="text-muted-foreground font-medium">Features:</span>
                <span className={`font-bold text-base ${getScoreColor(dataAvailability.features.coverage_pct)}`}>
                    {dataAvailability.features.coverage_pct}%
                </span>
            </div>
            {dataAvailability.trivy.total > 0 && (
                <div className="flex items-center gap-2">
                    <span className="text-muted-foreground font-medium">Trivy:</span>
                    <span className={`font-bold text-base ${getScoreColor(dataAvailability.trivy.coverage_pct)}`}>
                        {dataAvailability.trivy.coverage_pct}%
                    </span>
                </div>
            )}
            {dataAvailability.sonarqube.total > 0 && (
                <div className="flex items-center gap-2">
                    <span className="text-muted-foreground font-medium">SonarQube:</span>
                    <span className={`font-bold text-base ${getScoreColor(dataAvailability.sonarqube.coverage_pct)}`}>
                        {dataAvailability.sonarqube.coverage_pct}%
                    </span>
                </div>
            )}
            {!dataAvailability.all_complete && (
                <span className="text-xs text-amber-600 flex items-center gap-1 font-medium bg-amber-50 px-2 py-1 rounded">
                    <AlertTriangle className="h-3 w-3" />
                    Scans in progress
                </span>
            )}
        </div>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export default function CreateExportPage() {
    const params = useParams<{ scenarioId: string }>();
    const router = useRouter();
    const scenarioId = params.scenarioId;

    const [scenario, setScenario] = useState<TrainingScenarioRecord | null>(null);
    const [loading, setLoading] = useState(true);
    const [creating, setCreating] = useState(false);
    const [config, setConfig] = useState<ExportConfig>(DEFAULT_CONFIG);
    const [groupsPreview, setGroupsPreview] = useState<{
        groups: Array<{ value: string; label: string; count: number; warning?: string }>;
        total_builds: number;
    } | null>(null);
    const [loadingGroups, setLoadingGroups] = useState(false);
    const [dataAvailability, setDataAvailability] = useState<{
        features: { total: number; completed: number; coverage_pct: number; ready: boolean };
        trivy: { total: number; completed: number; coverage_pct: number; ready: boolean };
        sonarqube: { total: number; completed: number; coverage_pct: number; ready: boolean };
        all_complete: boolean;
    } | null>(null);

    const fetchScenario = useCallback(async () => {
        try {
            const data = await trainingScenariosApi.get(scenarioId);
            setScenario(data);
        } catch (err) {
            console.error("Failed to fetch scenario:", err);
            toast({ variant: "destructive", title: "Failed to fetch scenario" });
        } finally {
            setLoading(false);
        }
    }, [scenarioId]);

    const fetchGroupsPreview = useCallback(async () => {
        if (!scenarioId) return;
        setLoadingGroups(true);
        try {
            const data = await trainingScenariosApi.getGroupPreview(scenarioId, {
                group_by: config.group_by,
                num_bins: config.num_bins,
                time_slots: config.time_slots,
            });
            setGroupsPreview(data);
        } catch (err) {
            console.error("Failed to fetch groups preview:", err);
            setGroupsPreview(null);
        } finally {
            setLoadingGroups(false);
        }
    }, [scenarioId, config.group_by, config.num_bins, config.time_slots]);

    const fetchDataAvailability = useCallback(async () => {
        if (!scenarioId) return;
        try {
            const data = await trainingScenariosApi.getDataAvailability(scenarioId);
            setDataAvailability(data);
        } catch (err) {
            console.error("Failed to fetch data availability:", err);
        }
    }, [scenarioId]);

    useEffect(() => {
        fetchScenario();
    }, [fetchScenario]);

    useEffect(() => {
        if (scenario?.status === "processed" || scenario?.status === "completed") {
            fetchGroupsPreview();
            fetchDataAvailability();
        }
    }, [scenario?.status, fetchGroupsPreview, fetchDataAvailability]);

    const updateConfig = (updates: Partial<ExportConfig>) => {
        setConfig(prev => ({ ...prev, ...updates }));
    };

    const handleCreateAndGenerate = async () => {
        setCreating(true);
        try {
            const dto: TrainingExportCreateDTO = {
                name: config.name || undefined,
                splitting_config: {
                    strategy: config.strategy,
                    group_by: config.group_by,
                    ratios: config.ratios,
                    stratify_by: config.stratify_by,
                    num_bins: config.num_bins,
                    time_slots: config.time_slots,
                    n_folds: config.n_folds,
                    internal_val_ratio: config.internal_val_ratio,
                    imbalance_drop_rate: config.imbalance_drop_rate,
                    imbalance_drop_label: config.imbalance_drop_label,
                    novelty_target_label: config.novelty_target_label,
                },
                preprocessing_config: {
                    missing_values_strategy: config.missing_values_strategy,
                    normalization: config.normalization,
                },
                output_config: {
                    format: config.format,
                },
            };

            await trainingScenariosApi.createExport(scenarioId, dto);
            toast({ title: "Generate dataset started" });
            router.push(`/scenarios/${scenarioId}/export`);
        } catch (err) {
            console.error("Failed to create export:", err);
            toast({ variant: "destructive", title: "Failed to create export" });
        } finally {
            setCreating(false);
        }
    };

    // Validation
    const getConfigValidationError = (): string | null => {
        const requiresGroupBy = checkRequiresGroupBy(config.strategy);
        const groupCount = groupsPreview?.groups?.length || 0;

        if (requiresGroupBy && config.strategy === STRATEGY.L1GO_CV && groupCount < 3) {
            return `L1GO CV requires at least 3 groups. Current: ${groupCount}.`;
        }
        if (requiresGroupBy && config.strategy === STRATEGY.L2GO_CV && groupCount < 4) {
            return `L2GO CV requires at least 4 groups. Current: ${groupCount}.`;
        }
        return null;
    };

    const validationError = getConfigValidationError();

    if (loading) {
        return (
            <div className="flex min-h-[400px] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    const canCreate = scenario?.status === "processed" || scenario?.status === "completed";

    if (!canCreate) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>Create Export</CardTitle>
                    <CardDescription>Complete processing phase first</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="p-8 border rounded-lg bg-muted/50 flex flex-col items-center gap-4">
                        <AlertTriangle className="h-12 w-12 text-amber-500" />
                        <p className="text-muted-foreground text-center">
                            Dataset export requires the processing phase to be completed.
                        </p>
                        <Badge variant="outline">Current status: {scenario?.status}</Badge>
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col gap-4">
                <div className="flex items-center gap-4">
                    <Button
                        variant="ghost"
                        size="sm"
                        className="pl-0 hover:bg-transparent"
                        onClick={() => router.push(`/scenarios/${scenarioId}/export`)}
                    >
                        <ChevronLeft className="h-4 w-4 mr-1" />
                        Back
                    </Button>
                    <div>
                        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
                            <Settings className="h-6 w-6" />
                            Create New Export
                        </h1>
                        <p className="text-muted-foreground">
                            Configure preprocessing, splitting, and output format
                        </p>
                    </div>
                </div>

                {/* Data Availability Indicator */}
                <DataAvailabilityIndicator className="ml-1" dataAvailability={dataAvailability} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Left Column: General Config & Preprocessing */}
                <div className="lg:col-span-4 space-y-6">
                    {/* General Details Card */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">General Configuration</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label>Export Name</Label>
                                <Input
                                    placeholder="e.g., Python L1GO Test"
                                    value={config.name}
                                    onChange={(e) => updateConfig({ name: e.target.value })}
                                />
                                <p className="text-[11px] text-muted-foreground">
                                    Leave empty for auto-generated name
                                </p>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Preprocessing */}
                    <PreprocessingSection config={config} updateConfig={updateConfig} />

                    {/* Output Format */}
                    <OutputFormatSection config={config} updateConfig={updateConfig} />
                </div>

                {/* Right Column: Splitting Strategy */}
                <div className="lg:col-span-8">
                    <SplittingStrategySection
                        config={config}
                        updateConfig={updateConfig}
                        groupsPreview={groupsPreview}
                        loadingGroups={loadingGroups}
                        fetchGroupsPreview={fetchGroupsPreview}
                        validationError={validationError}
                    />
                </div>
            </div>

            {/* Generate Button */}
            <Button
                className="w-full h-12 text-lg bg-green-600 hover:bg-green-700 text-white"
                onClick={handleCreateAndGenerate}
                disabled={creating || !!validationError}
            >
                {creating ? (
                    <>
                        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                        Creating...
                    </>
                ) : (
                    <>
                        <Play className="mr-2 h-5 w-5" />
                        Generate Dataset
                    </>
                )}
            </Button>
        </div>
    );
}
