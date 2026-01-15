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
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { ChevronLeft, Loader2, Play, RefreshCw, AlertTriangle, Settings } from "lucide-react";
import {
    trainingScenariosApi,
    TrainingScenarioRecord,
    TrainingExportCreateDTO,
} from "@/lib/api/training-scenarios";
import { toast } from "@/components/ui/use-toast";
import { RatioSlider } from "@/components/ui/ratio-slider";

// =============================================================================
// Constants
// =============================================================================

const STRATEGY = {
    STRATIFIED_WITHIN_GROUP: "stratified_within_group",
    RANDOM_SPLIT: "random_split",
    TIME_SERIES_SPLIT: "time_series_split",
    L1GO_CV: "l1go_cv",
    L2GO_CV: "l2go_cv",
    EXTREME_NOVELTY_CV: "extreme_novelty_cv",
    IMBALANCED_KFOLD_CV: "imbalanced_kfold_cv",
} as const;

const GROUP_BY = {
    REPO_LANGUAGE: "repo_language",
    TIME_OF_DAY: "time_of_day",
    PERCENTAGE_OF_BUILDS_BEFORE: "percentage_of_builds_before",
    NUMBER_OF_BUILDS_BEFORE: "number_of_builds_before",
} as const;

const MISSING_VALUES_OPTIONS = [
    { value: "drop_row", label: "Drop Row" },
    { value: "fill_mean", label: "Fill with Mean" },
    { value: "fill_median", label: "Fill with Median" },
    { value: "fill_zero", label: "Fill with Zero" },
];

const NORMALIZATION_OPTIONS = [
    { value: "none", label: "None" },
    { value: "z_score", label: "Z-Score (StandardScaler)" },
    { value: "min_max", label: "Min-Max (0-1)" },
    { value: "robust", label: "Robust (IQR)" },
];

const STRATEGY_OPTIONS = [
    { value: "stratified_within_group", label: "Stratified Within Group", requiresGroupBy: true },
    { value: "random_split", label: "Random Split", requiresGroupBy: false },
    { value: "time_series_split", label: "Time Series Split", requiresGroupBy: false },
    { value: "l1go_cv", label: "L1GO Cross-Validation", requiresGroupBy: true },
    { value: "l2go_cv", label: "L2GO Cross-Validation", requiresGroupBy: true },
    { value: "extreme_novelty_cv", label: "Extreme Novelty CV", requiresGroupBy: true },
    { value: "imbalanced_kfold_cv", label: "Imbalanced K-Fold CV", requiresGroupBy: false },
];

const GROUP_BY_OPTIONS = [
    { value: "repo_language", label: "Language" },
    { value: "time_of_day", label: "Time of Day" },
    { value: "percentage_of_builds_before", label: "% of Builds Before" },
    { value: "number_of_builds_before", label: "# of Builds Before" },
];

const LABEL_OPTIONS = [
    { value: 0, label: "Success (0)" },
    { value: 1, label: "Failure (1)" },
];

// =============================================================================
// Types
// =============================================================================

interface ExportConfig {
    name: string;
    missing_values_strategy: string;
    normalization: string;
    strategy: string;
    group_by: string;
    ratios: { train: number; val: number; test: number };
    num_bins: number;
    time_slots: number;
    n_folds: number;
    internal_val_ratio: number;
    imbalance_drop_rate: number;
    imbalance_drop_label: number;
    novelty_target_label: number;
    format: string;
}

const DEFAULT_CONFIG: ExportConfig = {
    name: "",
    missing_values_strategy: "drop_row",
    normalization: "z_score",
    strategy: "stratified_within_group",
    group_by: "repo_language",
    ratios: { train: 0.7, val: 0.15, test: 0.15 },
    num_bins: 4,
    time_slots: 4,
    n_folds: 5,
    internal_val_ratio: 0.2,
    imbalance_drop_rate: 0.5,
    imbalance_drop_label: 1,
    novelty_target_label: 1,
    format: "parquet",
};

// =============================================================================
// Component
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
            toast({ title: "Export created and generation started" });
            router.push(`/scenarios/${scenarioId}/export`);
        } catch (err) {
            console.error("Failed to create export:", err);
            toast({ variant: "destructive", title: "Failed to create export" });
        } finally {
            setCreating(false);
        }
    };

    // Determine strategy requirements
    const currentStrategyOption = STRATEGY_OPTIONS.find(s => s.value === config.strategy);
    const requiresGroupBy = currentStrategyOption?.requiresGroupBy ?? true;

    // Validation
    const getConfigValidationError = (): string | null => {
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

    const isCVStrategy = [
        STRATEGY.L1GO_CV,
        STRATEGY.L2GO_CV,
        STRATEGY.EXTREME_NOVELTY_CV
    ].includes(config.strategy as any);

    const showNumBins = requiresGroupBy && (
        [GROUP_BY.PERCENTAGE_OF_BUILDS_BEFORE, GROUP_BY.NUMBER_OF_BUILDS_BEFORE] as string[]
    ).includes(config.group_by);
    const showTimeSlots = requiresGroupBy && config.group_by === GROUP_BY.TIME_OF_DAY;

    if (loading) {
        return (
            <div className="flex min-h-[400px] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    const canCreate = scenario?.status === "processed" || scenario?.status === "completed";

    // Helper for score colors
    const getScoreColor = (score: number | undefined | null) => {
        const val = score ?? 0;
        if (val >= 90) return 'text-green-600 dark:text-green-500';
        if (val >= 70) return 'text-yellow-600 dark:text-yellow-500';
        return 'text-red-600 dark:text-red-500';
    };

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
                {dataAvailability && (
                    <div className="flex flex-wrap items-center gap-6 text-sm ml-1">
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
                )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Left Column: General Config & Preprocessing */}
                <div className="lg:col-span-4 space-y-6">
                    <Card className="h-full">
                        <CardHeader>
                            <CardTitle className="text-lg">General Configuration</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            {/* Export Name */}
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

                            {/* Output Format */}
                            <div className="space-y-2">
                                <Label>Output Format</Label>
                                <Select
                                    value={config.format}
                                    onValueChange={(v) => updateConfig({ format: v })}
                                >
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="parquet">Parquet (recommended)</SelectItem>
                                        <SelectItem value="csv">CSV</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="border-t my-4" />

                            {/* Preprocessing */}
                            <div className="space-y-4">
                                <Label className="text-base font-medium">Preprocessing</Label>
                                <div className="space-y-4">
                                    <div className="space-y-2">
                                        <Label className="text-sm text-muted-foreground">Missing Values</Label>
                                        <Select
                                            value={config.missing_values_strategy}
                                            onValueChange={(v) => updateConfig({ missing_values_strategy: v })}
                                        >
                                            <SelectTrigger>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {MISSING_VALUES_OPTIONS.map(opt => (
                                                    <SelectItem key={opt.value} value={opt.value}>
                                                        {opt.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="space-y-2">
                                        <Label className="text-sm text-muted-foreground">Normalization</Label>
                                        <Select
                                            value={config.normalization}
                                            onValueChange={(v) => updateConfig({ normalization: v })}
                                        >
                                            <SelectTrigger>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {NORMALIZATION_OPTIONS.map(opt => (
                                                    <SelectItem key={opt.value} value={opt.value}>
                                                        {opt.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Right Column: Splitting Strategy */}
                <div className="lg:col-span-8">
                    <Card className="h-full">
                        <CardHeader>
                            <CardTitle className="text-lg">Splitting Strategy</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <div className="grid gap-6 md:grid-cols-2">
                                <div className="space-y-2">
                                    <Label>Strategy</Label>
                                    <Select
                                        value={config.strategy}
                                        onValueChange={(v) => updateConfig({ strategy: v })}
                                    >
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {STRATEGY_OPTIONS.map(opt => (
                                                <SelectItem key={opt.value} value={opt.value}>
                                                    {opt.label}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>

                                <div className="space-y-2">
                                    <Label className={!requiresGroupBy ? "text-muted-foreground" : ""}>Group By</Label>
                                    {requiresGroupBy ? (
                                        <Select
                                            value={config.group_by}
                                            onValueChange={(v) => updateConfig({ group_by: v })}
                                        >
                                            <SelectTrigger>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {GROUP_BY_OPTIONS.map(opt => (
                                                    <SelectItem key={opt.value} value={opt.value}>
                                                        {opt.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    ) : (
                                        <div className="p-2 h-10 border rounded-md bg-muted/50 text-sm text-muted-foreground flex items-center px-3">
                                            Not applicable for this strategy
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Dynamic Binning Options */}
                            {(showNumBins || showTimeSlots) && (
                                <div className="space-y-4 pt-4 border-t">
                                    <Label>Grouping Configuration</Label>
                                    <div className="grid gap-6 md:grid-cols-2">
                                        {showNumBins && (
                                            <div className="space-y-2">
                                                <div className="flex justify-between">
                                                    <span className="text-sm text-muted-foreground">Number of Bins</span>
                                                    <span className="text-sm font-medium">{config.num_bins}</span>
                                                </div>
                                                <Slider
                                                    value={[config.num_bins]}
                                                    onValueChange={([v]: number[]) => updateConfig({ num_bins: v })}
                                                    min={2}
                                                    max={10}
                                                    step={1}
                                                />
                                            </div>
                                        )}
                                        {showTimeSlots && (
                                            <div className="space-y-2">
                                                <div className="flex justify-between">
                                                    <span className="text-sm text-muted-foreground">Time Slots</span>
                                                    <span className="text-sm font-medium">{config.time_slots}</span>
                                                </div>
                                                <Slider
                                                    value={[config.time_slots]}
                                                    onValueChange={([v]: number[]) => updateConfig({ time_slots: v })}
                                                    min={2}
                                                    max={12}
                                                    step={1}
                                                />
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* Groups Preview - Only show if grouping is required */}
                            {requiresGroupBy && groupsPreview && (
                                <div className="space-y-4 pt-4 border-t">
                                    <div className="flex items-center justify-between">
                                        <Label>Available Groups ({groupsPreview.groups.length})</Label>
                                        <Button variant="ghost" size="sm" onClick={fetchGroupsPreview} disabled={loadingGroups}>
                                            {loadingGroups ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                                        </Button>
                                    </div>
                                    <div className="border rounded-lg overflow-hidden max-h-[300px] overflow-y-auto">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Group</TableHead>
                                                    <TableHead className="text-right">Count</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {groupsPreview.groups.map(g => (
                                                    <TableRow key={g.value}>
                                                        <TableCell className="font-medium">{g.label || g.value}</TableCell>
                                                        <TableCell className="text-right">
                                                            {g.count.toLocaleString()}
                                                            {g.warning && <Badge variant="outline" className="ml-2 text-xs">Small</Badge>}
                                                        </TableCell>
                                                    </TableRow>
                                                ))}
                                            </TableBody>
                                        </Table>
                                    </div>
                                </div>
                            )}

                            {/* CV Configuration */}
                            {isCVStrategy && (
                                <div className="space-y-4 pt-4 border-t">
                                    <Label>Cross-Validation Settings</Label>
                                    <div className="space-y-2">
                                        <div className="flex justify-between">
                                            <span className="text-sm text-muted-foreground">Internal Validation Ratio</span>
                                            <span className="text-sm font-medium">{(config.internal_val_ratio * 100).toFixed(0)}%</span>
                                        </div>
                                        <Slider
                                            value={[config.internal_val_ratio * 100]}
                                            onValueChange={([v]: number[]) => updateConfig({ internal_val_ratio: v / 100 })}
                                            min={5}
                                            max={50}
                                            step={5}
                                        />
                                    </div>
                                </div>
                            )}

                            {/* Imbalanced K-Fold */}
                            {config.strategy === STRATEGY.IMBALANCED_KFOLD_CV && (
                                <div className="space-y-4 pt-4 border-t">
                                    <Label>Imbalanced K-Fold Configuration</Label>
                                    <div className="grid gap-4 md:grid-cols-2">
                                        <div className="space-y-2">
                                            <div className="flex justify-between">
                                                <span className="text-sm text-muted-foreground">Number of Folds</span>
                                                <span className="text-sm font-medium">{config.n_folds}</span>
                                            </div>
                                            <Slider
                                                value={[config.n_folds]}
                                                onValueChange={([v]: number[]) => updateConfig({ n_folds: v })}
                                                min={2}
                                                max={20}
                                                step={1}
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <div className="flex justify-between">
                                                <span className="text-sm text-muted-foreground">Label Drop Rate</span>
                                                <span className="text-sm font-medium">{(config.imbalance_drop_rate * 100).toFixed(0)}%</span>
                                            </div>
                                            <Slider
                                                value={[config.imbalance_drop_rate * 100]}
                                                onValueChange={([v]: number[]) => updateConfig({ imbalance_drop_rate: v / 100 })}
                                                min={0}
                                                max={90}
                                                step={10}
                                            />
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Ratios for non-CV strategies */}
                            {!isCVStrategy && (
                                <div className="space-y-4 pt-4 border-t">
                                    <Label>Train / Validation / Test Ratios</Label>
                                    <RatioSlider
                                        ratios={config.ratios}
                                        onChange={(newRatios) => updateConfig({ ratios: newRatios })}
                                    />
                                </div>
                            )}

                            {/* Validation Error */}
                            {validationError && (
                                <div className="p-3 border border-amber-500 bg-amber-50 dark:bg-amber-950/20 rounded-lg flex items-center gap-2">
                                    <AlertTriangle className="h-4 w-4 text-amber-500" />
                                    <span className="text-sm text-amber-700 dark:text-amber-400">{validationError}</span>
                                </div>
                            )}
                        </CardContent>
                    </Card>
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
