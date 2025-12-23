"use client";

import { useEffect, useState, useCallback } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    ScrollArea,
    ScrollBar,
} from "@/components/ui/scroll-area";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import {
    AlertCircle,
    Grid3X3,
    Loader2,
    RefreshCw,
    X,
} from "lucide-react";
import {
    statisticsApi,
    type CorrelationMatrixResponse,
    type CorrelationPair,
} from "@/lib/api";

interface CorrelationMatrixModalProps {
    datasetId: string;
    versionId: string;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

// Color helper for correlation values
function getCorrelationColor(value: number | null): string {
    if (value === null) return "bg-gray-200 dark:bg-gray-700";

    // Blue for negative, Red for positive
    const absValue = Math.abs(value);
    const intensity = Math.round(absValue * 255);

    if (value < 0) {
        return `rgb(${255 - intensity}, ${255 - intensity}, 255)`;
    } else {
        return `rgb(255, ${255 - intensity}, ${255 - intensity})`;
    }
}

function getCorrelationBgClass(value: number | null): string {
    if (value === null) return "bg-gray-200 dark:bg-gray-700";

    const abs = Math.abs(value);

    if (abs >= 0.8) {
        return value > 0
            ? "bg-red-500 text-white"
            : "bg-blue-500 text-white";
    }
    if (abs >= 0.6) {
        return value > 0
            ? "bg-red-300 dark:bg-red-400"
            : "bg-blue-300 dark:bg-blue-400";
    }
    if (abs >= 0.4) {
        return value > 0
            ? "bg-red-200 dark:bg-red-300"
            : "bg-blue-200 dark:bg-blue-300";
    }
    if (abs >= 0.2) {
        return value > 0
            ? "bg-red-100 dark:bg-red-200 text-gray-800"
            : "bg-blue-100 dark:bg-blue-200 text-gray-800";
    }
    return "bg-gray-100 dark:bg-gray-600";
}

function getStrengthBadgeColor(strength: string): string {
    switch (strength) {
        case "strong_positive":
            return "bg-red-500 text-white";
        case "strong_negative":
            return "bg-blue-500 text-white";
        case "moderate_positive":
            return "bg-red-300";
        case "moderate_negative":
            return "bg-blue-300";
        default:
            return "bg-gray-200";
    }
}

export function CorrelationMatrixModal({
    datasetId,
    versionId,
    open,
    onOpenChange,
}: CorrelationMatrixModalProps) {
    const [correlationData, setCorrelationData] = useState<CorrelationMatrixResponse | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchCorrelation = useCallback(async () => {
        if (!versionId) return;

        setIsLoading(true);
        setError(null);

        try {
            const responseData = await statisticsApi.getCorrelation(datasetId, versionId);
            setCorrelationData(responseData);
        } catch (err) {
            console.error("Failed to fetch correlation matrix:", err);
            setError("Failed to load correlation matrix");
        } finally {
            setIsLoading(false);
        }
    }, [datasetId, versionId]);

    useEffect(() => {
        if (open && versionId) {
            fetchCorrelation();
        }
    }, [open, versionId, fetchCorrelation]);

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-[95vw] max-h-[90vh] overflow-hidden flex flex-col">
                <DialogHeader className="flex flex-row items-center justify-between">
                    <DialogTitle className="flex items-center gap-2">
                        <Grid3X3 className="h-5 w-5" />
                        Feature Correlation Matrix
                    </DialogTitle>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => onOpenChange(false)}
                    >
                        <X className="h-4 w-4" />
                        <span className="sr-only">Close</span>
                    </Button>
                </DialogHeader>

                {isLoading ? (
                    <div className="flex items-center justify-center py-12">
                        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                    </div>
                ) : error ? (
                    <div className="flex flex-col items-center justify-center py-12 gap-4">
                        <AlertCircle className="h-12 w-12 text-destructive" />
                        <p className="text-muted-foreground">{error}</p>
                        <Button variant="outline" onClick={fetchCorrelation}>
                            <RefreshCw className="mr-2 h-4 w-4" />
                            Retry
                        </Button>
                    </div>
                ) : !correlationData || correlationData.features.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 gap-4">
                        <Grid3X3 className="h-12 w-12 text-muted-foreground" />
                        <p className="text-muted-foreground">
                            No numeric features available for correlation analysis
                        </p>
                    </div>
                ) : (
                    <div className="flex-1 flex flex-col gap-4 overflow-hidden">
                        {/* Legend */}
                        <div className="flex items-center gap-4 text-sm">
                            <span>Correlation:</span>
                            <div className="flex items-center gap-1">
                                <div className="w-6 h-4 bg-blue-500 rounded" />
                                <span>-1 (Negative)</span>
                            </div>
                            <div className="flex items-center gap-1">
                                <div className="w-6 h-4 bg-gray-200 dark:bg-gray-600 rounded" />
                                <span>0 (None)</span>
                            </div>
                            <div className="flex items-center gap-1">
                                <div className="w-6 h-4 bg-red-500 rounded" />
                                <span>+1 (Positive)</span>
                            </div>
                            <Button variant="outline" size="sm" onClick={fetchCorrelation} className="ml-auto">
                                <RefreshCw className="h-4 w-4 mr-2" />
                                Refresh
                            </Button>
                        </div>

                        {/* Matrix Grid */}
                        <ScrollArea className="flex-1 border rounded-lg">
                            <div className="p-4">
                                <CorrelationMatrixGrid
                                    features={correlationData.features}
                                    matrix={correlationData.matrix}
                                />
                            </div>
                            <ScrollBar orientation="horizontal" />
                        </ScrollArea>

                        {/* Significant Pairs */}
                        {correlationData.significant_pairs.length > 0 && (
                            <div className="border rounded-lg p-4 max-h-48 overflow-auto">
                                <h3 className="text-sm font-medium mb-3">
                                    Significant Correlations ({correlationData.significant_pairs.length})
                                </h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                                    {correlationData.significant_pairs.map((pair, index) => (
                                        <SignificantPairCard key={index} pair={pair} />
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}

// =============================================================================
// Sub-components
// =============================================================================

interface CorrelationMatrixGridProps {
    features: string[];
    matrix: (number | null)[][];
}

function CorrelationMatrixGrid({ features, matrix }: CorrelationMatrixGridProps) {
    const cellSize = 60;
    const labelWidth = 120;

    return (
        <div className="inline-block">
            {/* Header Row */}
            <div className="flex" style={{ marginLeft: labelWidth }}>
                {features.map((feature, index) => (
                    <div
                        key={`header-${index}`}
                        className="text-xs font-medium text-center truncate transform -rotate-45 origin-bottom-left"
                        style={{
                            width: cellSize,
                            height: labelWidth,
                            display: "flex",
                            alignItems: "flex-end",
                            justifyContent: "flex-start",
                        }}
                        title={feature}
                    >
                        <span className="truncate max-w-[100px]">{feature}</span>
                    </div>
                ))}
            </div>

            {/* Matrix Rows */}
            {matrix.map((row, rowIndex) => (
                <div key={`row-${rowIndex}`} className="flex items-center">
                    {/* Row Label */}
                    <div
                        className="text-xs font-medium truncate text-right pr-2"
                        style={{ width: labelWidth }}
                        title={features[rowIndex]}
                    >
                        {features[rowIndex]}
                    </div>

                    {/* Cells */}
                    {row.map((value, colIndex) => (
                        <TooltipProvider key={`cell-${rowIndex}-${colIndex}`}>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <div
                                        className={`flex items-center justify-center text-xs font-medium border border-gray-200 dark:border-gray-700 ${getCorrelationBgClass(value)} cursor-pointer hover:ring-2 hover:ring-primary`}
                                        style={{
                                            width: cellSize,
                                            height: cellSize / 1.5,
                                        }}
                                    >
                                        {value !== null ? value.toFixed(2) : "-"}
                                    </div>
                                </TooltipTrigger>
                                <TooltipContent>
                                    <div className="text-xs">
                                        <p className="font-medium">{features[rowIndex]} × {features[colIndex]}</p>
                                        <p>Correlation: {value !== null ? value.toFixed(4) : "N/A"}</p>
                                    </div>
                                </TooltipContent>
                            </Tooltip>
                        </TooltipProvider>
                    ))}
                </div>
            ))}
        </div>
    );
}

interface SignificantPairCardProps {
    pair: CorrelationPair;
}

function SignificantPairCard({ pair }: SignificantPairCardProps) {
    const isPositive = pair.correlation > 0;

    return (
        <div className="flex items-center gap-2 p-2 bg-muted/50 rounded-lg">
            <div className="flex-1 min-w-0">
                <p className="text-xs font-medium truncate" title={pair.feature_1}>
                    {pair.feature_1}
                </p>
                <p className="text-xs text-muted-foreground truncate" title={pair.feature_2}>
                    ↔ {pair.feature_2}
                </p>
            </div>
            <Badge
                className={`text-xs ${isPositive ? "bg-red-100 text-red-800" : "bg-blue-100 text-blue-800"}`}
            >
                {pair.correlation.toFixed(3)}
            </Badge>
        </div>
    );
}
