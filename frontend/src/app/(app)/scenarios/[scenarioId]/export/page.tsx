"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, useCallback, useMemo } from "react";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, Play, Settings, AlertTriangle } from "lucide-react";
import {
    trainingScenariosApi,
    TrainingDatasetSplitRecord,
    TrainingExportRecord,
    TrainingScenarioRecord,
} from "@/lib/api/training-scenarios";
import { toast } from "@/components/ui/use-toast";
import { useSSE } from "@/contexts/sse-context";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import {
    PreprocessingSection,
    SplittingStrategySection,
    OutputFormatSection,
    DatasetSummarySection,
    NotReadyState,
    GeneratingState,
    LoadingState,
    ExportConfig,
    GroupPreview,
    DEFAULT_CONFIG,
    STRATEGY_OPTIONS,
    STRATEGY,
    isCVStrategy,
    getStrategyOption,
} from "./_components";

// =============================================================================
// Component
// =============================================================================

export default function ScenarioExportPage() {
    const params = useParams<{ scenarioId: string }>();
    const router = useRouter();
    const scenarioId = params.scenarioId;
    const { subscribe } = useSSE();

    const [scenario, setScenario] = useState<TrainingScenarioRecord | null>(null);
    const [exports, setExports] = useState<TrainingExportRecord[]>([]);
    const [splits, setSplits] = useState<TrainingDatasetSplitRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [config, setConfig] = useState<ExportConfig>(DEFAULT_CONFIG);
    const [groupsPreview, setGroupsPreview] = useState<GroupPreview | null>(null);
    const [loadingGroups, setLoadingGroups] = useState(false);

    // =============================================================================
    // Derived State
    // =============================================================================

    const canGenerate = scenario?.status === "processed" || scenario?.status === "completed";
    const hasExports = exports.length > 0;
    const latestExport = exports[0];
    const isExportGenerating = latestExport?.status === "generating";
    const isExportCompleted = latestExport?.status === "completed";

    // =============================================================================
    // Data Fetching
    // =============================================================================

    const fetchScenario = useCallback(async () => {
        try {
            const data = await trainingScenariosApi.get(scenarioId);
            setScenario(data);
            return data;
        } catch (err) {
            console.error("Failed to fetch scenario:", err);
            return null;
        }
    }, [scenarioId]);

    const fetchExports = useCallback(async () => {
        try {
            const data = await trainingScenariosApi.listExports(scenarioId);
            setExports(data.items);

            // If there's a completed export, fetch its splits
            const completedExport = data.items.find(e => e.status === "completed");
            if (completedExport) {
                const splitsData = await trainingScenariosApi.getExportSplits(
                    scenarioId,
                    completedExport.id
                );
                setSplits(splitsData);
            } else {
                setSplits([]);
            }
        } catch (err) {
            console.error("Failed to fetch exports:", err);
        }
    }, [scenarioId]);

    const fetchGroupsPreview = useCallback(async () => {
        if (!scenarioId) return;

        // Check if current strategy requires group preview
        const currentStrategy = STRATEGY_OPTIONS.find((s) => s.value === config.strategy);
        if (!currentStrategy?.requiresGroupBy) {
            setGroupsPreview(null);
            return;
        }

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
    }, [scenarioId, config.strategy, config.group_by, config.num_bins, config.time_slots]);

    const loadData = useCallback(async () => {
        setLoading(true);
        await Promise.all([fetchScenario(), fetchExports()]);
        setLoading(false);
    }, [fetchScenario, fetchExports]);

    // =============================================================================
    // Effects
    // =============================================================================

    useEffect(() => {
        loadData();
    }, [loadData]);

    // Fetch groups preview when group config changes
    useEffect(() => {
        if (scenario?.status === "processed") {
            fetchGroupsPreview();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [scenario?.status, config.strategy, config.group_by, config.num_bins, config.time_slots]);

    // Subscribe to SSE for real-time updates
    useEffect(() => {
        const unsubscribe = subscribe("SCENARIO_UPDATE", (data: { scenario_id?: string }) => {
            if (data.scenario_id === scenarioId) {
                fetchScenario();
                fetchExports();
            }
        });
        return () => unsubscribe();
    }, [subscribe, scenarioId, fetchScenario, fetchExports]);

    // Poll while any export is generating
    useEffect(() => {
        const hasGenerating = exports.some(e => e.status === "generating");
        if (!hasGenerating) return;

        const interval = setInterval(() => {
            fetchExports();
        }, 3000);

        return () => clearInterval(interval);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [scenario?.status]);

    // =============================================================================
    // Handlers
    // =============================================================================

    const handleGenerateDataset = async () => {
        setGenerating(true);
        try {
            // Build splitting config from UI state
            const splittingConfig = {
                strategy: config.strategy,
                group_by: config.group_by,
                num_bins: config.num_bins,
                time_slots: config.time_slots,
                n_folds: config.n_folds,
                ratios: config.ratios,
            };

            // Build preprocessing config
            const preprocessingConfig = {
                missing_values_strategy: config.missing_values_strategy,
                normalization: config.normalization,
            };

            // Build output config
            const outputConfig = {
                format: config.format,
                include_metadata: config.include_metadata,
            };

            await trainingScenariosApi.createExport(scenarioId, {
                name: `Export ${new Date().toISOString().split("T")[0]}`,
                splitting_config: splittingConfig,
                preprocessing_config: preprocessingConfig,
                output_config: outputConfig,
            });

            toast({ title: "Dataset generation started" });
            await fetchExports();
        } catch (err) {
            console.error("Failed to generate dataset:", err);
            toast({ variant: "destructive", title: "Failed to generate dataset" });
        } finally {
            setGenerating(false);
        }
    };

    const updateConfig = useCallback((updates: Partial<ExportConfig>) => {
        setConfig((prev) => ({ ...prev, ...updates }));
    }, []);

    const updateRatios = useCallback((key: "train" | "val" | "test", value: number) => {
        setConfig((prev) => {
            const newRatios = { ...prev.ratios, [key]: value };
            // Auto-adjust other values to sum to 1
            const total = newRatios.train + newRatios.val + newRatios.test;
            if (total > 1) {
                const other = key === "train" ? "val" : "train";
                newRatios[other] = Math.max(0, newRatios[other] - (total - 1));
            }
            return { ...prev, ratios: newRatios };
        });
    }, []);

    // =============================================================================
    // Validation
    // =============================================================================

    const getConfigValidationError = useCallback((): string | null => {
        const groupCount = groupsPreview?.groups?.length || 0;
        const currentStrategyOption = getStrategyOption(config.strategy);
        const isCV = isCVStrategy(config.strategy);

        // Check if strategy requires grouping and has minimum group requirement
        if (currentStrategyOption?.requiresGroupBy && currentStrategyOption?.minGroups) {
            if (groupCount < currentStrategyOption.minGroups) {
                return `${currentStrategyOption.label} requires at least ${currentStrategyOption.minGroups} groups. Current: ${groupCount}. Try different grouping.`;
            }
        }

        // Validate ratios sum to ~1.0 for non-CV strategies
        if (!isCV) {
            const ratioSum = config.ratios.train + config.ratios.val + config.ratios.test;
            if (ratioSum < 0.95 || ratioSum > 1.05) {
                return `Train/Val/Test ratios must sum to 100%. Current: ${(ratioSum * 100).toFixed(0)}%`;
            }
        }

        // Imbalanced K-Fold: warn if n_folds is too high
        if (config.strategy === STRATEGY.IMBALANCED_KFOLD_CV && config.n_folds > 20) {
            return `Number of folds should be ≤20 for practical K-Fold CV`;
        }

        return null;
    }, [config, groupsPreview]);

    const validationError = getConfigValidationError();

    // =============================================================================
    // Render States
    // =============================================================================

    if (loading) {
        return <LoadingState />;
    }

    // Not ready for export (features not done)
    if (!canGenerate) {
        return (
            <NotReadyState
                status={scenario?.status}
                isProcessing={scenario?.status === "processing"}
                buildsExtracted={scenario?.builds_features_extracted}
                buildsTotal={scenario?.builds_total}
            />
        );
    }

    // Generating state
    if (isExportGenerating) {
        return <GeneratingState />;
    }

    // Show completed exports
    if (hasExports && isExportCompleted && splits.length > 0) {
        return (
            <DatasetSummarySection
                scenarioId={scenarioId}
                splits={splits}
                onRegenerate={() => {
                    setExports([]);
                    setSplits([]);
                }}
            />
        );
    }

    // =============================================================================
    // Configuration UI (ready to generate)
    // =============================================================================

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Settings className="h-5 w-5" />
                        Export Configuration
                    </CardTitle>
                    <CardDescription>
                        Configure preprocessing, splitting, and output format
                    </CardDescription>
                </CardHeader>
            </Card>

            <PreprocessingSection config={config} updateConfig={updateConfig} />

            <SplittingStrategySection
                config={config}
                updateConfig={updateConfig}
                updateRatios={updateRatios}
                groupsPreview={groupsPreview}
                loadingGroups={loadingGroups}
                fetchGroupsPreview={fetchGroupsPreview}
                validationError={validationError}
            />

            <OutputFormatSection config={config} updateConfig={updateConfig} />

            {/* Generate Button */}
            <Card>
                <CardContent className="pt-6">
                    <Button
                        size="lg"
                        className="w-full bg-green-600 hover:bg-green-700"
                        onClick={handleGenerateDataset}
                        disabled={generating || !!validationError}
                    >
                        {generating ? (
                            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                        ) : (
                            <Play className="mr-2 h-5 w-5" />
                        )}
                        Generate Dataset
                    </Button>
                </CardContent>
            </Card>
        </div>
    );
}
