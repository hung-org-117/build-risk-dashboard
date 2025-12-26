"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
    Loader2,
    RefreshCw,
    AlertCircle,
    CheckCircle,
    TrendingUp,
    AlertTriangle,
    Info
} from "lucide-react";
import { qualityApi, type QualityReport, type QualityMetric, type QualityIssue } from "@/lib/api";

interface QualityReportSectionProps {
    datasetId: string;
    versionId: string;
    versionStatus: string;

}

function getScoreColor(score: number): string {
    if (score >= 80) return "text-green-600";
    if (score >= 60) return "text-yellow-600";
    return "text-red-600";
}

function getScoreBadge(score: number): string {
    if (score >= 80) return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
    if (score >= 60) return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400";
    return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";
}

function getProgressColor(score: number): string {
    if (score >= 80) return "bg-green-500";
    if (score >= 60) return "bg-yellow-500";
    return "bg-red-500";
}

export function QualityReportSection({
    datasetId,
    versionId,
    versionStatus,

}: QualityReportSectionProps) {
    const [report, setReport] = useState<QualityReport | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isEvaluating, setIsEvaluating] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchReport = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const result = await qualityApi.getReport(datasetId, versionId);
            if ("available" in result && !result.available) {
                setReport(null);
            } else {
                setReport(result as QualityReport);
            }
        } catch (err) {
            setError("Failed to load quality report");
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    }, [datasetId, versionId]);

    const handleEvaluate = async () => {
        setIsEvaluating(true);
        setError(null);
        try {
            await qualityApi.evaluate(datasetId, versionId);
            await fetchReport();
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Evaluation failed";
            setError(message);
        } finally {
            setIsEvaluating(false);
        }
    };

    useEffect(() => {
        if (versionStatus === "completed") {
            fetchReport();
        }
    }, [versionStatus, fetchReport]);

    const isVersionReady = versionStatus === "completed";

    // Loading state
    if (isLoading) {
        return (
            <Card>
                <CardContent className="flex items-center justify-center py-12">
                    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </CardContent>
            </Card>
        );
    }

    // Version not ready
    if (!isVersionReady) {
        return (
            <Card>
                <CardContent className="py-12 text-center">
                    <AlertCircle className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                    <p className="text-lg font-medium">Quality Report Not Available</p>
                    <p className="text-sm text-muted-foreground mt-2">
                        Quality evaluation is available after enrichment completes
                    </p>
                </CardContent>
            </Card>
        );
    }

    // No report - show evaluate button
    if (!report) {
        return (
            <Card>
                <CardContent className="py-12 text-center space-y-4">
                    <TrendingUp className="h-12 w-12 mx-auto text-muted-foreground" />
                    <div>
                        <p className="text-lg font-medium">No Quality Report</p>
                        <p className="text-sm text-muted-foreground mt-1">
                            Run quality evaluation to assess data quality
                        </p>
                    </div>
                    <Button onClick={handleEvaluate} disabled={isEvaluating}>
                        {isEvaluating ? (
                            <>
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                Evaluating...
                            </>
                        ) : (
                            <>Run Quality Evaluation</>
                        )}
                    </Button>
                    {error && (
                        <p className="text-sm text-red-500 flex items-center justify-center gap-1">
                            <AlertCircle className="h-4 w-4" />
                            {error}
                        </p>
                    )}
                </CardContent>
            </Card>
        );
    }

    // Report available - show full details
    const issueCount = (report.issue_counts?.error || 0) + (report.issue_counts?.warning || 0);

    return (
        <div className="space-y-6">
            {/* Overall Score Card */}
            <Card>
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="flex items-center gap-2">
                                <TrendingUp className="h-5 w-5" />
                                Data Quality Report
                            </CardTitle>
                            <CardDescription>
                                Evaluated at {report.created_at ? new Date(report.created_at).toLocaleString() : "N/A"}
                            </CardDescription>
                        </div>
                        <div className="flex items-center gap-3">
                            <Badge className={`text-lg px-3 py-1 ${getScoreBadge(report.quality_score)}`}>
                                {report.quality_score.toFixed(1)}%
                            </Badge>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handleEvaluate}
                                disabled={isEvaluating}
                            >
                                {isEvaluating ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <RefreshCw className="h-4 w-4" />
                                )}
                                <span className="ml-2">Re-evaluate</span>
                            </Button>
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    {/* Score Breakdown */}
                    <div className="grid grid-cols-4 gap-6">
                        <ScoreCard
                            label="Completeness"
                            score={report.completeness_score}
                            weight={40}
                            description="Measures missing values and null rates"
                        />
                        <ScoreCard
                            label="Validity"
                            score={report.validity_score}
                            weight={30}
                            description="Checks data types and format conformance"
                        />
                        <ScoreCard
                            label="Consistency"
                            score={report.consistency_score}
                            weight={20}
                            description="Detects outliers and anomalies"
                        />
                        <ScoreCard
                            label="Coverage"
                            score={report.coverage_score}
                            weight={10}
                            description="Feature extraction success rate"
                        />
                    </div>
                </CardContent>
            </Card>

            {/* Metrics & Issues Grid */}
            <div className="grid grid-cols-2 gap-6">
                {/* Feature Metrics */}
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base">Feature Metrics</CardTitle>
                        <CardDescription>Quality metrics per feature</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="max-h-64 overflow-y-auto space-y-2">
                            {report.feature_metrics && report.feature_metrics.length > 0 ? (
                                report.feature_metrics.map((metric, idx) => (
                                    <MetricRow key={idx} metric={metric} />
                                ))
                            ) : (
                                <p className="text-sm text-muted-foreground text-center py-4">
                                    No feature metrics available
                                </p>
                            )}
                        </div>
                    </CardContent>
                </Card>

                {/* Issues */}
                <Card>
                    <CardHeader className="pb-2">
                        <div className="flex items-center justify-between">
                            <div>
                                <CardTitle className="text-base">Issues Detected</CardTitle>
                                <CardDescription>Problems found in data</CardDescription>
                            </div>
                            {issueCount > 0 && (
                                <Badge variant="destructive">{issueCount}</Badge>
                            )}
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="max-h-64 overflow-y-auto space-y-2">
                            {report.issues && report.issues.length > 0 ? (
                                report.issues.map((issue, idx) => (
                                    <IssueRow key={idx} issue={issue} />
                                ))
                            ) : (
                                <div className="text-center py-4">
                                    <CheckCircle className="h-8 w-8 mx-auto text-green-500 mb-2" />
                                    <p className="text-sm text-muted-foreground">
                                        No issues detected
                                    </p>
                                </div>
                            )}
                        </div>
                    </CardContent>
                </Card>
            </div>

            {error && (
                <Card className="border-red-200 dark:border-red-900">
                    <CardContent className="py-3">
                        <p className="text-sm text-red-500 flex items-center gap-2">
                            <AlertCircle className="h-4 w-4" />
                            {error}
                        </p>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}

interface ScoreCardProps {
    label: string;
    score: number;
    weight: number;
    description: string;
}

function ScoreCard({ label, score, weight, description }: ScoreCardProps) {
    return (
        <div className="text-center p-4 rounded-lg bg-muted/30">
            <p className="text-sm text-muted-foreground mb-1">{label} ({weight}%)</p>
            <p className={`text-3xl font-bold ${getScoreColor(score)}`}>
                {score.toFixed(0)}%
            </p>
            <Progress
                value={score}
                className="h-2 mt-2"
            />
            <p className="text-xs text-muted-foreground mt-2">{description}</p>
        </div>
    );
}

function MetricRow({ metric }: { metric: QualityMetric }) {
    return (
        <div className="flex items-center justify-between py-1.5 border-b last:border-0">
            <span className="text-sm font-mono truncate max-w-[60%]">{metric.feature_name}</span>
            <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">
                    {metric.completeness_pct.toFixed(0)}% complete
                </span>
                <Badge
                    variant="outline"
                    className={`text-xs ${getScoreBadge(metric.completeness_pct)}`}
                >
                    {metric.null_count} nulls
                </Badge>
            </div>
        </div>
    );
}

function IssueRow({ issue }: { issue: QualityIssue }) {
    const Icon = issue.severity === "error" ? AlertCircle :
        issue.severity === "warning" ? AlertTriangle : Info;
    const colorClass = issue.severity === "error" ? "text-red-500" :
        issue.severity === "warning" ? "text-yellow-500" : "text-blue-500";

    return (
        <div className="flex items-start gap-2 py-1.5 border-b last:border-0">
            <Icon className={`h-4 w-4 mt-0.5 shrink-0 ${colorClass}`} />
            <div className="flex-1 min-w-0">
                <p className="text-sm">{issue.message}</p>
                {issue.feature_name && (
                    <p className="text-xs text-muted-foreground font-mono">
                        {issue.feature_name}
                    </p>
                )}
            </div>
        </div>
    );
}
