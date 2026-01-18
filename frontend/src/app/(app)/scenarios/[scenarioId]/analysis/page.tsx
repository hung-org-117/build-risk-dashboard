"use client";

import { FeatureDistributionChart } from "@/components/analysis/feature-distribution-chart";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useSSE } from "@/contexts/sse-context";
import { FeatureDistributionResponse, FeatureMetricsResponse, NumericDistribution, ScanMetricsStatisticsResponse, statisticsApi } from "@/lib/api/statistics";
import {
    DataQualityReport,
    TrainingScenarioRecord,
    trainingScenariosApi,
} from "@/lib/api/training-scenarios";
import { AlertCircle, BarChart3, ChevronLeft, ChevronRight, Clock, Loader2, RefreshCw, Search, Shield } from "lucide-react";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";


const ITEMS_PER_PAGE = 6;

const getFeatureCategory = (name: string): string => {
    if (name.startsWith("git_") || name.startsWith("repo_")) return "Source Code";
    if (name.startsWith("build_")) return "Build Process";
    if (name.startsWith("history_") || name.startsWith("temporal_")) return "History & Trends";
    if (name.startsWith("log_") || name.startsWith("test_") || name.startsWith("devops_")) return "CI/CD & Testing";
    if (name.startsWith("author_")) return "Collaboration";
    return "Other";
};

export default function ScenarioAnalysisPage() {
    const params = useParams<{ scenarioId: string }>();
    const scenarioId = params.scenarioId;
    const { subscribe } = useSSE();
    const router = useRouter();
    const searchParams = useSearchParams();
    const pathname = usePathname();

    // Get tab from URL or default to "features"
    const activeTab = searchParams.get("tab") || "features";

    // Sync URL when tab changes
    const handleTabChange = useCallback((value: string) => {
        const newParams = new URLSearchParams(searchParams.toString());
        newParams.set("tab", value);
        router.push(`${pathname}?${newParams.toString()}`);
    }, [pathname, router, searchParams]);

    const [scenario, setScenario] = useState<TrainingScenarioRecord | null>(null);
    const [qualityReport, setQualityReport] = useState<DataQualityReport | null>(null);
    // Integration stats
    const [trivyStats, setTrivyStats] = useState<ScanMetricsStatisticsResponse | null>(null);
    const [sonarStats, setSonarStats] = useState<ScanMetricsStatisticsResponse | null>(null);
    const [scanDistributions, setScanDistributions] = useState<FeatureDistributionResponse | null>(null); // Placeholder for scan distributions if we separate API

    // Feature distributions
    const [distributions, setDistributions] = useState<FeatureDistributionResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    // Feature Distribution UI State
    const [distributionSearch, setDistributionSearch] = useState("");
    const [distributionPage, setDistributionPage] = useState(1);

    // Feature Metrics UI State
    const [metricsData, setMetricsData] = useState<FeatureMetricsResponse | null>(null);
    const [metricsPage, setMetricsPage] = useState(1);
    const [metricsSearch, setMetricsSearch] = useState("");
    const [metricsLoading, setMetricsLoading] = useState(false);

    // Scan Metrics Distribution UI State
    const [scanDistributionPage, setScanDistributionPage] = useState(1);
    const [scanDistributionSearch, setScanDistributionSearch] = useState("");

    // 1. Fetch Scenario Details (Controlled by scenarioId)
    const fetchScenario = useCallback(async () => {
        try {
            const data = await trainingScenariosApi.get(scenarioId);
            setScenario(data);
        } catch (err) {
            console.error("Failed to fetch scenario:", err);
        }
    }, [scenarioId]);

    // Scenario Effect
    useEffect(() => {
        if (scenarioId) {
            fetchScenario();
        }
    }, [fetchScenario, scenarioId]);

    // 2. Fetch Features Tab Data (Quality Report, Metrics, Distributions)
    const fetchFeatureData = useCallback(async () => {
        if (!scenarioId) return;
        setLoading(true);
        try {
            const [qualityData, metricData, distributionData] = await Promise.all([
                trainingScenariosApi.getAnalysis(scenarioId),
                statisticsApi.getFeatureMetrics(scenarioId, {
                    page: metricsPage,
                    limit: 10,
                    search: metricsSearch
                }),
                statisticsApi.getDistributions(scenarioId, {
                    page: distributionPage,
                    limit: 6,
                    search: distributionSearch,
                    category: "All"
                })
            ]);
            setQualityReport(qualityData);
            setMetricsData(metricData);
            setDistributions(distributionData);
        } catch (err) {
            console.error("Failed to fetch features tab data:", err);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, [scenarioId, metricsPage, metricsSearch, distributionPage, distributionSearch]);

    // Features Effect
    useEffect(() => {
        if (scenarioId && activeTab === "features") {
            fetchFeatureData();
        }
    }, [fetchFeatureData, scenarioId, activeTab]);

    // 3. Fetch Integration Tab Data (Scan Stats)
    // Note: Depends on qualityReport existence but NOT its value to avoid loops set by setQualityReport
    const fetchIntegrationData = useCallback(async () => {
        if (!scenarioId) return;
        setLoading(true);
        try {
            // Parallel fetch for Trivy and Sonar
            const [trivyData, sonarData] = await Promise.all([
                statisticsApi.getScanMetrics(scenarioId, "trivy"),
                statisticsApi.getScanMetrics(scenarioId, "sonarqube"),
            ]);
            setTrivyStats(trivyData);
            setSonarStats(sonarData);

            // Fetch quality report if missing (needed for distributions), independent of main flow
            if (!qualityReport) {
                const qualityData = await trainingScenariosApi.getAnalysis(scenarioId);
                setQualityReport(qualityData);
            }

        } catch (err) {
            console.error("Failed to fetch integration tab data:", err);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, [scenarioId, qualityReport]); // Depends on qualityReport to know if it's missing, but logic prevents loop? 
    // Wait, if qualityReport is null -> fetch -> setQualityReport -> fetchIntegrationData changes -> Effect runs -> qualityReport is NOT null -> no fetch -> no set. Loop broken. Correct.

    // Integration Effect
    useEffect(() => {
        if (scenarioId && activeTab === "integration") {
            fetchIntegrationData();
        }
    }, [fetchIntegrationData, scenarioId, activeTab]);

    // Subscribe to SSE for updates - trigger specific refreshes
    useEffect(() => {
        const unsubscribe = subscribe("SCENARIO.UPDATED", (data: { scenario_id?: string }) => {
            if (data.scenario_id === scenarioId) {
                fetchScenario(); // Always update scenario status
                if (activeTab === "features") fetchFeatureData();
                if (activeTab === "integration") fetchIntegrationData();
            }
        });
        return () => unsubscribe();
    }, [subscribe, scenarioId, activeTab, fetchScenario, fetchFeatureData, fetchIntegrationData]);

    const handleRefresh = () => {
        setRefreshing(true);
        // Reset local caches?
        setTrivyStats(null);
        setSonarStats(null);
        // Trigger re-fetch based on active tab
        if (activeTab === "features") fetchFeatureData();
        if (activeTab === "integration") fetchIntegrationData();
    };

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

            <Tabs value={activeTab} onValueChange={handleTabChange} className="space-y-4">
                <TabsList className="w-full grid grid-cols-2">
                    <TabsTrigger value="features">Features</TabsTrigger>
                    <TabsTrigger value="integration">Integration Tools</TabsTrigger>
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
                                    {/* Feature Metrics Table (Server-Side Paginated) */}
                                    {metricsData && (
                                        <Card>
                                            <CardHeader>
                                                <div className="flex flex-col gap-4">
                                                    <div className="flex items-center justify-between">
                                                        <div>
                                                            <CardTitle>Feature Metrics Detail</CardTitle>
                                                            <CardDescription>Completeness and quality metrics for each extracted feature</CardDescription>
                                                        </div>
                                                        <div className="flex items-center gap-2">
                                                            <div className="relative w-64">
                                                                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                                                <Input
                                                                    placeholder="Search metrics..."
                                                                    value={metricsSearch}
                                                                    onChange={(e) => {
                                                                        setMetricsSearch(e.target.value);
                                                                        setMetricsPage(1);
                                                                    }}
                                                                    className="pl-8"
                                                                />
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                            </CardHeader>
                                            <CardContent>
                                                {metricsLoading ? (
                                                    <div className="py-12 flex justify-center">
                                                        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                                                    </div>
                                                ) : metricsData.items.length === 0 ? (
                                                    <div className="text-center py-12 text-muted-foreground">No metrics found matching your criteria.</div>
                                                ) : (
                                                    <div className="space-y-4">
                                                        <div className="overflow-x-auto relative rounded-md border">
                                                            <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                                                                <thead className="bg-slate-50 dark:bg-slate-900/40">
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
                                                                    {metricsData.items.map((metric) => (
                                                                        <tr key={metric.feature_name} className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
                                                                            <td className="px-4 py-3 font-medium">{metric.feature_name}</td>
                                                                            <td className="px-4 py-3 text-muted-foreground">{metric.data_type}</td>
                                                                            <td className="px-4 py-3 text-right">
                                                                                <span className={metric.completeness < 90 ? "text-amber-600" : "text-green-600"}>
                                                                                    {metric.completeness.toFixed(1)}%
                                                                                </span>
                                                                            </td>
                                                                            <td className="px-4 py-3 text-right text-muted-foreground">
                                                                                {metric.null_count}
                                                                            </td>
                                                                            <td className="px-4 py-3 text-right text-muted-foreground">
                                                                                {metric.mean != null ? metric.mean.toFixed(2) : "—"}
                                                                            </td>
                                                                            <td className="px-4 py-3 text-right">
                                                                                {metric.issues_count > 0 ? (
                                                                                    <Badge variant="destructive" className="text-xs">
                                                                                        {metric.issues_count}
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

                                                        {/* Metrics Pagination */}
                                                        {metricsData.total_pages > 1 && (
                                                            <div className="flex items-center justify-between pt-2">
                                                                <div className="text-sm text-muted-foreground">
                                                                    Showing {(metricsPage - 1) * 10 + 1} to {Math.min(metricsPage * 10, metricsData.total_items)} of {metricsData.total_items} entries
                                                                </div>
                                                                <div className="flex items-center gap-2">
                                                                    <Button
                                                                        variant="outline"
                                                                        size="sm"
                                                                        onClick={() => setMetricsPage(p => Math.max(1, p - 1))}
                                                                        disabled={metricsPage === 1}
                                                                    >
                                                                        <ChevronLeft className="h-4 w-4" />
                                                                    </Button>
                                                                    <span className="text-sm font-medium">Page {metricsPage} of {metricsData.total_pages}</span>
                                                                    <Button
                                                                        variant="outline"
                                                                        size="sm"
                                                                        onClick={() => setMetricsPage(p => Math.min(metricsData.total_pages, p + 1))}
                                                                        disabled={metricsPage === metricsData.total_pages}
                                                                    >
                                                                        <ChevronRight className="h-4 w-4" />
                                                                    </Button>
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                )}
                                            </CardContent>
                                        </Card>
                                    )}

                                    {/* Feature Distribution Statistics */}
                                    {distributions && Object.keys(distributions.distributions).length > 0 && (
                                        <Card>
                                            <CardHeader>
                                                <div className="flex flex-col gap-4">
                                                    <div className="flex items-center justify-between">
                                                        <div>
                                                            <CardTitle>Feature Distribution Statistics</CardTitle>
                                                            <CardDescription>
                                                                Statistical summary of numeric features across all builds
                                                            </CardDescription>
                                                        </div>
                                                        <div className="flex items-center gap-2">
                                                            <div className="relative w-64">
                                                                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                                                <Input
                                                                    placeholder="Search features..."
                                                                    value={distributionSearch}
                                                                    onChange={(e) => {
                                                                        setDistributionSearch(e.target.value);
                                                                        setDistributionPage(1);
                                                                    }}
                                                                    className="pl-8"
                                                                />
                                                            </div>
                                                        </div>
                                                    </div>

                                                </div>
                                            </CardHeader>
                                            <CardContent>
                                                {distributions.total_items === 0 ? (
                                                    <div className="text-center py-12 text-muted-foreground">No features found matching your criteria.</div>
                                                ) : (
                                                    <div className="space-y-4">
                                                        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                                            {Object.entries(distributions.distributions)
                                                                .filter(([, dist]) => (dist as NumericDistribution).bins)
                                                                .map(([name, dist]) => (
                                                                    <FeatureDistributionChart
                                                                        key={name}
                                                                        featureName={name}
                                                                        distribution={dist as NumericDistribution}
                                                                    />
                                                                ))}
                                                        </div>

                                                        {distributions.total_pages > 1 && (
                                                            <div className="flex items-center justify-between pt-4 border-t">
                                                                <div className="text-sm text-muted-foreground">
                                                                    Showing {(distributions.current_page - 1) * 6 + 1} to {Math.min(distributions.current_page * 6, distributions.total_items)} of {distributions.total_items} entries
                                                                </div>
                                                                <div className="flex items-center gap-2">
                                                                    <Button
                                                                        variant="outline"
                                                                        size="sm"
                                                                        onClick={() => setDistributionPage(p => Math.max(1, p - 1))}
                                                                        disabled={distributions.current_page === 1}
                                                                    >
                                                                        <ChevronLeft className="h-4 w-4" />
                                                                    </Button>
                                                                    <span className="text-sm font-medium">Page {distributions.current_page} of {distributions.total_pages}</span>
                                                                    <Button
                                                                        variant="outline"
                                                                        size="sm"
                                                                        onClick={() => setDistributionPage(p => Math.min(distributions.total_pages, p + 1))}
                                                                        disabled={distributions.current_page === distributions.total_pages}
                                                                    >
                                                                        <ChevronRight className="h-4 w-4" />
                                                                    </Button>
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                )}
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

                {/* Integration Tools Tab (Combined) */}
                <TabsContent value="integration" className="space-y-8">
                    {/* TRIVY SECTION */}
                    <div className="space-y-4">
                        <div className="flex items-center gap-2 pb-2 border-b">
                            <Shield className="h-5 w-5 text-blue-500" />
                            <h3 className="text-lg font-semibold tracking-tight">Trivy Security Scanning</h3>
                        </div>

                        {/* Empty State - Check trivyStats directly, not qualityReport.scan_metrics_summary */}
                        {!trivyStats ? (
                            <div className="flex min-h-[150px] items-center justify-center border rounded-md">
                                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : trivyStats.scan_summary.builds_with_trivy === 0 ? (
                            <Card>
                                <CardContent className="py-8">
                                    <div className="flex flex-col items-center gap-4 text-center">
                                        <p className="text-sm text-muted-foreground">
                                            No Trivy security scans were detected for this scenario.
                                        </p>
                                    </div>
                                </CardContent>
                            </Card>
                        ) : (
                            <>
                                {/* Trivy Overview Cards */}
                                <div className="grid gap-4 md:grid-cols-2">
                                    <Card>
                                        <CardHeader className="pb-3">
                                            <div className="flex items-center justify-between">
                                                <CardTitle className="text-base">Coverage</CardTitle>
                                                <Badge className={getBadgeClass(trivyStats.scan_summary.trivy_coverage_pct)}>
                                                    {trivyStats.scan_summary.trivy_coverage_pct.toFixed(1)}%
                                                </Badge>
                                            </div>
                                        </CardHeader>
                                        <CardContent className="space-y-4">
                                            <Progress value={trivyStats.scan_summary.trivy_coverage_pct} className={`h-2 ${getProgressClass(trivyStats.scan_summary.trivy_coverage_pct)}`} />
                                            <div className="grid grid-cols-2 gap-4 text-sm">
                                                <div>
                                                    <p className="text-muted-foreground">Scanned Builds</p>
                                                    <p className="font-semibold">{trivyStats.scan_summary.builds_with_trivy} / {trivyStats.scan_summary.total_builds}</p>
                                                </div>
                                                <div className="text-right">
                                                    <p className="text-muted-foreground">Secrets Found</p>
                                                    <p className="font-semibold">{trivyStats.trivy_summary?.secrets_count.count ?? 0}</p>
                                                </div>
                                            </div>
                                        </CardContent>
                                    </Card>

                                    {/* Vulnerability Summary */}
                                    <Card>
                                        <CardHeader className="pb-3">
                                            <CardTitle className="text-base">Vulnerabilities</CardTitle>
                                            <CardDescription>
                                                Avg/Total across {trivyStats.trivy_summary?.total_scans ?? 0} scans
                                            </CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="grid grid-cols-4 gap-2 text-center">
                                                <div className="p-2 rounded bg-red-50 dark:bg-red-900/10">
                                                    <p className="text-xs font-semibold text-red-600">Crit</p>
                                                    <p className="font-mono font-bold text-red-700">{trivyStats.trivy_summary?.vuln_critical.sum ?? 0}</p>
                                                </div>
                                                <div className="p-2 rounded bg-orange-50 dark:bg-orange-900/10">
                                                    <p className="text-xs font-semibold text-orange-600">High</p>
                                                    <p className="font-mono font-bold text-orange-700">{trivyStats.trivy_summary?.vuln_high.sum ?? 0}</p>
                                                </div>
                                                <div className="p-2 rounded bg-amber-50 dark:bg-amber-900/10">
                                                    <p className="text-xs font-semibold text-amber-600">Med</p>
                                                    <p className="font-mono font-bold text-amber-700">{trivyStats.trivy_summary?.vuln_medium.sum ?? 0}</p>
                                                </div>
                                                <div className="p-2 rounded bg-blue-50 dark:bg-blue-900/10">
                                                    <p className="text-xs font-semibold text-blue-600">Low</p>
                                                    <p className="font-mono font-bold text-blue-700">{trivyStats.trivy_summary?.vuln_low.sum ?? 0}</p>
                                                </div>
                                            </div>
                                        </CardContent>
                                    </Card>
                                </div>

                            </>
                        )}
                    </div>

                    {/* SONARQUBE SECTION */}
                    <div className="space-y-4">
                        <div className="flex items-center gap-2 pb-2 border-b">
                            <BarChart3 className="h-5 w-5 text-purple-500" />
                            <h3 className="text-lg font-semibold tracking-tight">SonarQube Quality Gate</h3>
                        </div>

                        {/* Empty State - Check sonarStats directly, not qualityReport.scan_metrics_summary */}
                        {!sonarStats ? (
                            <div className="flex min-h-[150px] items-center justify-center border rounded-md">
                                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : sonarStats.scan_summary.builds_with_sonar === 0 ? (
                            <Card>
                                <CardContent className="py-8">
                                    <div className="flex flex-col items-center gap-4 text-center">
                                        <p className="text-sm text-muted-foreground">
                                            No SonarQube quality scans were detected for this scenario.
                                        </p>
                                    </div>
                                </CardContent>
                            </Card>
                        ) : (
                            <>
                                {/* SonarQube Overview Cards */}
                                <div className="grid gap-4 md:grid-cols-2">
                                    <Card>
                                        <CardHeader className="pb-3">
                                            <div className="flex items-center justify-between">
                                                <CardTitle className="text-base">Coverage</CardTitle>
                                                <Badge className={getBadgeClass(sonarStats.scan_summary.sonar_coverage_pct)}>
                                                    {sonarStats.scan_summary.sonar_coverage_pct.toFixed(1)}%
                                                </Badge>
                                            </div>
                                        </CardHeader>
                                        <CardContent className="space-y-4">
                                            <Progress value={sonarStats.scan_summary.sonar_coverage_pct} className={`h-2 ${getProgressClass(sonarStats.scan_summary.sonar_coverage_pct)}`} />
                                            <div className="grid grid-cols-2 gap-4 text-sm">
                                                <div>
                                                    <p className="text-muted-foreground">Scanned Builds</p>
                                                    <p className="font-semibold">{sonarStats.scan_summary.builds_with_sonar} / {sonarStats.scan_summary.total_builds}</p>
                                                </div>
                                                <div className="text-right">
                                                    <p className="text-muted-foreground">Total Issues</p>
                                                    <p className="font-semibold">{(sonarStats.sonar_summary?.bugs.sum ?? 0) + (sonarStats.sonar_summary?.code_smells.sum ?? 0) + (sonarStats.sonar_summary?.vulnerabilities.sum ?? 0)}</p>
                                                </div>
                                            </div>
                                        </CardContent>
                                    </Card>

                                    <Card>
                                        <CardHeader className="pb-3">
                                            <CardTitle className="text-base">Quality Metrics</CardTitle>
                                            <CardDescription>
                                                Aggregated from {sonarStats.sonar_summary?.total_scans ?? 0} scans
                                            </CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="grid grid-cols-4 gap-2 text-center">
                                                <div className="p-2 rounded bg-red-50 dark:bg-red-900/10">
                                                    <p className="text-xs font-semibold text-red-600">Bugs</p>
                                                    <p className="font-mono font-bold text-red-700">{sonarStats.sonar_summary?.bugs.sum ?? 0}</p>
                                                </div>
                                                <div className="p-2 rounded bg-amber-50 dark:bg-amber-900/10">
                                                    <p className="text-xs font-semibold text-amber-600">Smells</p>
                                                    <p className="font-mono font-bold text-amber-700">{sonarStats.sonar_summary?.code_smells.sum ?? 0}</p>
                                                </div>
                                                <div className="p-2 rounded bg-purple-50 dark:bg-purple-900/10">
                                                    <p className="text-xs font-semibold text-purple-600">Vulns</p>
                                                    <p className="font-mono font-bold text-purple-700">{sonarStats.sonar_summary?.vulnerabilities.sum ?? 0}</p>
                                                </div>
                                                <div className="p-2 rounded bg-orange-50 dark:bg-orange-900/10">
                                                    <p className="text-xs font-semibold text-orange-600">Hotspots</p>
                                                    <p className="font-mono font-bold text-orange-700">{sonarStats.sonar_summary?.security_hotspots.sum ?? 0}</p>
                                                </div>
                                            </div>
                                            <div className="mt-3 flex justify-between text-xs text-muted-foreground">
                                                <div className="flex gap-1">
                                                    <span>Rel:</span>
                                                    <span className="font-medium text-foreground">{sonarStats.sonar_summary?.reliability_rating_avg?.toFixed(1) ?? "N/A"}</span>
                                                </div>
                                                <div className="flex gap-1">
                                                    <span>Sec:</span>
                                                    <span className="font-medium text-foreground">{sonarStats.sonar_summary?.security_rating_avg?.toFixed(1) ?? "N/A"}</span>
                                                </div>
                                                <div className="flex gap-1">
                                                    <span>Maint:</span>
                                                    <span className="font-medium text-foreground">{sonarStats.sonar_summary?.maintainability_rating_avg?.toFixed(1) ?? "N/A"}</span>
                                                </div>
                                            </div>
                                        </CardContent>
                                    </Card>
                                </div>

                            </>
                        )}
                    </div>



                    {/* COMBINED SCAN METRICS DISTRIBUTIONS */}
                    {qualityReport?.scan_metric_distributions && qualityReport.scan_metric_distributions.length > 0 && (() => {
                        // Filter and paginate scan metrics
                        const filteredScanMetrics = qualityReport.scan_metric_distributions.filter(m =>
                            m.feature_name.toLowerCase().includes(scanDistributionSearch.toLowerCase())
                        );
                        const scanTotalPages = Math.ceil(filteredScanMetrics.length / ITEMS_PER_PAGE);
                        const scanStartIndex = (scanDistributionPage - 1) * ITEMS_PER_PAGE;
                        const paginatedScanMetrics = filteredScanMetrics.slice(scanStartIndex, scanStartIndex + ITEMS_PER_PAGE);

                        return (
                            <Card>
                                <CardHeader className="py-4">
                                    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                                        <div className="flex items-center gap-2">
                                            <BarChart3 className="h-5 w-5 text-indigo-500" />
                                            <div>
                                                <CardTitle className="text-base">Scan Metrics Distributions</CardTitle>
                                                <CardDescription>
                                                    Histogram distributions for Trivy and SonarQube scan metrics across builds
                                                </CardDescription>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <div className="relative">
                                                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                                                <Input
                                                    placeholder="Search metrics..."
                                                    value={scanDistributionSearch}
                                                    onChange={(e) => {
                                                        setScanDistributionSearch(e.target.value);
                                                        setScanDistributionPage(1);
                                                    }}
                                                    className="pl-8 w-[200px]"
                                                />
                                            </div>
                                        </div>
                                    </div>
                                </CardHeader>
                                <CardContent>
                                    {filteredScanMetrics.length === 0 ? (
                                        <div className="text-center py-12 text-muted-foreground">No scan metrics found matching your search.</div>
                                    ) : (
                                        <div className="space-y-4">
                                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                                {paginatedScanMetrics.map((metric) => (
                                                    <FeatureDistributionChart
                                                        key={metric.feature_name}
                                                        featureName={metric.feature_name}
                                                        distribution={{
                                                            feature_name: metric.feature_name,
                                                            data_type: metric.data_type,
                                                            total_count: metric.total_values,
                                                            null_count: metric.null_count,
                                                            bins: metric.distribution_bins?.map(b => ({
                                                                min_value: b.min_value,
                                                                max_value: b.max_value,
                                                                count: b.count,
                                                                percentage: b.percentage,
                                                            })) ?? [],
                                                            stats: {
                                                                min: metric.min_value ?? 0,
                                                                max: metric.max_value ?? 0,
                                                                mean: metric.mean_value ?? 0,
                                                                median: 0,
                                                                std: metric.std_dev ?? 0,
                                                                q1: 0,
                                                                q3: 0,
                                                                iqr: 0,
                                                            },
                                                        }}
                                                    />
                                                ))}
                                            </div>

                                            {scanTotalPages > 1 && (
                                                <div className="flex items-center justify-between pt-4 border-t">
                                                    <div className="text-sm text-muted-foreground">
                                                        Showing {scanStartIndex + 1} to {Math.min(scanStartIndex + ITEMS_PER_PAGE, filteredScanMetrics.length)} of {filteredScanMetrics.length} entries
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <Button
                                                            variant="outline"
                                                            size="sm"
                                                            onClick={() => setScanDistributionPage(p => Math.max(1, p - 1))}
                                                            disabled={scanDistributionPage === 1}
                                                        >
                                                            <ChevronLeft className="h-4 w-4" />
                                                        </Button>
                                                        <span className="text-sm font-medium">Page {scanDistributionPage} of {scanTotalPages}</span>
                                                        <Button
                                                            variant="outline"
                                                            size="sm"
                                                            onClick={() => setScanDistributionPage(p => Math.min(scanTotalPages, p + 1))}
                                                            disabled={scanDistributionPage === scanTotalPages}
                                                        >
                                                            <ChevronRight className="h-4 w-4" />
                                                        </Button>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        );
                    })()}
                </TabsContent>
            </Tabs >
        </div >
    );
}
