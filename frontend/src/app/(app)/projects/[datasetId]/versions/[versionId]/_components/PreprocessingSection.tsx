"use client";

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
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    ChevronDown,
    ChevronUp,
    Settings2,
    ArrowRight,
    Loader2,
    RefreshCw,
    Sparkles,
    Hash,
    Binary,
    AlertTriangle,
    TrendingUp,
    Lock,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface PreprocessingSectionProps {
    datasetId: string;
    versionId: string;
    versionStatus: string;
}

interface NormalizationMethod {
    value: string;
    label: string;
    description: string;
}

interface PreviewRow {
    [key: string]: number | string | null;
}

const NORMALIZATION_METHODS: NormalizationMethod[] = [
    { value: "none", label: "None", description: "No transformation applied" },
    { value: "minmax", label: "Min-Max", description: "Scale to [0, 1] range" },
    { value: "zscore", label: "Z-Score", description: "Standardize to μ=0, σ=1" },
    { value: "robust", label: "Robust", description: "IQR-based scaling" },
    { value: "log", label: "Log", description: "Logarithmic transformation" },
];

export function PreprocessingSection({
    datasetId,
    versionId,
    versionStatus,
}: PreprocessingSectionProps) {
    // Section open states
    const [isNormalizationOpen, setIsNormalizationOpen] = useState(true);
    const [isEncodingOpen, setIsEncodingOpen] = useState(false);
    const [isMissingOpen, setIsMissingOpen] = useState(false);
    const [isOutlierOpen, setIsOutlierOpen] = useState(false);

    // Normalization state
    const [normMethod, setNormMethod] = useState("none");
    const [previewData, setPreviewData] = useState<PreviewRow[]>([]);
    const [previewFeatures, setPreviewFeatures] = useState<string[]>([]);
    const [isLoadingPreview, setIsLoadingPreview] = useState(false);

    const isVersionCompleted = versionStatus === "completed";

    const fetchNormalizationPreview = useCallback(async (method: string) => {
        if (!isVersionCompleted || method === "none") {
            setPreviewData([]);
            return;
        }

        setIsLoadingPreview(true);
        try {
            const res = await fetch(
                `${API_BASE}/datasets/${datasetId}/versions/${versionId}/preprocess/preview?method=${method}&limit=5`,
                { credentials: "include" }
            );
            if (res.ok) {
                const data = await res.json();
                setPreviewData(data.sample_data || []);
                setPreviewFeatures(data.selected_features?.slice(0, 4) || []);
            }
        } catch (err) {
            console.error("Failed to fetch normalization preview:", err);
        } finally {
            setIsLoadingPreview(false);
        }
    }, [datasetId, versionId, isVersionCompleted]);

    useEffect(() => {
        if (isNormalizationOpen && normMethod !== "none") {
            fetchNormalizationPreview(normMethod);
        }
    }, [isNormalizationOpen, normMethod, fetchNormalizationPreview]);

    const formatValue = (value: number | string | null): string => {
        if (value === null || value === undefined) return "—";
        if (typeof value === "number") {
            return Number.isInteger(value) ? value.toString() : value.toFixed(4);
        }
        return String(value);
    };

    if (!isVersionCompleted) {
        return (
            <Card>
                <CardContent className="py-12 text-center">
                    <Lock className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                    <p className="text-lg font-medium">Preprocessing Not Available</p>
                    <p className="text-sm text-muted-foreground mt-2">
                        Preprocessing options are available after enrichment completes
                    </p>
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-lg font-semibold flex items-center gap-2">
                        <Settings2 className="h-5 w-5" />
                        Data Preprocessing
                    </h2>
                    <p className="text-sm text-muted-foreground">
                        Configure data transformations for analysis and export
                    </p>
                </div>
            </div>

            {/* Normalization Section */}
            <Collapsible open={isNormalizationOpen} onOpenChange={setIsNormalizationOpen}>
                <Card>
                    <CollapsibleTrigger asChild>
                        <CardHeader className="cursor-pointer hover:bg-muted/50">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="h-8 w-8 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                                        <Sparkles className="h-4 w-4 text-blue-600" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">Normalization</CardTitle>
                                        <CardDescription>Scale numeric features</CardDescription>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Badge variant={normMethod !== "none" ? "default" : "secondary"}>
                                        {normMethod === "none" ? "Not configured" : NORMALIZATION_METHODS.find(m => m.value === normMethod)?.label}
                                    </Badge>
                                    {isNormalizationOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                                </div>
                            </div>
                        </CardHeader>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                        <CardContent className="pt-0 space-y-4">
                            {/* Method Selector */}
                            <div className="flex items-center gap-4">
                                <span className="text-sm font-medium w-24">Method:</span>
                                <Select value={normMethod} onValueChange={setNormMethod}>
                                    <SelectTrigger className="w-48">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {NORMALIZATION_METHODS.map((m) => (
                                            <SelectItem key={m.value} value={m.value}>
                                                <div>
                                                    <div className="font-medium">{m.label}</div>
                                                    <div className="text-xs text-muted-foreground">{m.description}</div>
                                                </div>
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                {normMethod !== "none" && (
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => fetchNormalizationPreview(normMethod)}
                                        disabled={isLoadingPreview}
                                    >
                                        <RefreshCw className={`h-4 w-4 ${isLoadingPreview ? "animate-spin" : ""}`} />
                                    </Button>
                                )}
                            </div>

                            {/* Preview Table */}
                            {normMethod !== "none" && (
                                <div className="border rounded-lg overflow-hidden">
                                    <div className="bg-muted/30 px-4 py-2 text-sm font-medium">
                                        Preview (5 sample rows)
                                    </div>
                                    {isLoadingPreview ? (
                                        <div className="flex items-center justify-center py-8">
                                            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                                        </div>
                                    ) : previewData.length > 0 ? (
                                        <div className="overflow-x-auto">
                                            <Table>
                                                <TableHeader>
                                                    <TableRow>
                                                        <TableHead className="w-12">#</TableHead>
                                                        {previewFeatures.map((feat) => (
                                                            <TableHead key={feat} className="min-w-[180px]">
                                                                <div className="flex items-center gap-1 text-xs">
                                                                    <span className="truncate">{feat}</span>
                                                                </div>
                                                            </TableHead>
                                                        ))}
                                                    </TableRow>
                                                </TableHeader>
                                                <TableBody>
                                                    {previewData.slice(0, 5).map((row, idx) => (
                                                        <TableRow key={idx}>
                                                            <TableCell className="text-muted-foreground">{idx + 1}</TableCell>
                                                            {previewFeatures.map((feat) => (
                                                                <TableCell key={feat} className="font-mono text-xs">
                                                                    <div className="flex items-center gap-2">
                                                                        <span className="text-muted-foreground">
                                                                            {formatValue(row[`${feat}_raw`])}
                                                                        </span>
                                                                        <ArrowRight className="h-3 w-3 text-muted-foreground/50" />
                                                                        <span className="text-blue-600 font-medium">
                                                                            {formatValue(row[`${feat}_normalized`])}
                                                                        </span>
                                                                    </div>
                                                                </TableCell>
                                                            ))}
                                                        </TableRow>
                                                    ))}
                                                </TableBody>
                                            </Table>
                                        </div>
                                    ) : (
                                        <div className="py-8 text-center text-muted-foreground text-sm">
                                            No preview data available
                                        </div>
                                    )}
                                </div>
                            )}
                        </CardContent>
                    </CollapsibleContent>
                </Card>
            </Collapsible>

            {/* Categorical Encoding Section - Skeleton */}
            <Collapsible open={isEncodingOpen} onOpenChange={setIsEncodingOpen}>
                <Card className="opacity-75">
                    <CollapsibleTrigger asChild>
                        <CardHeader className="cursor-pointer hover:bg-muted/50">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="h-8 w-8 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
                                        <Hash className="h-4 w-4 text-purple-600" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">Categorical Encoding</CardTitle>
                                        <CardDescription>Convert text to numeric values</CardDescription>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Badge variant="outline">Coming Soon</Badge>
                                    {isEncodingOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                                </div>
                            </div>
                        </CardHeader>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                        <CardContent className="pt-0">
                            <div className="py-8 text-center">
                                <Hash className="h-12 w-12 mx-auto text-muted-foreground mb-4 opacity-50" />
                                <p className="text-sm text-muted-foreground">
                                    One-hot encoding, label encoding, and target encoding will be available here.
                                </p>
                            </div>
                        </CardContent>
                    </CollapsibleContent>
                </Card>
            </Collapsible>

            {/* Missing Value Handling Section - Skeleton */}
            <Collapsible open={isMissingOpen} onOpenChange={setIsMissingOpen}>
                <Card className="opacity-75">
                    <CollapsibleTrigger asChild>
                        <CardHeader className="cursor-pointer hover:bg-muted/50">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="h-8 w-8 rounded-lg bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
                                        <Binary className="h-4 w-4 text-amber-600" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">Missing Value Handling</CardTitle>
                                        <CardDescription>Impute or remove null values</CardDescription>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Badge variant="outline">Coming Soon</Badge>
                                    {isMissingOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                                </div>
                            </div>
                        </CardHeader>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                        <CardContent className="pt-0">
                            <div className="py-8 text-center">
                                <Binary className="h-12 w-12 mx-auto text-muted-foreground mb-4 opacity-50" />
                                <p className="text-sm text-muted-foreground">
                                    Mean/median imputation, forward fill, and drop strategies will be available here.
                                </p>
                            </div>
                        </CardContent>
                    </CollapsibleContent>
                </Card>
            </Collapsible>

            {/* Outlier Detection Section - Skeleton */}
            <Collapsible open={isOutlierOpen} onOpenChange={setIsOutlierOpen}>
                <Card className="opacity-75">
                    <CollapsibleTrigger asChild>
                        <CardHeader className="cursor-pointer hover:bg-muted/50">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="h-8 w-8 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                                        <TrendingUp className="h-4 w-4 text-red-600" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">Outlier Detection</CardTitle>
                                        <CardDescription>Identify and handle outliers</CardDescription>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Badge variant="outline">Coming Soon</Badge>
                                    {isOutlierOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                                </div>
                            </div>
                        </CardHeader>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                        <CardContent className="pt-0">
                            <div className="py-8 text-center">
                                <AlertTriangle className="h-12 w-12 mx-auto text-muted-foreground mb-4 opacity-50" />
                                <p className="text-sm text-muted-foreground">
                                    IQR-based, Z-score, and isolation forest detection will be available here.
                                </p>
                            </div>
                        </CardContent>
                    </CollapsibleContent>
                </Card>
            </Collapsible>
        </div>
    );
}
