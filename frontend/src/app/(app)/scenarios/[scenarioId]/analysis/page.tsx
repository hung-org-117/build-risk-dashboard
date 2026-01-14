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
import { Loader2 } from "lucide-react";
import {
    trainingScenariosApi,
    TrainingScenarioRecord,
    TrainingDatasetSplitRecord,
    DataQualityReport,
} from "@/lib/api/training-scenarios";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function ScenarioAnalysisPage() {
    const params = useParams<{ scenarioId: string }>();
    const scenarioId = params.scenarioId;

    const [scenario, setScenario] = useState<TrainingScenarioRecord | null>(null);
    const [splits, setSplits] = useState<TrainingDatasetSplitRecord[]>([]);
    const [qualityReport, setQualityReport] = useState<DataQualityReport | null>(null);
    const [loading, setLoading] = useState(true);

    const fetchData = useCallback(async () => {
        try {
            const [scenarioData, splitsData, qualityData] = await Promise.all([
                trainingScenariosApi.get(scenarioId),
                trainingScenariosApi.getSplits(scenarioId),
                trainingScenariosApi.getAnalysis(scenarioId),
            ]);
            setScenario(scenarioData);
            setSplits(splitsData);
            setQualityReport(qualityData);
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
            <h2 className="text-2xl font-bold tracking-tight">Dataset Analysis</h2>

            <Tabs defaultValue="quality" className="space-y-4">
                <TabsList>
                    <TabsTrigger value="quality">Data Quality</TabsTrigger>
                    <TabsTrigger value="distribution">Class Distribution</TabsTrigger>
                    <TabsTrigger value="features">Features & Scans</TabsTrigger>
                </TabsList>

                {/* Data Quality Tab */}
                <TabsContent value="quality" className="space-y-4">
                    {qualityReport ? (
                        <>
                            {/* Overall Score */}
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                                <Card>
                                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                        <CardTitle className="text-sm font-medium">Quality Score</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="text-2xl font-bold">
                                            {qualityReport.quality_score.toFixed(1)}
                                        </div>
                                        <p className="text-xs text-muted-foreground">
                                            Overall quality rating (0-100)
                                        </p>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                        <CardTitle className="text-sm font-medium">Completeness</CardTitle>
                                        <div className="text-2xl font-bold">
                                            {qualityReport.completeness_score.toFixed(1)}%
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        <Progress value={qualityReport.completeness_score} className="h-2" />
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                        <CardTitle className="text-sm font-medium">Validity</CardTitle>
                                        <div className="text-2xl font-bold">
                                            {qualityReport.validity_score.toFixed(1)}%
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        <Progress value={qualityReport.validity_score} className="h-2" />
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                        <CardTitle className="text-sm font-medium">Consistency</CardTitle>
                                        <div className="text-2xl font-bold">
                                            {qualityReport.consistency_score.toFixed(1)}%
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        <Progress value={qualityReport.consistency_score} className="h-2" />
                                    </CardContent>
                                </Card>
                            </div>

                            {/* Scan Metrics Summary */}
                            {qualityReport.scan_metrics_summary && (
                                <Card>
                                    <CardHeader>
                                        <CardTitle>
                                            Scan Metrics Coverage
                                        </CardTitle>
                                        <CardDescription>
                                            Availability of scan results for builds in this dataset
                                        </CardDescription>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="grid gap-6 md:grid-cols-2">
                                            {/* Trivy Stats */}
                                            <div className="space-y-4 border rounded-lg p-4">
                                                <div className="flex items-center justify-between">
                                                    <h4 className="font-semibold flex items-center gap-2">
                                                        Trivy Security
                                                    </h4>
                                                    <Badge variant={qualityReport.scan_metrics_summary.trivy_coverage_pct > 80 ? "default" : "secondary"}>
                                                        {qualityReport.scan_metrics_summary.trivy_coverage_pct.toFixed(1)}% Coverage
                                                    </Badge>
                                                </div>
                                                <div className="grid grid-cols-2 gap-4 text-sm">
                                                    <div>
                                                        <p className="text-muted-foreground">Builds Scanned</p>
                                                        <p className="font-medium">{qualityReport.scan_metrics_summary.trivy_builds_scanned}</p>
                                                    </div>
                                                    <div>
                                                        <p className="text-muted-foreground">With Metrics</p>
                                                        <p className="font-medium">{qualityReport.scan_metrics_summary.trivy_builds_with_metrics}</p>
                                                    </div>
                                                </div>
                                                <Progress value={qualityReport.scan_metrics_summary.trivy_coverage_pct} className="h-2" />
                                            </div>

                                            {/* SonarQube Stats */}
                                            <div className="space-y-4 border rounded-lg p-4">
                                                <div className="flex items-center justify-between">
                                                    <h4 className="font-semibold flex items-center gap-2">
                                                        SonarQube Quality
                                                    </h4>
                                                    <Badge variant={qualityReport.scan_metrics_summary.sonarqube_coverage_pct > 80 ? "default" : "secondary"}>
                                                        {qualityReport.scan_metrics_summary.sonarqube_coverage_pct.toFixed(1)}% Coverage
                                                    </Badge>
                                                </div>
                                                <div className="grid grid-cols-2 gap-4 text-sm">
                                                    <div>
                                                        <p className="text-muted-foreground">Builds Scanned</p>
                                                        <p className="font-medium">{qualityReport.scan_metrics_summary.sonarqube_builds_scanned}</p>
                                                    </div>
                                                    <div>
                                                        <p className="text-muted-foreground">With Metrics</p>
                                                        <p className="font-medium">{qualityReport.scan_metrics_summary.sonarqube_builds_with_metrics}</p>
                                                    </div>
                                                </div>
                                                <Progress value={qualityReport.scan_metrics_summary.sonarqube_coverage_pct} className="h-2" />
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            )}

                            {/* Issues List */}
                            {qualityReport.issues && qualityReport.issues.length > 0 && (
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Quality Issues</CardTitle>
                                        <CardDescription>
                                            Issues detected during quality evaluation
                                        </CardDescription>
                                    </CardHeader>
                                    <CardContent className="space-y-2">
                                        {qualityReport.issues.map((issue, idx) => (
                                            <Alert key={idx} variant={issue.severity === "error" ? "destructive" : "default"}>
                                                <AlertTitle className="capitalize">{issue.category} Issue</AlertTitle>
                                                <AlertDescription>
                                                    {issue.message}
                                                    {issue.feature_name && (
                                                        <span className="block mt-1 text-xs font-semibold">
                                                            Feature: {issue.feature_name}
                                                        </span>
                                                    )}
                                                </AlertDescription>
                                            </Alert>
                                        ))}
                                    </CardContent>
                                </Card>
                            )}
                        </>
                    ) : (
                        <div className="text-center py-12 text-muted-foreground border rounded-lg bg-muted/20">
                            <p>Data quality report not available yet. Process the scenario to generate report.</p>
                        </div>
                    )}
                </TabsContent>

                {/* Class Distribution Tab (Existing Content) */}
                <TabsContent value="distribution" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>
                                Class Distribution
                            </CardTitle>
                            <CardDescription>
                                Distribution of build outcomes across the entire dataset
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {/* ... (Keep existing distribution logic) ... */}
                            {totalSamples > 0 ? (
                                <>
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
                                                <div className="flex h-2 rounded-lg overflow-hidden mb-2">
                                                    <div className="bg-green-500" style={{ width: `${splitSuccessPct}%` }} />
                                                    <div className="bg-red-500" style={{ width: `${100 - splitSuccessPct}%` }} />
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
                </TabsContent>

                {/* Features & Scans Tab */}
                <TabsContent value="features" className="space-y-4">
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

                    {/* List feature metrics if available */}
                    {qualityReport?.feature_metrics && (
                        <Card>
                            <CardHeader>
                                <CardTitle>Feature Metrics Detail</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-4">
                                    {qualityReport.feature_metrics.slice(0, 10).map((metric) => (
                                        <div key={metric.feature_name} className="flex items-center justify-between p-2 border-b last:border-0">
                                            <div>
                                                <p className="font-medium">{metric.feature_name}</p>
                                                <div className="flex gap-2 text-xs text-muted-foreground">
                                                    <Badge variant="outline" className="text-[10px]">{metric.source}</Badge>
                                                    <span>{metric.data_type}</span>
                                                </div>
                                            </div>
                                            <div className="text-right">
                                                <p className="text-sm">{metric.completeness_pct.toFixed(1)}% Complete</p>
                                                {metric.issues.length > 0 && (
                                                    <Badge variant="destructive" className="text-[10px]">{metric.issues.length} Issues</Badge>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                    {qualityReport.feature_metrics.length > 10 && (
                                        <p className="text-center text-sm text-muted-foreground pt-2">
                                            And {qualityReport.feature_metrics.length - 10} more features...
                                        </p>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>
            </Tabs>
        </div>
    );
}
