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
import { Loader2, Shield, BarChart3, AlertCircle } from "lucide-react";
import {
    trainingScenariosApi,
    TrainingScenarioRecord,
    DataQualityReport,
} from "@/lib/api/training-scenarios";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function ScenarioAnalysisPage() {
    const params = useParams<{ scenarioId: string }>();
    const scenarioId = params.scenarioId;

    const [scenario, setScenario] = useState<TrainingScenarioRecord | null>(null);
    const [qualityReport, setQualityReport] = useState<DataQualityReport | null>(null);
    const [loading, setLoading] = useState(true);

    const fetchData = useCallback(async () => {
        try {
            const [scenarioData, qualityData] = await Promise.all([
                trainingScenariosApi.get(scenarioId),
                trainingScenariosApi.getAnalysis(scenarioId),
            ]);
            setScenario(scenarioData);
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

    // If report not available, show empty state with message from API
    if (!qualityReport?.available) {
        return (
            <div className="space-y-6">
                <h2 className="text-2xl font-bold tracking-tight">Dataset Analysis</h2>
                <Card>
                    <CardContent className="py-12">
                        <div className="flex flex-col items-center gap-4 text-center">
                            <div className="p-4 rounded-full bg-muted">
                                <AlertCircle className="h-8 w-8 text-muted-foreground" />
                            </div>
                            <div>
                                <h3 className="font-semibold">Analysis Not Available</h3>
                                <p className="text-sm text-muted-foreground mt-1">
                                    {qualityReport?.message || "Complete the processing phase to view data quality analysis."}
                                </p>
                            </div>
                            <Badge variant="outline" className="text-sm">
                                Current status: {qualityReport?.scenario_status || scenario.status}
                            </Badge>
                        </div>
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <h2 className="text-2xl font-bold tracking-tight">Dataset Analysis</h2>

            <Tabs defaultValue="quality" className="space-y-4">
                <TabsList>
                    <TabsTrigger value="quality">Data Quality</TabsTrigger>
                    <TabsTrigger value="features">Features</TabsTrigger>
                    <TabsTrigger value="scans">Scan Metrics</TabsTrigger>
                </TabsList>

                {/* Data Quality Tab */}
                <TabsContent value="quality" className="space-y-4">
                    {qualityReport ? (
                        <>
                            {/* Overall Scores */}
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                                <Card>
                                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                        <CardTitle className="text-sm font-medium">Quality Score</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="text-2xl font-bold">
                                            {(qualityReport.quality_score ?? 0).toFixed(1)}
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
                                            {(qualityReport.completeness_score ?? 0).toFixed(1)}%
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        <Progress value={qualityReport.completeness_score ?? 0} className="h-2" />
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                        <CardTitle className="text-sm font-medium">Validity</CardTitle>
                                        <div className="text-2xl font-bold">
                                            {(qualityReport.validity_score ?? 0).toFixed(1)}%
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        <Progress value={qualityReport.validity_score ?? 0} className="h-2" />
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                        <CardTitle className="text-sm font-medium">Consistency</CardTitle>
                                        <div className="text-2xl font-bold">
                                            {(qualityReport.consistency_score ?? 0).toFixed(1)}%
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        <Progress value={qualityReport.consistency_score ?? 0} className="h-2" />
                                    </CardContent>
                                </Card>
                            </div>

                            {/* Build Statistics */}
                            <Card>
                                <CardHeader>
                                    <CardTitle>Build Statistics</CardTitle>
                                    <CardDescription>
                                        Overview of processed builds in this scenario
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid gap-4 md:grid-cols-4">
                                        <div className="p-4 border rounded-lg text-center">
                                            <p className="text-sm text-muted-foreground">Total Builds</p>
                                            <p className="text-2xl font-bold">{qualityReport.total_builds}</p>
                                        </div>
                                        <div className="p-4 border rounded-lg text-center bg-green-50 dark:bg-green-950/30">
                                            <p className="text-sm text-muted-foreground">Enriched</p>
                                            <p className="text-2xl font-bold text-green-600">{qualityReport.enriched_builds}</p>
                                        </div>
                                        <div className="p-4 border rounded-lg text-center bg-yellow-50 dark:bg-yellow-950/30">
                                            <p className="text-sm text-muted-foreground">Partial</p>
                                            <p className="text-2xl font-bold text-yellow-600">{qualityReport.partial_builds}</p>
                                        </div>
                                        <div className="p-4 border rounded-lg text-center bg-red-50 dark:bg-red-950/30">
                                            <p className="text-sm text-muted-foreground">Failed</p>
                                            <p className="text-2xl font-bold text-red-600">{qualityReport.failed_builds}</p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

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

                {/* Features Tab */}
                <TabsContent value="features" className="space-y-4">
                    {qualityReport?.feature_metrics && qualityReport.feature_metrics.length > 0 ? (
                        <>
                            {/* Feature Summary */}
                            <Card>
                                <CardHeader>
                                    <CardTitle>Feature Summary</CardTitle>
                                    <CardDescription>
                                        Overview of extracted features from the Hamilton DAG
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid gap-4 md:grid-cols-3">
                                        <div className="p-4 border rounded-lg text-center">
                                            <p className="text-sm text-muted-foreground">Total Features</p>
                                            <p className="text-2xl font-bold">{qualityReport.total_features}</p>
                                        </div>
                                        <div className="p-4 border rounded-lg text-center">
                                            <p className="text-sm text-muted-foreground">With Issues</p>
                                            <p className="text-2xl font-bold text-amber-600">{qualityReport.features_with_issues}</p>
                                        </div>
                                        <div className="p-4 border rounded-lg text-center">
                                            <p className="text-sm text-muted-foreground">DAG Features</p>
                                            <p className="text-2xl font-bold">
                                                {qualityReport.feature_metrics.filter(m => m.source === "feature").length}
                                            </p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Feature Metrics Table */}
                            <Card>
                                <CardHeader>
                                    <CardTitle>Feature Metrics Detail</CardTitle>
                                    <CardDescription>
                                        Completeness and quality metrics for each extracted feature
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="overflow-x-auto">
                                        <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                                            <thead className="bg-slate-50 dark:bg-slate-900/40">
                                                <tr>
                                                    <th className="px-4 py-3 text-left font-medium">Feature Name</th>
                                                    <th className="px-4 py-3 text-left font-medium">Source</th>
                                                    <th className="px-4 py-3 text-left font-medium">Type</th>
                                                    <th className="px-4 py-3 text-right font-medium">Completeness</th>
                                                    <th className="px-4 py-3 text-right font-medium">Null Count</th>
                                                    <th className="px-4 py-3 text-right font-medium">Issues</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                                                {qualityReport.feature_metrics
                                                    .filter(m => m.source === "feature")
                                                    .map((metric) => (
                                                        <tr key={metric.feature_name} className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
                                                            <td className="px-4 py-3 font-medium">{metric.feature_name}</td>
                                                            <td className="px-4 py-3">
                                                                <Badge variant="outline" className="text-xs">DAG</Badge>
                                                            </td>
                                                            <td className="px-4 py-3 text-muted-foreground">{metric.data_type}</td>
                                                            <td className="px-4 py-3 text-right">
                                                                <span className={metric.completeness_pct < 90 ? "text-amber-600" : "text-green-600"}>
                                                                    {metric.completeness_pct.toFixed(1)}%
                                                                </span>
                                                            </td>
                                                            <td className="px-4 py-3 text-right text-muted-foreground">
                                                                {metric.null_count}
                                                            </td>
                                                            <td className="px-4 py-3 text-right">
                                                                {metric.issues.length > 0 ? (
                                                                    <Badge variant="destructive" className="text-xs">
                                                                        {metric.issues.length}
                                                                    </Badge>
                                                                ) : (
                                                                    <span className="text-muted-foreground">—</span>
                                                                )}
                                                            </td>
                                                        </tr>
                                                    ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </CardContent>
                            </Card>
                        </>
                    ) : (
                        <div className="text-center py-12 text-muted-foreground border rounded-lg bg-muted/20">
                            <p>No feature metrics available yet.</p>
                        </div>
                    )}
                </TabsContent>

                {/* Scan Metrics Tab */}
                <TabsContent value="scans" className="space-y-4">
                    {qualityReport?.scan_metrics_summary ? (
                        <>
                            {/* Scan Coverage Summary */}
                            <div className="grid gap-4 md:grid-cols-2">
                                {/* Trivy Card */}
                                <Card>
                                    <CardHeader className="pb-3">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <Shield className="h-5 w-5 text-green-600" />
                                                <CardTitle className="text-base">Trivy Security</CardTitle>
                                            </div>
                                            <Badge variant={qualityReport.scan_metrics_summary.trivy_coverage_pct > 80 ? "default" : "secondary"}>
                                                {qualityReport.scan_metrics_summary.trivy_coverage_pct.toFixed(1)}% Coverage
                                            </Badge>
                                        </div>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        <Progress value={qualityReport.scan_metrics_summary.trivy_coverage_pct} className="h-2" />
                                        <div className="grid grid-cols-3 gap-4 text-sm">
                                            <div className="text-center">
                                                <p className="text-muted-foreground">Scanned</p>
                                                <p className="font-semibold">{qualityReport.scan_metrics_summary.trivy_builds_scanned}</p>
                                            </div>
                                            <div className="text-center">
                                                <p className="text-muted-foreground">With Metrics</p>
                                                <p className="font-semibold">{qualityReport.scan_metrics_summary.trivy_builds_with_metrics}</p>
                                            </div>
                                            <div className="text-center">
                                                <p className="text-muted-foreground">Metric Keys</p>
                                                <p className="font-semibold">{qualityReport.scan_metrics_summary.trivy_metrics_count}</p>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>

                                {/* SonarQube Card */}
                                <Card>
                                    <CardHeader className="pb-3">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <BarChart3 className="h-5 w-5 text-blue-600" />
                                                <CardTitle className="text-base">SonarQube Quality</CardTitle>
                                            </div>
                                            <Badge variant={qualityReport.scan_metrics_summary.sonarqube_coverage_pct > 80 ? "default" : "secondary"}>
                                                {qualityReport.scan_metrics_summary.sonarqube_coverage_pct.toFixed(1)}% Coverage
                                            </Badge>
                                        </div>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        <Progress value={qualityReport.scan_metrics_summary.sonarqube_coverage_pct} className="h-2" />
                                        <div className="grid grid-cols-3 gap-4 text-sm">
                                            <div className="text-center">
                                                <p className="text-muted-foreground">Scanned</p>
                                                <p className="font-semibold">{qualityReport.scan_metrics_summary.sonarqube_builds_scanned}</p>
                                            </div>
                                            <div className="text-center">
                                                <p className="text-muted-foreground">With Metrics</p>
                                                <p className="font-semibold">{qualityReport.scan_metrics_summary.sonarqube_builds_with_metrics}</p>
                                            </div>
                                            <div className="text-center">
                                                <p className="text-muted-foreground">Metric Keys</p>
                                                <p className="font-semibold">{qualityReport.scan_metrics_summary.sonarqube_metrics_count}</p>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>

                            {/* Scan Metrics Table */}
                            {(qualityReport.feature_metrics ?? []).filter(m => m.source !== "feature").length > 0 && (
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Scan Metrics Detail</CardTitle>
                                        <CardDescription>
                                            Quality metrics from Trivy and SonarQube scans
                                        </CardDescription>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="overflow-x-auto">
                                            <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                                                <thead className="bg-slate-50 dark:bg-slate-900/40">
                                                    <tr>
                                                        <th className="px-4 py-3 text-left font-medium">Metric Name</th>
                                                        <th className="px-4 py-3 text-left font-medium">Source</th>
                                                        <th className="px-4 py-3 text-left font-medium">Type</th>
                                                        <th className="px-4 py-3 text-right font-medium">Completeness</th>
                                                        <th className="px-4 py-3 text-right font-medium">Mean</th>
                                                        <th className="px-4 py-3 text-right font-medium">Issues</th>
                                                    </tr>
                                                </thead>
                                                <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                                                    {(qualityReport.feature_metrics ?? [])
                                                        .filter(m => m.source !== "feature")
                                                        .map((metric) => (
                                                            <tr key={metric.feature_name} className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
                                                                <td className="px-4 py-3 font-medium">{metric.feature_name}</td>
                                                                <td className="px-4 py-3">
                                                                    <Badge
                                                                        variant="outline"
                                                                        className={`text-xs ${metric.source === "trivy" ? "border-green-500 text-green-600" : "border-blue-500 text-blue-600"}`}
                                                                    >
                                                                        {metric.source === "trivy" ? "Trivy" : "SonarQube"}
                                                                    </Badge>
                                                                </td>
                                                                <td className="px-4 py-3 text-muted-foreground">{metric.data_type}</td>
                                                                <td className="px-4 py-3 text-right">
                                                                    <span className={metric.completeness_pct < 90 ? "text-amber-600" : "text-green-600"}>
                                                                        {metric.completeness_pct.toFixed(1)}%
                                                                    </span>
                                                                </td>
                                                                <td className="px-4 py-3 text-right text-muted-foreground">
                                                                    {metric.mean_value != null ? metric.mean_value.toFixed(2) : "—"}
                                                                </td>
                                                                <td className="px-4 py-3 text-right">
                                                                    {metric.issues.length > 0 ? (
                                                                        <Badge variant="destructive" className="text-xs">
                                                                            {metric.issues.length}
                                                                        </Badge>
                                                                    ) : (
                                                                        <span className="text-muted-foreground">—</span>
                                                                    )}
                                                                </td>
                                                            </tr>
                                                        ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </CardContent>
                                </Card>
                            )}
                        </>
                    ) : (
                        <div className="text-center py-12 text-muted-foreground border rounded-lg bg-muted/20">
                            <p>No scan metrics available yet.</p>
                        </div>
                    )}
                </TabsContent>
            </Tabs>
        </div>
    );
}
