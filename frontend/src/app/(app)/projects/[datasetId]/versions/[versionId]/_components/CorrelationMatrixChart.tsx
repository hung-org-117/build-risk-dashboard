"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, AlertCircle, RefreshCw, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { statisticsApi, type CorrelationMatrixResponse } from "@/lib/api/statistics";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";

interface CorrelationMatrixChartProps {
    datasetId: string;
    versionId: string;
}

export function CorrelationMatrixChart({ datasetId, versionId }: CorrelationMatrixChartProps) {
    const [data, setData] = useState<CorrelationMatrixResponse | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchData = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const response = await statisticsApi.getCorrelation(datasetId, versionId);
            setData(response);
        } catch (err) {
            console.error("Failed to fetch correlation matrix:", err);
            setError("Failed to load correlation data");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, [datasetId, versionId]);

    const getColor = (value: number | null) => {
        if (value === null) return "bg-muted";

        // Red for positive correlation, Blue for negative
        // Opacity based on absolute value
        const absVal = Math.abs(value);
        if (value > 0) {
            // Positive (Red)
            if (absVal < 0.2) return "bg-red-50 text-slate-700";
            if (absVal < 0.4) return "bg-red-200 text-slate-800";
            if (absVal < 0.6) return "bg-red-400 text-white";
            if (absVal < 0.8) return "bg-red-600 text-white";
            return "bg-red-800 text-white";
        } else {
            // Negative (Blue)
            if (absVal < 0.2) return "bg-blue-50 text-slate-700";
            if (absVal < 0.4) return "bg-blue-200 text-slate-800";
            if (absVal < 0.6) return "bg-blue-400 text-white";
            if (absVal < 0.8) return "bg-blue-600 text-white";
            return "bg-blue-800 text-white";
        }
    };

    if (isLoading && !data) {
        return (
            <Card>
                <CardContent className="flex justify-center p-6">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </CardContent>
            </Card>
        );
    }

    if (error) {
        return (
            <Card>
                <CardContent className="flex flex-col items-center justify-center p-6 gap-2">
                    <AlertCircle className="h-6 w-6 text-destructive" />
                    <p className="text-sm text-muted-foreground">{error}</p>
                    <Button variant="ghost" size="sm" onClick={fetchData}>
                        Retry
                    </Button>
                </CardContent>
            </Card>
        );
    }

    if (!data || data.features.length === 0) {
        return null;
    }

    // Since matrix can be large, we need proper scrolling
    return (
        <Card className="col-span-2">
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="text-base flex items-center gap-2">
                            <Activity className="h-4 w-4" />
                            Correlation Matrix
                        </CardTitle>
                        <CardDescription>
                            Pearson correlation between numeric features within this version
                        </CardDescription>
                    </div>
                    <Button variant="ghost" size="icon" onClick={fetchData}>
                        <RefreshCw className="h-4 w-4" />
                    </Button>
                </div>
            </CardHeader>
            <CardContent>
                <ScrollArea className="w-full h-[500px] border rounded-md">
                    <div className="min-w-max p-4">
                        {/* Header Row */}
                        <div className="flex">
                            <div className="w-32 shrink-0" /> {/* Corner Spacer */}
                            {data.features.map((feature, i) => (
                                <div
                                    key={i}
                                    className="w-16 shrink-0 -rotate-45 origin-bottom-left translate-x-8 mb-8 text-xs text-muted-foreground truncate"
                                    title={feature}
                                >
                                    {feature}
                                </div>
                            ))}
                        </div>

                        {/* Matrix Rows */}
                        {data.features.map((rowFeature, i) => (
                            <div key={i} className="flex items-center">
                                {/* Row Label */}
                                <div
                                    className="w-32 shrink-0 text-xs text-muted-foreground truncate text-right pr-2"
                                    title={rowFeature}
                                >
                                    {rowFeature}
                                </div>

                                {/* Cells */}
                                {data.matrix[i].map((value, j) => (
                                    <TooltipProvider key={j}>
                                        <Tooltip>
                                            <TooltipTrigger asChild>
                                                <div
                                                    className={`w-12 h-12 m-0.5 flex items-center justify-center text-[10px] rounded cursor-default ${getColor(value)}`}
                                                >
                                                    {value !== null ? value.toFixed(2) : "-"}
                                                </div>
                                            </TooltipTrigger>
                                            <TooltipContent>
                                                <div className="text-xs">
                                                    <p className="font-semibold">{rowFeature} vs {data.features[j]}</p>
                                                    <p>Correlation: {value !== null ? value.toFixed(4) : "N/A"}</p>
                                                </div>
                                            </TooltipContent>
                                        </Tooltip>
                                    </TooltipProvider>
                                ))}
                            </div>
                        ))}
                    </div>
                    <ScrollBar orientation="horizontal" />
                </ScrollArea>

                {data.significant_pairs.length > 0 && (
                    <div className="mt-4">
                        <h4 className="text-sm font-semibold mb-2">Significant Correlations (|r| &gt; 0.5)</h4>
                        <div className="flex flex-wrap gap-2">
                            {data.significant_pairs.slice(0, 10).map((pair, idx) => (
                                <Badge key={idx} variant="outline" className="text-xs">
                                    {pair.feature_1} ↔ {pair.feature_2}: {pair.correlation.toFixed(2)}
                                </Badge>
                            ))}
                            {data.significant_pairs.length > 10 && (
                                <span className="text-xs text-muted-foreground py-1">
                                    +{data.significant_pairs.length - 10} more
                                </span>
                            )}
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
