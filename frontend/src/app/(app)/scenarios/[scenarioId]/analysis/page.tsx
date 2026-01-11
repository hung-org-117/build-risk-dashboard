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
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Loader2, BarChart3, PieChart } from "lucide-react";
import {
    trainingScenariosApi,
    TrainingScenarioRecord,
    TrainingDatasetSplitRecord,
} from "@/lib/api/training-scenarios";

export default function ScenarioAnalysisPage() {
    const params = useParams<{ scenarioId: string }>();
    const scenarioId = params.scenarioId;

    const [scenario, setScenario] = useState<TrainingScenarioRecord | null>(null);
    const [splits, setSplits] = useState<TrainingDatasetSplitRecord[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchData = useCallback(async () => {
        try {
            const [scenarioData, splitsData] = await Promise.all([
                trainingScenariosApi.get(scenarioId),
                trainingScenariosApi.getSplits(scenarioId),
            ]);
            setScenario(scenarioData);
            setSplits(splitsData);
        } catch (err) {
            console.error("Failed to fetch analysis data:", err);
        } finally {
            setLoading(false);
        }
    }, [scenarioId]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    if (loading || !scenario) {
        return (
            <div className="flex min-h-[400px] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    // Aggregate class distribution from all splits
    const aggregatedClassDist: Record<string, number> = {};
    splits.forEach((split) => {
        Object.entries(split.class_distribution || {}).forEach(([cls, count]) => {
            aggregatedClassDist[cls] = (aggregatedClassDist[cls] || 0) + count;
        });
    });

    // Calculate totals
    const totalSamples = Object.values(aggregatedClassDist).reduce((a, b) => a + b, 0);
    const successCount = aggregatedClassDist["success"] || aggregatedClassDist["1"] || 0;
    const failureCount = aggregatedClassDist["failure"] || aggregatedClassDist["0"] || 0;
    const successPct = totalSamples > 0 ? (successCount / totalSamples) * 100 : 0;
    const failurePct = totalSamples > 0 ? (failureCount / totalSamples) * 100 : 0;

    return (
        <div className="space-y-6">
            {/* Summary Stats */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <BarChart3 className="h-5 w-5" />
                        Dataset Summary
                    </CardTitle>
                    <CardDescription>
                        Overview of extracted features and samples
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="grid gap-4 md:grid-cols-4">
                        <div className="p-4 border rounded-lg">
                            <p className="text-sm text-muted-foreground">Total Samples</p>
                            <p className="text-2xl font-bold">{scenario.builds_features_extracted}</p>
                        </div>
                        <div className="p-4 border rounded-lg">
                            <p className="text-sm text-muted-foreground">Train Set</p>
                            <p className="text-2xl font-bold">{scenario.train_count}</p>
                        </div>
                        <div className="p-4 border rounded-lg">
                            <p className="text-sm text-muted-foreground">Validation Set</p>
                            <p className="text-2xl font-bold">{scenario.val_count}</p>
                        </div>
                        <div className="p-4 border rounded-lg">
                            <p className="text-sm text-muted-foreground">Test Set</p>
                            <p className="text-2xl font-bold">{scenario.test_count}</p>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Class Distribution */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <PieChart className="h-5 w-5" />
                        Class Distribution
                    </CardTitle>
                    <CardDescription>
                        Distribution of build outcomes across the entire dataset
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {totalSamples > 0 ? (
                        <>
                            {/* Visual bar */}
                            <div className="flex h-8 rounded-lg overflow-hidden mb-4">
                                <div
                                    className="bg-green-500 flex items-center justify-center text-white text-sm font-medium"
                                    style={{ width: `${successPct}%` }}
                                >
                                    {successPct > 10 && `${successPct.toFixed(1)}%`}
                                </div>
                                <div
                                    className="bg-red-500 flex items-center justify-center text-white text-sm font-medium"
                                    style={{ width: `${failurePct}%` }}
                                >
                                    {failurePct > 10 && `${failurePct.toFixed(1)}%`}
                                </div>
                            </div>

                            {/* Stats grid */}
                            <div className="grid gap-4 md:grid-cols-2">
                                <div className="p-4 border rounded-lg bg-green-50 dark:bg-green-950">
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-green-700 dark:text-green-300">Success</span>
                                        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300">
                                            {successPct.toFixed(1)}%
                                        </Badge>
                                    </div>
                                    <p className="text-2xl font-bold text-green-800 dark:text-green-200 mt-2">
                                        {successCount.toLocaleString()}
                                    </p>
                                    <Progress value={successPct} className="mt-2 h-2" />
                                </div>
                                <div className="p-4 border rounded-lg bg-red-50 dark:bg-red-950">
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-red-700 dark:text-red-300">Failure</span>
                                        <Badge className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300">
                                            {failurePct.toFixed(1)}%
                                        </Badge>
                                    </div>
                                    <p className="text-2xl font-bold text-red-800 dark:text-red-200 mt-2">
                                        {failureCount.toLocaleString()}
                                    </p>
                                    <Progress value={failurePct} className="mt-2 h-2" />
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="text-center py-8 text-muted-foreground">
                            <p>Class distribution data available after splits are generated.</p>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Per-Split Distribution */}
            {splits.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>Distribution by Split</CardTitle>
                        <CardDescription>
                            Class distribution breakdown for each data split
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="grid gap-4 md:grid-cols-3">
                            {splits.map((split) => {
                                const splitTotal = Object.values(split.class_distribution || {}).reduce((a, b) => a + b, 0);
                                const splitSuccess = (split.class_distribution?.["success"] || split.class_distribution?.["1"] || 0);
                                const splitFailure = (split.class_distribution?.["failure"] || split.class_distribution?.["0"] || 0);
                                const splitSuccessPct = splitTotal > 0 ? (splitSuccess / splitTotal) * 100 : 0;

                                return (
                                    <div key={split.id} className="p-4 border rounded-lg">
                                        <div className="flex items-center justify-between mb-2">
                                            <Badge variant="outline" className="capitalize">
                                                {split.split_type}
                                            </Badge>
                                            <span className="text-sm text-muted-foreground">
                                                {split.record_count} samples
                                            </span>
                                        </div>
                                        <div className="flex h-4 rounded-lg overflow-hidden mb-2">
                                            <div
                                                className="bg-green-500"
                                                style={{ width: `${splitSuccessPct}%` }}
                                            />
                                            <div
                                                className="bg-red-500"
                                                style={{ width: `${100 - splitSuccessPct}%` }}
                                            />
                                        </div>
                                        <div className="flex justify-between text-xs text-muted-foreground">
                                            <span>Success: {splitSuccess}</span>
                                            <span>Failure: {splitFailure}</span>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Feature Info */}
            {splits.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>Feature Summary</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="grid gap-4 md:grid-cols-2">
                            <div className="p-4 border rounded-lg">
                                <p className="text-sm text-muted-foreground">Features Extracted</p>
                                <p className="text-2xl font-bold">{splits[0]?.feature_count || 0}</p>
                            </div>
                            <div className="p-4 border rounded-lg">
                                <p className="text-sm text-muted-foreground">Data Format</p>
                                <p className="text-2xl font-bold uppercase">{splits[0]?.file_format || "CSV"}</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
