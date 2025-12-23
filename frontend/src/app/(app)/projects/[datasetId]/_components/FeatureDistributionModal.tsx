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
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import {
    AlertCircle,
    BarChart3,
    Loader2,
    RefreshCw,
    X,
} from "lucide-react";
import {
    statisticsApi,
    type FeatureDistributionResponse,
    type NumericDistribution,
    type CategoricalDistribution,
    type HistogramBin,
    type NumericStats,
} from "@/lib/api";

interface FeatureDistributionModalProps {
    datasetId: string;
    versionId: string;
    features: string[];
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function FeatureDistributionModal({
    datasetId,
    versionId,
    features,
    open,
    onOpenChange,
}: FeatureDistributionModalProps) {
    const [distributionData, setDistributionData] = useState<FeatureDistributionResponse | null>(null);
    const [selectedFeature, setSelectedFeature] = useState<string>("");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchDistributions = useCallback(async () => {
        if (!versionId || features.length === 0) return;

        setIsLoading(true);
        setError(null);

        try {
            const responseData = await statisticsApi.getDistributions(
                datasetId,
                versionId,
                { bins: 20, top_n: 20 }
            );
            setDistributionData(responseData);

            // Auto-select first feature if not selected
            const availableFeatures = Object.keys(responseData.distributions);
            if (!selectedFeature && availableFeatures.length > 0) {
                setSelectedFeature(availableFeatures[0]);
            }
        } catch (err) {
            console.error("Failed to fetch distributions:", err);
            setError("Failed to load distribution data");
        } finally {
            setIsLoading(false);
        }
    }, [datasetId, versionId, features, selectedFeature]);

    useEffect(() => {
        if (open && versionId) {
            fetchDistributions();
        }
    }, [open, versionId, fetchDistributions]);

    const currentDistribution = selectedFeature && distributionData
        ? distributionData.distributions[selectedFeature]
        : null;

    const isNumeric = currentDistribution
        && "bins" in currentDistribution
        && currentDistribution.data_type === "numeric";

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-[800px] max-h-[85vh] overflow-hidden flex flex-col">
                <DialogHeader className="flex flex-row items-center justify-between">
                    <DialogTitle className="flex items-center gap-2">
                        <BarChart3 className="h-5 w-5" />
                        Feature Distribution
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

                {/* Feature Selector */}
                <div className="flex items-center gap-4">
                    <Select value={selectedFeature} onValueChange={setSelectedFeature}>
                        <SelectTrigger className="w-[300px]">
                            <SelectValue placeholder="Select a feature" />
                        </SelectTrigger>
                        <SelectContent>
                            {distributionData && Object.keys(distributionData.distributions).map((featureName) => (
                                <SelectItem key={featureName} value={featureName}>
                                    {featureName}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <Button variant="outline" size="sm" onClick={fetchDistributions} disabled={isLoading}>
                        <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
                        Refresh
                    </Button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-auto">
                    {isLoading ? (
                        <div className="flex items-center justify-center py-12">
                            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                        </div>
                    ) : error ? (
                        <div className="flex flex-col items-center justify-center py-12 gap-4">
                            <AlertCircle className="h-12 w-12 text-destructive" />
                            <p className="text-muted-foreground">{error}</p>
                        </div>
                    ) : !currentDistribution ? (
                        <div className="flex flex-col items-center justify-center py-12 gap-4">
                            <BarChart3 className="h-12 w-12 text-muted-foreground" />
                            <p className="text-muted-foreground">Select a feature to view distribution</p>
                        </div>
                    ) : isNumeric ? (
                        <NumericDistributionChart
                            distribution={currentDistribution as NumericDistribution}
                        />
                    ) : (
                        <CategoricalDistributionChart
                            distribution={currentDistribution as CategoricalDistribution}
                        />
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}

// =============================================================================
// Numeric Distribution Chart (Histogram)
// =============================================================================

interface NumericDistributionChartProps {
    distribution: NumericDistribution;
}

function NumericDistributionChart({ distribution }: NumericDistributionChartProps) {
    const { feature_name, total_count, null_count, bins, stats } = distribution;

    // Find max count for scaling
    const maxCount = Math.max(...bins.map(bin => bin.count), 1);

    return (
        <div className="space-y-6 p-4">
            {/* Header Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatBox label="Total Values" value={total_count} />
                <StatBox label="Missing" value={null_count} className="text-amber-600" />
                {stats && (
                    <>
                        <StatBox label="Mean" value={stats.mean.toFixed(2)} />
                        <StatBox label="Std Dev" value={stats.std.toFixed(2)} />
                    </>
                )}
            </div>

            {/* Box Plot Summary */}
            {stats && <BoxPlotSummary stats={stats} />}

            {/* Histogram */}
            <div className="space-y-2">
                <h4 className="text-sm font-medium">Distribution Histogram</h4>
                <div className="flex items-end h-48 gap-[2px] border-b border-l p-2">
                    {bins.map((bin, index) => (
                        <TooltipProvider key={index}>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <div
                                        className="flex-1 bg-blue-500 hover:bg-blue-600 transition-colors rounded-t cursor-pointer"
                                        style={{
                                            height: `${(bin.count / maxCount) * 100}%`,
                                            minHeight: bin.count > 0 ? "4px" : "0px",
                                        }}
                                    />
                                </TooltipTrigger>
                                <TooltipContent>
                                    <div className="text-xs space-y-1">
                                        <p className="font-medium">
                                            {bin.min_value.toFixed(2)} - {bin.max_value.toFixed(2)}
                                        </p>
                                        <p>Count: {bin.count} ({bin.percentage}%)</p>
                                    </div>
                                </TooltipContent>
                            </Tooltip>
                        </TooltipProvider>
                    ))}
                </div>

                {/* X-axis labels */}
                {bins.length > 0 && (
                    <div className="flex justify-between text-xs text-muted-foreground pl-2">
                        <span>{bins[0].min_value.toFixed(1)}</span>
                        <span>{bins[Math.floor(bins.length / 2)].min_value.toFixed(1)}</span>
                        <span>{bins[bins.length - 1].max_value.toFixed(1)}</span>
                    </div>
                )}
            </div>
        </div>
    );
}

// =============================================================================
// Categorical Distribution Chart (Bar Chart)
// =============================================================================

interface CategoricalDistributionChartProps {
    distribution: CategoricalDistribution;
}

function CategoricalDistributionChart({ distribution }: CategoricalDistributionChartProps) {
    const { feature_name, total_count, null_count, unique_count, values, truncated } = distribution;

    // Find max count for scaling
    const maxCount = Math.max(...values.map(v => v.count), 1);

    return (
        <div className="space-y-6 p-4">
            {/* Header Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatBox label="Total Values" value={total_count} />
                <StatBox label="Missing" value={null_count} className="text-amber-600" />
                <StatBox label="Unique Values" value={unique_count} />
                <StatBox
                    label="Shown"
                    value={truncated ? `${values.length} of ${unique_count}` : `${values.length}`}
                />
            </div>

            {/* Horizontal Bar Chart */}
            <div className="space-y-2">
                <h4 className="text-sm font-medium">Value Distribution</h4>
                <div className="space-y-2 max-h-80 overflow-y-auto">
                    {values.map((item, index) => (
                        <div key={index} className="flex items-center gap-3">
                            <div
                                className="w-32 truncate text-sm text-right"
                                title={item.value}
                            >
                                {item.value}
                            </div>
                            <div className="flex-1 h-6 bg-muted rounded overflow-hidden">
                                <div
                                    className="h-full bg-green-500 flex items-center justify-end pr-2"
                                    style={{ width: `${(item.count / maxCount) * 100}%` }}
                                >
                                    {item.percentage > 10 && (
                                        <span className="text-xs text-white font-medium">
                                            {item.count}
                                        </span>
                                    )}
                                </div>
                            </div>
                            <div className="w-16 text-right text-sm text-muted-foreground">
                                {item.percentage.toFixed(1)}%
                            </div>
                        </div>
                    ))}
                </div>

                {truncated && (
                    <p className="text-sm text-muted-foreground text-center pt-2">
                        Showing top {values.length} values of {unique_count} total
                    </p>
                )}
            </div>
        </div>
    );
}

// =============================================================================
// Helper Components
// =============================================================================

interface StatBoxProps {
    label: string;
    value: string | number;
    className?: string;
}

function StatBox({ label, value, className = "" }: StatBoxProps) {
    return (
        <div className="p-3 bg-muted/50 rounded-lg">
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className={`text-lg font-semibold ${className}`}>{value}</p>
        </div>
    );
}

interface BoxPlotSummaryProps {
    stats: NumericStats;
}

function BoxPlotSummary({ stats }: BoxPlotSummaryProps) {
    const range = stats.max - stats.min;
    const getPosition = (value: number) => ((value - stats.min) / range) * 100;

    return (
        <div className="space-y-2">
            <h4 className="text-sm font-medium">Box Plot Summary</h4>

            {/* Box Plot Visualization */}
            <div className="relative h-12 bg-muted rounded px-4">
                {/* Min line */}
                <div
                    className="absolute top-1/4 h-1/2 w-px bg-gray-600"
                    style={{ left: `${getPosition(stats.min)}%` }}
                />

                {/* Whisker min to q1 */}
                <div
                    className="absolute top-1/2 h-px bg-gray-600 -translate-y-1/2"
                    style={{
                        left: `${getPosition(stats.min)}%`,
                        width: `${getPosition(stats.q1) - getPosition(stats.min)}%`,
                    }}
                />

                {/* Box (Q1 to Q3) */}
                <div
                    className="absolute top-1/4 h-1/2 bg-blue-200 border-2 border-blue-500 rounded"
                    style={{
                        left: `${getPosition(stats.q1)}%`,
                        width: `${getPosition(stats.q3) - getPosition(stats.q1)}%`,
                    }}
                />

                {/* Median line */}
                <div
                    className="absolute top-1/4 h-1/2 w-0.5 bg-red-500"
                    style={{ left: `${getPosition(stats.median)}%` }}
                />

                {/* Whisker q3 to max */}
                <div
                    className="absolute top-1/2 h-px bg-gray-600 -translate-y-1/2"
                    style={{
                        left: `${getPosition(stats.q3)}%`,
                        width: `${getPosition(stats.max) - getPosition(stats.q3)}%`,
                    }}
                />

                {/* Max line */}
                <div
                    className="absolute top-1/4 h-1/2 w-px bg-gray-600"
                    style={{ left: `${getPosition(stats.max)}%` }}
                />
            </div>

            {/* Labels */}
            <div className="grid grid-cols-5 text-xs text-center text-muted-foreground">
                <div>
                    <p className="font-medium">Min</p>
                    <p>{stats.min.toFixed(2)}</p>
                </div>
                <div>
                    <p className="font-medium">Q1</p>
                    <p>{stats.q1.toFixed(2)}</p>
                </div>
                <div>
                    <p className="font-medium text-red-600">Median</p>
                    <p>{stats.median.toFixed(2)}</p>
                </div>
                <div>
                    <p className="font-medium">Q3</p>
                    <p>{stats.q3.toFixed(2)}</p>
                </div>
                <div>
                    <p className="font-medium">Max</p>
                    <p>{stats.max.toFixed(2)}</p>
                </div>
            </div>
        </div>
    );
}
