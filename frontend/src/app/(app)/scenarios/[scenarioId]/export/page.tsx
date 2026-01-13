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
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Download, Loader2, Play, RefreshCw, AlertTriangle, Settings } from "lucide-react";
import {
    trainingScenariosApi,
    TrainingDatasetSplitRecord,
    TrainingScenarioRecord,
} from "@/lib/api/training-scenarios";
import { formatBytes } from "@/lib/utils";
import { toast } from "@/components/ui/use-toast";
import { useSSE } from "@/contexts/sse-context";

// =============================================================================
// Types
// =============================================================================

interface ExportConfig {
    // Preprocessing
    missing_values_strategy: "drop_row" | "fill_mean" | "fill_median" | "fill_zero";
    normalization: "none" | "z_score" | "min_max" | "robust";
    // Splitting
    strategy: string;
    group_by: string;
    ratios: { train: number; val: number; test: number };
    // Output
    format: "parquet" | "csv";
    include_metadata: boolean;
}

const DEFAULT_CONFIG: ExportConfig = {
    missing_values_strategy: "drop_row",
    normalization: "z_score",
    strategy: "stratified_within_group",
    group_by: "repo_language",
    ratios: { train: 0.7, val: 0.15, test: 0.15 },
    format: "parquet",
    include_metadata: true,
};

// =============================================================================
// Constants
// =============================================================================

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
    { value: "stratified_within_group", label: "Stratified Within Group" },
    { value: "random_split", label: "Random Split" },
    { value: "leave_one_out", label: "Leave One Out" },
    { value: "leave_two_out", label: "Leave Two Out" },
];

const GROUP_BY_OPTIONS = [
    { value: "repo_language", label: "Language" },
    { value: "time_of_day", label: "Time of Day" },
    { value: "percentage_of_builds_before", label: "% of Builds Before" },
    { value: "number_of_builds_before", label: "# of Builds Before" },
];

// =============================================================================
// Component
// =============================================================================

export default function ScenarioExportPage() {
    const params = useParams<{ scenarioId: string }>();
    const scenarioId = params.scenarioId;
    const { subscribe } = useSSE();

    const [scenario, setScenario] = useState<TrainingScenarioRecord | null>(null);
    const [splits, setSplits] = useState<TrainingDatasetSplitRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [config, setConfig] = useState<ExportConfig>(DEFAULT_CONFIG);

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

    const fetchSplits = useCallback(async () => {
        try {
            const data = await trainingScenariosApi.getSplits(scenarioId);
            setSplits(data);
        } catch (err) {
            console.error("Failed to fetch splits:", err);
        }
    }, [scenarioId]);

    const loadData = useCallback(async () => {
        setLoading(true);
        await Promise.all([fetchScenario(), fetchSplits()]);
        setLoading(false);
    }, [fetchScenario, fetchSplits]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    // Subscribe to SSE for real-time updates
    useEffect(() => {
        const unsubscribe = subscribe("SCENARIO_UPDATE", (data: { scenario_id?: string }) => {
            if (data.scenario_id === scenarioId) {
                fetchScenario();
                fetchSplits();
            }
        });
        return () => unsubscribe();
    }, [subscribe, scenarioId, fetchScenario, fetchSplits]);

    // Poll while generating
    useEffect(() => {
        if (!scenario || scenario.status !== "splitting") return;

        const interval = setInterval(() => {
            fetchScenario();
            fetchSplits();
        }, 3000);

        return () => clearInterval(interval);
    }, [scenario?.status, fetchScenario, fetchSplits]);

    const handleGenerateDataset = async () => {
        setGenerating(true);
        try {
            // TODO: Pass config to backend when API is updated
            await trainingScenariosApi.generateDataset(scenarioId);
            toast({ title: "Dataset generation started" });
            await fetchScenario();
        } catch (err) {
            console.error("Failed to generate dataset:", err);
            toast({ variant: "destructive", title: "Failed to generate dataset" });
        } finally {
            setGenerating(false);
        }
    };

    const updateConfig = (updates: Partial<ExportConfig>) => {
        setConfig(prev => ({ ...prev, ...updates }));
    };

    const updateRatios = (key: "train" | "val" | "test", value: number) => {
        const newRatios = { ...config.ratios, [key]: value };
        // Auto-adjust other values to sum to 1
        const total = newRatios.train + newRatios.val + newRatios.test;
        if (total > 1) {
            const other = key === "train" ? "val" : "train";
            newRatios[other] = Math.max(0, newRatios[other] - (total - 1));
        }
        setConfig(prev => ({ ...prev, ratios: newRatios }));
    };

    if (loading) {
        return (
            <div className="flex min-h-[400px] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    const canGenerate = scenario?.status === "processed";
    const isGenerating = scenario?.status === "splitting" || generating;
    const isCompleted = scenario?.status === "completed";
    const hasSplits = splits.length > 0;

    // Not ready for export
    if (!canGenerate && !isCompleted && !isGenerating) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>Export Dataset</CardTitle>
                    <CardDescription>Complete processing phase first</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="p-8 border rounded-lg bg-muted/50 flex flex-col items-center gap-4">
                        <AlertTriangle className="h-12 w-12 text-amber-500" />
                        <p className="text-muted-foreground text-center">
                            Dataset export requires the processing phase to be completed.
                        </p>
                        <Badge variant="outline" className="text-sm">
                            Current status: {scenario?.status}
                        </Badge>
                    </div>
                </CardContent>
            </Card>
        );
    }

    // Show existing splits (completed)
    if (hasSplits) {
        const totalRecords = splits.reduce((sum, s) => sum + s.record_count, 0);
        const totalSize = splits.reduce((sum, s) => sum + s.file_size_bytes, 0);

        return (
            <div className="space-y-6">
                {/* Summary Card */}
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between">
                        <div>
                            <CardTitle>Dataset Summary</CardTitle>
                            <CardDescription>Generated splits ready for download</CardDescription>
                        </div>
                        <div className="flex gap-2">
                            <Button variant="outline" size="sm" asChild>
                                <a href={`/api/training-scenarios/${scenarioId}/splits/download-all?file_format=parquet`}>
                                    <Download className="mr-2 h-4 w-4" />
                                    All (Parquet)
                                </a>
                            </Button>
                            <Button variant="outline" size="sm" asChild>
                                <a href={`/api/training-scenarios/${scenarioId}/splits/download-all?file_format=csv`}>
                                    <Download className="mr-2 h-4 w-4" />
                                    All (CSV)
                                </a>
                            </Button>
                            <Button variant="outline" size="sm" onClick={() => setSplits([])}>
                                <RefreshCw className="mr-2 h-4 w-4" />
                                Regenerate
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="grid gap-4 md:grid-cols-4">
                            <div className="p-4 border rounded-lg">
                                <p className="text-sm text-muted-foreground">Total Splits</p>
                                <p className="text-2xl font-bold">{splits.length}</p>
                            </div>
                            <div className="p-4 border rounded-lg">
                                <p className="text-sm text-muted-foreground">Total Records</p>
                                <p className="text-2xl font-bold">{totalRecords.toLocaleString()}</p>
                            </div>
                            <div className="p-4 border rounded-lg">
                                <p className="text-sm text-muted-foreground">Features</p>
                                <p className="text-2xl font-bold">{splits[0]?.feature_count || 0}</p>
                            </div>
                            <div className="p-4 border rounded-lg">
                                <p className="text-sm text-muted-foreground">Total Size</p>
                                <p className="text-2xl font-bold">{formatBytes(totalSize)}</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Splits Table */}
                <Card>
                    <CardHeader>
                        <CardTitle>Split Files</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Split</TableHead>
                                    <TableHead>Records</TableHead>
                                    <TableHead>Features</TableHead>
                                    <TableHead>Size</TableHead>
                                    <TableHead>Format</TableHead>
                                    <TableHead className="text-right">Action</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {splits.map((split) => (
                                    <TableRow key={split.id}>
                                        <TableCell>
                                            <Badge variant="outline" className="capitalize">
                                                {split.split_type}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>{split.record_count.toLocaleString()}</TableCell>
                                        <TableCell>{split.feature_count}</TableCell>
                                        <TableCell>{formatBytes(split.file_size_bytes)}</TableCell>
                                        <TableCell>
                                            <Badge variant="secondary">{split.file_format.toUpperCase()}</Badge>
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <Button size="sm" variant="outline" asChild>
                                                <a href={`/api/training-scenarios/${scenarioId}/splits/${split.id}/download`}>
                                                    <Download className="mr-2 h-4 w-4" />
                                                    Download
                                                </a>
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>
            </div>
        );
    }

    // Generating state
    if (isGenerating) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>Generating Dataset</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="p-8 border rounded-lg bg-muted/50 flex flex-col items-center gap-4">
                        <Loader2 className="h-12 w-12 animate-spin text-purple-500" />
                        <p className="text-muted-foreground text-center">
                            Generating train/val/test splits...
                        </p>
                        <p className="text-xs text-muted-foreground">
                            This may take a few minutes depending on the number of builds.
                        </p>
                    </div>
                </CardContent>
            </Card>
        );
    }

    // Configuration UI (ready to generate)
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

            {/* Section 1: Preprocessing */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">1. Preprocessing</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid gap-6 md:grid-cols-2">
                        <div className="space-y-2">
                            <Label>Missing Values Strategy</Label>
                            <Select
                                value={config.missing_values_strategy}
                                onValueChange={(v) => updateConfig({ missing_values_strategy: v as any })}
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
                            <Label>Normalization</Label>
                            <Select
                                value={config.normalization}
                                onValueChange={(v) => updateConfig({ normalization: v as any })}
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
                </CardContent>
            </Card>

            {/* Section 2: Splitting Strategy */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">2. Splitting Strategy</CardTitle>
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
                            <Label>Group By</Label>
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
                        </div>
                    </div>

                    {/* Ratios */}
                    <div className="space-y-4 pt-4 border-t">
                        <Label>Train / Validation / Test Ratios</Label>
                        <div className="grid gap-4 md:grid-cols-3">
                            <div className="space-y-2">
                                <div className="flex justify-between">
                                    <span className="text-sm text-muted-foreground">Train</span>
                                    <span className="text-sm font-medium">{(config.ratios.train * 100).toFixed(0)}%</span>
                                </div>
                                <Slider
                                    value={[config.ratios.train * 100]}
                                    onValueChange={([v]) => updateRatios("train", v / 100)}
                                    min={10}
                                    max={90}
                                    step={5}
                                />
                            </div>
                            <div className="space-y-2">
                                <div className="flex justify-between">
                                    <span className="text-sm text-muted-foreground">Validation</span>
                                    <span className="text-sm font-medium">{(config.ratios.val * 100).toFixed(0)}%</span>
                                </div>
                                <Slider
                                    value={[config.ratios.val * 100]}
                                    onValueChange={([v]) => updateRatios("val", v / 100)}
                                    min={5}
                                    max={40}
                                    step={5}
                                />
                            </div>
                            <div className="space-y-2">
                                <div className="flex justify-between">
                                    <span className="text-sm text-muted-foreground">Test</span>
                                    <span className="text-sm font-medium">{(config.ratios.test * 100).toFixed(0)}%</span>
                                </div>
                                <Slider
                                    value={[config.ratios.test * 100]}
                                    onValueChange={([v]) => updateRatios("test", v / 100)}
                                    min={5}
                                    max={40}
                                    step={5}
                                />
                            </div>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Section 3: Output Format */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">3. Output Format</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid gap-6 md:grid-cols-2">
                        <div className="space-y-2">
                            <Label>File Format</Label>
                            <Select
                                value={config.format}
                                onValueChange={(v) => updateConfig({ format: v as "parquet" | "csv" })}
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
                        <div className="flex items-center gap-3 pt-6">
                            <Checkbox
                                id="include-metadata"
                                checked={config.include_metadata}
                                onCheckedChange={(v) => updateConfig({ include_metadata: !!v })}
                            />
                            <Label htmlFor="include-metadata" className="cursor-pointer">
                                Include Metadata (repo, commit, build_id)
                            </Label>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Generate Button */}
            <Card>
                <CardContent className="pt-6">
                    <Button
                        size="lg"
                        className="w-full bg-green-600 hover:bg-green-700"
                        onClick={handleGenerateDataset}
                        disabled={generating}
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
