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
import { preprocessingApi, type NormalizationPreviewResponse, type NormalizationMethod, type FeaturePreview } from "@/lib/api";

interface PreprocessingSectionProps {
    datasetId: string;
    versionId: string;
    versionStatus: string;
}

interface NormalizationMethodOption {
    value: NormalizationMethod;
    label: string;
    description: string;
}

const NORMALIZATION_METHODS: NormalizationMethodOption[] = [
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
    const [normMethod, setNormMethod] = useState<NormalizationMethod>("none");
    const [previewData, setPreviewData] = useState<NormalizationPreviewResponse | null>(null);
    const [isLoadingPreview, setIsLoadingPreview] = useState(false);

    const isVersionCompleted = ["processed", "completed"].includes(versionStatus);

    const fetchNormalizationPreview = useCallback(async (method: NormalizationMethod) => {
        if (!isVersionCompleted || method === "none") {
            setPreviewData(null);
            return;
        }

        setIsLoadingPreview(true);
        try {
            const data = await preprocessingApi.previewNormalization(
                datasetId,
                versionId,
                { method, sample_size: 5 }
            );
            setPreviewData(data);
        } catch (err) {
            console.error("Failed to fetch normalization preview:", err);
            setPreviewData(null);
        } finally {
            setIsLoadingPreview(false);
        }
    }, [datasetId, versionId, isVersionCompleted]);

    useEffect(() => {
        if (isNormalizationOpen && normMethod !== "none") {
            fetchNormalizationPreview(normMethod);
        }
    }, [isNormalizationOpen, normMethod, fetchNormalizationPreview]);

    const formatValue = (value: number | null | undefined): string => {
        if (value === null || value === undefined) return "—";
        return value.toFixed(4);
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
                                <Select value={normMethod} onValueChange={(v) => setNormMethod(v as NormalizationMethod)}>
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
                                        Preview (sample values for each feature)
                                    </div>
                                    {isLoadingPreview ? (
                                        <div className="flex items-center justify-center py-8">
                                            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                                        </div>
                                    ) : previewData && Object.keys(previewData.features).length > 0 ? (
                                        <div className="overflow-x-auto">
                                            <Table>
                                                <TableHeader>
                                                    <TableRow>
                                                        <TableHead className="w-40">Feature</TableHead>
                                                        <TableHead className="min-w-[250px]">Original</TableHead>
                                                        <TableHead className="w-10"></TableHead>
                                                        <TableHead className="min-w-[250px]">Transformed</TableHead>
                                                        <TableHead className="w-32">Stats Change</TableHead>
                                                    </TableRow>
                                                </TableHeader>
                                                <TableBody>
                                                    {(Object.entries(previewData.features) as [string, FeaturePreview][]).map(([feat, data]) => (
                                                        <TableRow key={feat}>
                                                            <TableCell className="font-medium">
                                                                <div className="truncate max-w-[140px]" title={feat}>
                                                                    {feat}
                                                                </div>
                                                                <Badge variant="outline" className="text-xs mt-1">
                                                                    {data.data_type}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell className="font-mono text-xs">
                                                                <div className="text-muted-foreground">
                                                                    [{data.original.sample.map((v: number) => formatValue(v)).join(", ")}]
                                                                </div>
                                                                <div className="text-xs mt-1">
                                                                    μ={formatValue(data.original.stats.mean)}, σ={formatValue(data.original.stats.std)}
                                                                </div>
                                                            </TableCell>
                                                            <TableCell>
                                                                <ArrowRight className="h-4 w-4 text-muted-foreground/50" />
                                                            </TableCell>
                                                            <TableCell className="font-mono text-xs">
                                                                <div className="text-blue-600 font-medium">
                                                                    [{data.transformed.sample.map((v: number) => formatValue(v)).join(", ")}]
                                                                </div>
                                                                <div className="text-xs mt-1">
                                                                    μ={formatValue(data.transformed.stats.mean)}, σ={formatValue(data.transformed.stats.std)}
                                                                </div>
                                                            </TableCell>
                                                            <TableCell className="text-xs">
                                                                <div className="space-y-1">
                                                                    <div>range: [{formatValue(data.transformed.stats.min)}, {formatValue(data.transformed.stats.max)}]</div>
                                                                </div>
                                                            </TableCell>
                                                        </TableRow>
                                                    ))}
                                                </TableBody>
                                            </Table>
                                        </div>
                                    ) : (
                                        <div className="py-8 text-center text-muted-foreground text-sm">
                                            {previewData?.message || "No preview data available"}
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
