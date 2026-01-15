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
import { Loader2, Shield, BarChart3, AlertCircle, RefreshCw, Clock, Bug, Code, AlertTriangle } from "lucide-react";
import {
    trainingScenariosApi,
    TrainingScenarioRecord,
    DataQualityReport,
} from "@/lib/api/training-scenarios";
import { statisticsApi, ScanMetricsStatisticsResponse, FeatureDistributionResponse, NumericDistribution } from "@/lib/api/statistics";
import { FeatureDistributionChart } from "@/components/analysis/feature-distribution-chart";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { useSSE } from "@/contexts/sse-context";

export default function ScenarioAnalysisPage() {
    const params = useParams<{ scenarioId: string }>();
    const scenarioId = params.scenarioId;
    const { subscribe } = useSSE();

    const [scenario, setScenario] = useState<TrainingScenarioRecord | null>(null);
    const [qualityReport, setQualityReport] = useState<DataQualityReport | null>(null);
    const [trivyStats, setTrivyStats] = useState<ScanMetricsStatisticsResponse | null>(null);
    const [sonarStats, setSonarStats] = useState<ScanMetricsStatisticsResponse | null>(null);
    const [distributions, setDistributions] = useState<FeatureDistributionResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [activeTab, setActiveTab] = useState("features");

    const fetchData = useCallback(async () => {
        try {
            const [scenarioData, qualityData] = await Promise.all([
                trainingScenariosApi.get(scenarioId),
                trainingScenariosApi.getAnalysis(scenarioId),
            ]);
            setScenario(scenarioData);
            setQualityReport(qualityData);

            // Fetch statistics if features are extracted (only distributions initially)
            if (scenarioData.feature_extraction_completed || scenarioData.status === "processed") {
                try {
                    const distributionsData = await statisticsApi.getDistributions(scenarioId);
                    setDistributions(distributionsData);
                } catch (err) {
                    console.warn("Failed to fetch statistics:", err);
                }
            }
        } catch (err) {
            console.error("Failed to fetch analysis data:", err);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, [scenarioId]);

    // Fetch tab-specific data when active tab changes
    useEffect(() => {
        if (!scenarioId || loading) return;

        const fetchTabStats = async () => {
            if (activeTab === "trivy" && !trivyStats) {
                try {
                    const data = await statisticsApi.getScanMetrics(scenarioId, "trivy");
                    setTrivyStats(data);
                } catch (err) {
                    console.error("Failed to fetch trivy stats:", err);
                }
            } else if (activeTab === "sonarqube" && !sonarStats) {
                try {
                    const data = await statisticsApi.getScanMetrics(scenarioId, "sonarqube");
                    setSonarStats(data);
                } catch (err) {
                    console.error("Failed to fetch sonarqube stats:", err);
                }
            }
        };

        fetchTabStats();
    }, [activeTab, scenarioId, loading, trivyStats, sonarStats]);

    const handleRefresh = async () => {
        setRefreshing(true);
        // Clear cached stats to force refetch
        setTrivyStats(null);
        setSonarStats(null);
        await fetchData();
    };

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    // Subscribe to SSE for real-time updates when scans complete
    useEffect(() => {
        const unsubscribe = subscribe("SCENARIO.UPDATED", (data: { scenario_id?: string }) => {
            if (data.scenario_id === scenarioId) {
                fetchData();
            }
        });
        return () => unsubscribe();
    }, [subscribe, scenarioId, fetchData]);

    // =============================================================================
    // Derived State for Progressive Availability
    // =============================================================================

    const isProcessing = scenario?.status === "processing";
    const isProcessed = scenario?.status === "processed";
    const featuresCompleted = scenario?.feature_extraction_completed ?? false;
    const scansCompleted = scenario?.scan_extraction_completed ?? false;

    // Scan progress
    const scansTotal = scenario?.scans_total ?? 0;
    const scansFinished = (scenario?.scans_completed ?? 0) + (scenario?.scans_failed ?? 0);
    const scansProgress = scansTotal > 0 ? Math.round((scansFinished / scansTotal) * 100) : 0;
    const scansRunning = scansTotal > 0 && !scansCompleted;

    if (loading || !scenario) {
        return (
            <div className="flex min-h-[400px] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    // =============================================================================
    // Case 1: Features not done yet (still PROCESSING or early states)
    // =============================================================================
    if (!featuresCompleted && !isProcessed) {
        return (
            <div className="space-y-6">
                <h2 className="text-2xl font-bold tracking-tight">Dataset Analysis</h2>
                <Card>
                    <CardContent className="py-12">
                        <div className="flex flex-col items-center gap-4 text-center">
                            <div className="p-4 rounded-full bg-muted">
                                {isProcessing ? (
                                    <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
                                ) : (
                                    <Clock className="h-8 w-8 text-muted-foreground" />
                                )}
                            </div>
                            <div>
                                <h3 className="font-semibold">
                                    {isProcessing ? "Feature Extraction in Progress" : "Analysis Not Available"}
                                </h3>
                                <p className="text-sm text-muted-foreground mt-1">
                                    {isProcessing
                                        ? `Extracting features... ${scenario.builds_features_extracted}/${scenario.builds_total} builds processed`
                                        : "Start the processing phase to extract features and generate analysis."
                                    }
                                </p>
                            </div>
                            <Badge variant="outline" className="text-sm">
                                Status: {scenario.status}
                            </Badge>
                            {isProcessing && (
                                <Progress
                                    value={(scenario.builds_features_extracted / Math.max(scenario.builds_total, 1)) * 100}
                                    className="w-64 h-2"
                                />
                            )}
                        </div>
                    </CardContent>
                </Card>
            </div>
        );
    }

    // =============================================================================
    // Case 2 & 3: Features done - show analysis (with or without complete scans)
    // =============================================================================

    // =============================================================================
    // Helper & Render Logic
    // =============================================================================

    const getScoreColor = (score: number | undefined | null, type: 'text' | 'bg') => {
        const val = score ?? 0;
        if (val >= 90) return type === 'text' ? 'text-green-600 dark:text-green-500' : 'bg-green-500';
        if (val >= 70) return type === 'text' ? 'text-yellow-600 dark:text-yellow-500' : 'bg-yellow-500';
        return type === 'text' ? 'text-red-600 dark:text-red-500' : 'bg-red-500';
    };

    const getProgressClass = (score: number | undefined | null) => {
        const val = score ?? 0;
        // Tailwind doesn't support dynamic class construction like `[&>div]:${color}` well with JIT if not seen.
        // We must return full static class strings.
        if (val >= 90) return "[&>div]:bg-green-500";
        if (val >= 70) return "[&>div]:bg-yellow-500";
        return "[&>div]:bg-red-500";
    };

    const getBadgeClass = (score: number | undefined | null) => {
        const val = score ?? 0;
        if (val >= 90) return "bg-green-600 hover:bg-green-700";
        if (val >= 70) return "bg-yellow-600 hover:bg-yellow-700";
        return "bg-red-600 hover:bg-red-700";
    };

    // If no quality report yet but features are done, show message
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
                                <h3 className="font-semibold">Quality Report Pending</h3>
                                <p className="text-sm text-muted-foreground mt-1">
                                    {qualityReport?.message || "The quality report is being generated. Please refresh shortly."}
                                </p>
                            </div>
                            <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing}>
                                {refreshing ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <RefreshCw className="h-4 w-4 mr-2" />}
                                Refresh
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold tracking-tight">Dataset Analysis</h2>
                <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing}>
                    {refreshing ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <RefreshCw className="h-4 w-4 mr-2" />}
                    Refresh
                </Button>
            </div>

            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
                <TabsList>
                    <TabsTrigger value="features">Features</TabsTrigger>
                    <TabsTrigger value="trivy">Trivy Security</TabsTrigger>
                    <TabsTrigger value="sonarqube">SonarQube Quality</TabsTrigger>
                </TabsList>

                {/* Features Tab (Merged with Data Quality) */}
                <TabsContent value="features" className="space-y-4">
                    {qualityReport ? (
                        <>
                            {/* Overall Scores */}
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                                <Card>
                                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                        <CardTitle className="text-sm font-medium">Completeness</CardTitle>
                                        <div className={`text-2xl font-bold ${getScoreColor(qualityReport.completeness_score, 'text')}`}>
                                            {(qualityReport.completeness_score ?? 0).toFixed(1)}%
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        <Progress
                                            value={qualityReport.completeness_score ?? 0}
                                            className={`h-2 ${getProgressClass(qualityReport.completeness_score)}`}
                                        />
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                        <CardTitle className="text-sm font-medium">Validity</CardTitle>
                                        <div className={`text-2xl font-bold ${getScoreColor(qualityReport.validity_score, 'text')}`}>
                                            {(qualityReport.validity_score ?? 0).toFixed(1)}%
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        <Progress
                                            value={qualityReport.validity_score ?? 0}
                                            className={`h-2 ${getProgressClass(qualityReport.validity_score)}`}
                                        />
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                        <CardTitle className="text-sm font-medium">Consistency</CardTitle>
                                        <div className={`text-2xl font-bold ${getScoreColor(qualityReport.consistency_score, 'text')}`}>
                                            {(qualityReport.consistency_score ?? 0).toFixed(1)}%
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        <Progress
                                            value={qualityReport.consistency_score ?? 0}
                                            className={`h-2 ${getProgressClass(qualityReport.consistency_score)}`}
                                        />
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                        <CardTitle className="text-sm font-medium">Coverage</CardTitle>
                                        <div className={`text-2xl font-bold ${getScoreColor(qualityReport.coverage_score, 'text')}`}>
                                            {(qualityReport.coverage_score ?? 0).toFixed(1)}%
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        <Progress
                                            value={qualityReport.coverage_score ?? 0}
                                            className={`h-2 ${getProgressClass(qualityReport.coverage_score)}`}
                                        />
                                    </CardContent>
                                </Card>
                            </div>



                            {/* Issues List */}
                            {qualityReport.issues && qualityReport.issues.length > 0 && (
                                <Card>
                                    <CardHeader className="pb-3">
                                        <CardTitle className="text-base">Quality Issues ({qualityReport.issues.length})</CardTitle>
                                    </CardHeader>
                                    <CardContent className="max-h-48 overflow-y-auto">
                                        <ul className="space-y-1 text-sm">
                                            {qualityReport.issues.map((issue, idx) => (
                                                <li key={idx} className="flex items-start gap-2">
                                                    <span className={`inline-block w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${issue.severity === "error" ? "bg-red-500" :
                                                        issue.severity === "warning" ? "bg-amber-500" : "bg-blue-500"
                                                        }`}></span>
                                                    <span className="text-muted-foreground">{issue.message}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </CardContent>
                                </Card>
                            )}

                            {/* Feature Summary & Metrics - Only if features exist */}
                            {qualityReport.feature_metrics && qualityReport.feature_metrics.length > 0 && (
                                <>

                                    {/* Feature Summary */}
                                    <Card>
                                        <CardHeader>
                                            <CardTitle>Feature Summary</CardTitle>
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
                                            <div className="overflow-x-auto max-h-[500px] overflow-y-auto relative">
                                                <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                                                    <thead className="bg-slate-50 dark:bg-slate-900/40 sticky top-0 z-10 shadow-sm">
                                                        <tr>
                                                            <th className="px-4 py-3 text-left font-medium">Feature Name</th>
                                                            <th className="px-4 py-3 text-left font-medium">Type</th>
                                                            <th className="px-4 py-3 text-right font-medium">Completeness</th>
                                                            <th className="px-4 py-3 text-right font-medium">Null Count</th>
                                                            <th className="px-4 py-3 text-right font-medium">Mean</th>
                                                            <th className="px-4 py-3 text-right font-medium">Issues</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                                                        {qualityReport.feature_metrics
                                                            .filter(m => m.source === "feature")
                                                            .map((metric) => (
                                                                <tr key={metric.feature_name} className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
                                                                    <td className="px-4 py-3 font-medium">{metric.feature_name}</td>
                                                                    <td className="px-4 py-3 text-muted-foreground">{metric.data_type}</td>
                                                                    <td className="px-4 py-3 text-right">
                                                                        <span className={metric.completeness_pct < 90 ? "text-amber-600" : "text-green-600"}>
                                                                            {metric.completeness_pct.toFixed(1)}%
                                                                        </span>
                                                                    </td>
                                                                    <td className="px-4 py-3 text-right text-muted-foreground">
                                                                        {metric.null_count}
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

                                    {/* Feature Distribution Statistics */}
                                    {distributions && Object.keys(distributions.distributions).length > 0 && (
                                        <Card>
                                            <CardHeader>
                                                <CardTitle>Feature Distribution Statistics</CardTitle>
                                                <CardDescription>
                                                    Statistical summary of numeric features across all builds
                                                </CardDescription>
                                            </CardHeader>
                                            <CardContent>
                                                <div className="max-h-[600px] overflow-y-auto pr-2">
                                                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                                        {Object.entries(distributions.distributions)
                                                            .filter(([, dist]) => (dist as NumericDistribution).bins && (dist as NumericDistribution).bins.length > 0)
                                                            .map(([name, dist]) => (
                                                                <FeatureDistributionChart
                                                                    key={name}
                                                                    featureName={name}
                                                                    distribution={dist as NumericDistribution}
                                                                />
                                                            ))}
                                                    </div>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    )}
                                </>
                            )}
                        </>
                    ) : (
                        <div className="text-center py-12 text-muted-foreground border rounded-lg bg-muted/20">
                            <p>No feature metrics available yet.</p>
                        </div>
                    )}
                </TabsContent>

                {/* Scan Metrics Tab */}
                <TabsContent value="trivy" className="space-y-4">
                    {/* Empty State */}
                    {qualityReport?.scan_metrics_summary?.trivy_builds_scanned === 0 ? (
                        <Card>
                            <CardContent className="py-12">
                                <div className="flex flex-col items-center gap-4 text-center">
                                    <div className="p-4 rounded-full bg-muted">
                                        <Shield className="h-8 w-8 text-muted-foreground" />
                                    </div>
                                    <div>
                                        <h3 className="font-semibold">No Trivy Scans Found</h3>
                                        <p className="text-sm text-muted-foreground mt-1">
                                            No Trivy security scans were detected for this scenario.
                                        </p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    ) : !trivyStats ? (
                        <div className="flex min-h-[200px] items-center justify-center">
                            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                        </div>
                    ) : (
                        <>
                            {/* Trivy Card */}
                            <Card>
                                <CardHeader className="pb-3">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <Shield className="h-5 w-5 text-green-600" />
                                            <CardTitle className="text-base">Trivy Security</CardTitle>
                                        </div>
                                        <Badge className={getBadgeClass(trivyStats.scan_summary.trivy_coverage_pct)}>
                                            {trivyStats.scan_summary.trivy_coverage_pct.toFixed(1)}% Coverage
                                        </Badge>
                                    </div>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <Progress value={trivyStats.scan_summary.trivy_coverage_pct} className={`h-2 ${getProgressClass(trivyStats.scan_summary.trivy_coverage_pct)}`} />
                                    <div className="grid grid-cols-3 gap-4 text-sm">
                                        <div className="text-center">
                                            <p className="text-muted-foreground">Scanned</p>
                                            <p className="font-semibold">{trivyStats.scan_summary.builds_with_trivy}</p>
                                        </div>
                                        <div className="text-center">
                                            <p className="text-muted-foreground">Total Builds</p>
                                            <p className="font-semibold">{trivyStats.scan_summary.total_builds}</p>
                                        </div>
                                        <div className="text-center">
                                            <p className="text-muted-foreground">Secrets</p>
                                            <p className="font-semibold">{trivyStats.trivy_summary.secrets_count.count}</p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Vulnerability Summary */}
                            <Card>
                                <CardHeader>
                                    <div className="flex items-center gap-2">
                                        <AlertTriangle className="h-5 w-5 text-red-500" />
                                        <CardTitle className="text-base">Vulnerability Summary</CardTitle>
                                    </div>
                                    <CardDescription>
                                        Aggregated vulnerability counts from {trivyStats.trivy_summary.total_scans} Trivy scans
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid grid-cols-4 gap-3 text-center">
                                        <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
                                            <p className="text-xs text-red-600 dark:text-red-400">Critical</p>
                                            <p className="text-xl font-bold text-red-700 dark:text-red-300">
                                                {trivyStats.trivy_summary.vuln_critical.sum}
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                avg: {trivyStats.trivy_summary.vuln_critical.avg.toFixed(1)}
                                            </p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800">
                                            <p className="text-xs text-orange-600 dark:text-orange-400">High</p>
                                            <p className="text-xl font-bold text-orange-700 dark:text-orange-300">
                                                {trivyStats.trivy_summary.vuln_high.sum}
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                avg: {trivyStats.trivy_summary.vuln_high.avg.toFixed(1)}
                                            </p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
                                            <p className="text-xs text-amber-600 dark:text-amber-400">Medium</p>
                                            <p className="text-xl font-bold text-amber-700 dark:text-amber-300">
                                                {trivyStats.trivy_summary.vuln_medium.sum}
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                avg: {trivyStats.trivy_summary.vuln_medium.avg.toFixed(1)}
                                            </p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
                                            <p className="text-xs text-blue-600 dark:text-blue-400">Low</p>
                                            <p className="text-xl font-bold text-blue-700 dark:text-blue-300">
                                                {trivyStats.trivy_summary.vuln_low.sum}
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                avg: {trivyStats.trivy_summary.vuln_low.avg.toFixed(1)}
                                            </p>
                                        </div>
                                    </div>
                                    <div className="mt-4 flex items-center gap-4 text-sm text-muted-foreground">
                                        <div className="flex items-center gap-1">
                                            <span className="inline-block w-2 h-2 rounded-full bg-red-500"></span>
                                            <span>{trivyStats.trivy_summary.has_critical_count} builds with criticals</span>
                                        </div>
                                        <div className="flex items-center gap-1">
                                            <span className="inline-block w-2 h-2 rounded-full bg-orange-500"></span>
                                            <span>{trivyStats.trivy_summary.has_high_count} builds with highs</span>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Trivy Metrics Detail Table */}
                            {(qualityReport.feature_metrics ?? []).filter(m => m.source === "trivy").length > 0 && (
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Trivy Metrics Detail</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="overflow-x-auto">
                                            <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                                                <thead className="bg-slate-50 dark:bg-slate-900/40">
                                                    <tr>
                                                        <th className="px-4 py-3 text-left font-medium">Metric Name</th>
                                                        <th className="px-4 py-3 text-left font-medium">Type</th>
                                                        <th className="px-4 py-3 text-right font-medium">Completeness</th>
                                                        <th className="px-4 py-3 text-right font-medium">Mean</th>
                                                        <th className="px-4 py-3 text-right font-medium">Issues</th>
                                                    </tr>
                                                </thead>
                                                <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                                                    {(qualityReport.feature_metrics ?? [])
                                                        .filter(m => m.source === "trivy")
                                                        .map((metric) => (
                                                            <tr key={metric.feature_name} className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
                                                                <td className="px-4 py-3 font-medium">{metric.feature_name}</td>
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
                    )}
                </TabsContent>

                <TabsContent value="sonarqube" className="space-y-4">
                    {/* Empty State */}
                    {qualityReport?.scan_metrics_summary?.sonarqube_builds_scanned === 0 ? (
                        <Card>
                            <CardContent className="py-12">
                                <div className="flex flex-col items-center gap-4 text-center">
                                    <div className="p-4 rounded-full bg-muted">
                                        <BarChart3 className="h-8 w-8 text-muted-foreground" />
                                    </div>
                                    <div>
                                        <h3 className="font-semibold">No SonarQube Scans Found</h3>
                                        <p className="text-sm text-muted-foreground mt-1">
                                            No SonarQube quality scans were detected for this scenario.
                                        </p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    ) : !sonarStats ? (
                        <div className="flex min-h-[200px] items-center justify-center">
                            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                        </div>
                    ) : (
                        <>
                            {/* SonarQube Card */}
                            <Card>
                                <CardHeader className="pb-3">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <BarChart3 className="h-5 w-5 text-blue-600" />
                                            <CardTitle className="text-base">SonarQube Quality</CardTitle>
                                        </div>
                                        <Badge className={getBadgeClass(sonarStats.scan_summary.sonar_coverage_pct)}>
                                            {sonarStats.scan_summary.sonar_coverage_pct.toFixed(1)}% Coverage
                                        </Badge>
                                    </div>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <Progress value={sonarStats.scan_summary.sonar_coverage_pct} className={`h-2 ${getProgressClass(sonarStats.scan_summary.sonar_coverage_pct)}`} />
                                    <div className="grid grid-cols-3 gap-4 text-sm">
                                        <div className="text-center">
                                            <p className="text-muted-foreground">Scanned</p>
                                            <p className="font-semibold">{sonarStats.scan_summary.builds_with_sonar}</p>
                                        </div>
                                        <div className="text-center">
                                            <p className="text-muted-foreground">Total Builds</p>
                                            <p className="font-semibold">{sonarStats.scan_summary.total_builds}</p>
                                        </div>
                                        <div className="text-center">
                                            <p className="text-muted-foreground">Issues</p>
                                            <p className="font-semibold">{sonarStats.sonar_summary.bugs.sum + sonarStats.sonar_summary.code_smells.sum}</p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* SonarQube Code Quality Summary */}
                            <Card>
                                <CardHeader>
                                    <div className="flex items-center gap-2">
                                        <Code className="h-5 w-5 text-blue-500" />
                                        <CardTitle className="text-base">Code Quality Summary</CardTitle>
                                    </div>
                                    <CardDescription>
                                        Aggregated metrics from {sonarStats.sonar_summary.total_scans} SonarQube scans
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid grid-cols-4 gap-3 text-center">
                                        <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
                                            <p className="text-xs text-red-600 dark:text-red-400">
                                                <Bug className="h-3 w-3 inline mr-1" />
                                                Bugs
                                            </p>
                                            <p className="text-xl font-bold text-red-700 dark:text-red-300">
                                                {sonarStats.sonar_summary.bugs.sum}
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                avg: {sonarStats.sonar_summary.bugs.avg.toFixed(1)}
                                            </p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
                                            <p className="text-xs text-amber-600 dark:text-amber-400">Code Smells</p>
                                            <p className="text-xl font-bold text-amber-700 dark:text-amber-300">
                                                {sonarStats.sonar_summary.code_smells.sum}
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                avg: {sonarStats.sonar_summary.code_smells.avg.toFixed(1)}
                                            </p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800">
                                            <p className="text-xs text-purple-600 dark:text-purple-400">Vulnerabilities</p>
                                            <p className="text-xl font-bold text-purple-700 dark:text-purple-300">
                                                {sonarStats.sonar_summary.vulnerabilities.sum}
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                avg: {sonarStats.sonar_summary.vulnerabilities.avg.toFixed(1)}
                                            </p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800">
                                            <p className="text-xs text-orange-600 dark:text-orange-400">Hotspots</p>
                                            <p className="text-xl font-bold text-orange-700 dark:text-orange-300">
                                                {sonarStats.sonar_summary.security_hotspots.sum}
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                avg: {sonarStats.sonar_summary.security_hotspots.avg.toFixed(1)}
                                            </p>
                                        </div>
                                    </div>
                                    <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
                                        <div className="text-center p-2 border rounded-lg">
                                            <p className="text-muted-foreground">Reliability</p>
                                            <p className="font-semibold">
                                                {sonarStats.sonar_summary.reliability_rating_avg?.toFixed(1) ?? "N/A"}
                                            </p>
                                        </div>
                                        <div className="text-center p-2 border rounded-lg">
                                            <p className="text-muted-foreground">Security</p>
                                            <p className="font-semibold">
                                                {sonarStats.sonar_summary.security_rating_avg?.toFixed(1) ?? "N/A"}
                                            </p>
                                        </div>
                                        <div className="text-center p-2 border rounded-lg">
                                            <p className="text-muted-foreground">Maintainability</p>
                                            <p className="font-semibold">
                                                {sonarStats.sonar_summary.maintainability_rating_avg?.toFixed(1) ?? "N/A"}
                                            </p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Sonar Metrics Detail Table */}
                            {(qualityReport.feature_metrics ?? []).filter(m => m.source === "sonarqube").length > 0 && (
                                <Card>
                                    <CardHeader>
                                        <CardTitle>SonarQube Metrics Detail</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="overflow-x-auto">
                                            <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                                                <thead className="bg-slate-50 dark:bg-slate-900/40">
                                                    <tr>
                                                        <th className="px-4 py-3 text-left font-medium">Metric Name</th>
                                                        <th className="px-4 py-3 text-left font-medium">Type</th>
                                                        <th className="px-4 py-3 text-right font-medium">Completeness</th>
                                                        <th className="px-4 py-3 text-right font-medium">Mean</th>
                                                        <th className="px-4 py-3 text-right font-medium">Issues</th>
                                                    </tr>
                                                </thead>
                                                <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                                                    {(qualityReport.feature_metrics ?? [])
                                                        .filter(m => m.source === "sonarqube")
                                                        .map((metric) => (
                                                            <tr key={metric.feature_name} className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
                                                                <td className="px-4 py-3 font-medium">{metric.feature_name}</td>
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
                    )}
                </TabsContent>
            </Tabs >
        </div >
    );
}
