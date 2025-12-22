"use client";

import { useState, useEffect, useCallback } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    Loader2,
    RefreshCw,
    AlertCircle,
    AlertTriangle,
    Info,
    X,
    Download,
} from "lucide-react";
import { qualityApi, type QualityReport, type QualityMetric, type QualityIssue } from "@/lib/api";

interface QualityReportModalProps {
    isOpen: boolean;
    onClose: () => void;
    datasetId: string;
    versionId: string;
}

/**
 * Modal dialog showing detailed quality report.
 * Includes score breakdown, feature metrics table, and issues list.
 */
export function QualityReportModal({
    isOpen,
    onClose,
    datasetId,
    versionId,
}: QualityReportModalProps) {
    const [report, setReport] = useState<QualityReport | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isEvaluating, setIsEvaluating] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleLoadReport = useCallback(async () => {
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

    useEffect(() => {
        if (isOpen && datasetId && versionId) {
            handleLoadReport();
        }
    }, [isOpen, datasetId, versionId, handleLoadReport]);

    const handleEvaluate = async () => {
        setIsEvaluating(true);
        setError(null);
        try {
            const result = await qualityApi.evaluate(datasetId, versionId);
            // Reload report after evaluation
            await handleLoadReport();
        } catch (err: any) {
            const message = err.response?.data?.detail || "Evaluation failed";
            setError(message);
        } finally {
            setIsEvaluating(false);
        }
    };

    const getScoreColor = (score: number): string => {
        if (score >= 80) return "text-green-600";
        if (score >= 60) return "text-yellow-600";
        return "text-red-600";
    };

    const getScoreBadge = (score: number): string => {
        if (score >= 80) return "bg-green-100 text-green-800";
        if (score >= 60) return "bg-yellow-100 text-yellow-800";
        return "bg-red-100 text-red-800";
    };

    const getSeverityIcon = (severity: string) => {
        switch (severity) {
            case "error":
                return <AlertCircle className="h-4 w-4 text-red-500" />;
            case "warning":
                return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
            default:
                return <Info className="h-4 w-4 text-blue-500" />;
        }
    };

    const getSeverityBadge = (severity: string): string => {
        switch (severity) {
            case "error":
                return "bg-red-100 text-red-800";
            case "warning":
                return "bg-yellow-100 text-yellow-800";
            default:
                return "bg-blue-100 text-blue-800";
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={() => onClose()}>
            <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle className="flex items-center justify-between">
                        <span>Data Quality Report</span>
                        {report && (
                            <Badge className={getScoreBadge(report.quality_score)}>
                                Score: {report.quality_score.toFixed(1)}%
                            </Badge>
                        )}
                    </DialogTitle>
                </DialogHeader>

                {isLoading && (
                    <div className="flex items-center justify-center py-12">
                        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                    </div>
                )}

                {error && (
                    <div className="p-4 bg-red-50 text-red-700 rounded-lg flex items-center gap-2">
                        <AlertCircle className="h-5 w-5" />
                        <span>{error}</span>
                    </div>
                )}

                {!isLoading && !report && (
                    <div className="text-center py-12 space-y-4">
                        <p className="text-muted-foreground">
                            No quality report available for this version.
                        </p>
                        <Button onClick={handleEvaluate} disabled={isEvaluating}>
                            {isEvaluating ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    Evaluating...
                                </>
                            ) : (
                                "Run Quality Evaluation"
                            )}
                        </Button>
                    </div>
                )}

                {!isLoading && report && (
                    <Tabs defaultValue="overview" className="space-y-4">
                        <TabsList>
                            <TabsTrigger value="overview">Overview</TabsTrigger>
                            <TabsTrigger value="features">
                                Features ({report.feature_metrics.length})
                            </TabsTrigger>
                            <TabsTrigger value="issues">
                                Issues ({report.issues.length})
                            </TabsTrigger>
                        </TabsList>

                        {/* Overview Tab */}
                        <TabsContent value="overview" className="space-y-6">
                            {/* Score Breakdown */}
                            <div className="grid grid-cols-2 gap-4">
                                <ScoreCard
                                    label="Completeness"
                                    score={report.completeness_score}
                                    description="Non-null feature values"
                                    weight={40}
                                />
                                <ScoreCard
                                    label="Validity"
                                    score={report.validity_score}
                                    description="Values within valid range"
                                    weight={30}
                                />
                                <ScoreCard
                                    label="Consistency"
                                    score={report.consistency_score}
                                    description="Builds with all features"
                                    weight={20}
                                />
                                <ScoreCard
                                    label="Coverage"
                                    score={report.coverage_score}
                                    description="Successfully enriched builds"
                                    weight={10}
                                />
                            </div>

                            {/* Summary Stats */}
                            <div className="grid grid-cols-4 gap-4 text-center">
                                <StatCard
                                    label="Total Builds"
                                    value={report.total_builds}
                                />
                                <StatCard
                                    label="Enriched"
                                    value={report.enriched_builds}
                                    color="green"
                                />
                                <StatCard
                                    label="Partial"
                                    value={report.partial_builds}
                                    color="yellow"
                                />
                                <StatCard
                                    label="Failed"
                                    value={report.failed_builds}
                                    color="red"
                                />
                            </div>

                            {/* Actions */}
                            <div className="flex gap-2 justify-end">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleEvaluate}
                                    disabled={isEvaluating}
                                >
                                    {isEvaluating ? (
                                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                                    ) : (
                                        <RefreshCw className="h-4 w-4 mr-2" />
                                    )}
                                    Re-evaluate
                                </Button>
                            </div>
                        </TabsContent>

                        {/* Features Tab */}
                        <TabsContent value="features">
                            <div className="border rounded-lg overflow-hidden">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Feature</TableHead>
                                            <TableHead>Type</TableHead>
                                            <TableHead className="text-right">Completeness</TableHead>
                                            <TableHead className="text-right">Validity</TableHead>
                                            <TableHead className="text-right">Null Count</TableHead>
                                            <TableHead>Issues</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {report.feature_metrics.map((metric) => (
                                            <FeatureRow key={metric.feature_name} metric={metric} />
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        </TabsContent>

                        {/* Issues Tab */}
                        <TabsContent value="issues">
                            {report.issues.length === 0 ? (
                                <div className="text-center py-8 text-muted-foreground">
                                    No issues detected
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    {report.issues.map((issue, idx) => (
                                        <IssueRow key={idx} issue={issue} />
                                    ))}
                                </div>
                            )}
                        </TabsContent>
                    </Tabs>
                )}
            </DialogContent>
        </Dialog>
    );
}

// Sub-components
interface ScoreCardProps {
    label: string;
    score: number;
    description: string;
    weight: number;
}

function ScoreCard({ label, score, description, weight }: ScoreCardProps) {
    const getColor = (score: number): string => {
        if (score >= 80) return "text-green-600";
        if (score >= 60) return "text-yellow-600";
        return "text-red-600";
    };

    return (
        <div className="p-4 border rounded-lg">
            <div className="flex items-center justify-between mb-2">
                <span className="font-medium">{label}</span>
                <span className="text-xs text-muted-foreground">({weight}%)</span>
            </div>
            <div className={`text-2xl font-bold ${getColor(score)}`}>
                {score.toFixed(1)}%
            </div>
            <Progress value={score} className="h-2 mt-2" />
            <p className="text-xs text-muted-foreground mt-1">{description}</p>
        </div>
    );
}

interface StatCardProps {
    label: string;
    value: number;
    color?: "green" | "yellow" | "red";
}

function StatCard({ label, value, color }: StatCardProps) {
    const colorClass =
        color === "green"
            ? "text-green-600"
            : color === "yellow"
                ? "text-yellow-600"
                : color === "red"
                    ? "text-red-600"
                    : "";

    return (
        <div className="p-3 border rounded-lg">
            <div className={`text-xl font-bold ${colorClass}`}>{value}</div>
            <div className="text-xs text-muted-foreground">{label}</div>
        </div>
    );
}

interface FeatureRowProps {
    metric: QualityMetric;
}

function FeatureRow({ metric }: FeatureRowProps) {
    const hasIssues = metric.issues.length > 0;

    return (
        <TableRow className={hasIssues ? "bg-yellow-50" : ""}>
            <TableCell className="font-mono text-sm">{metric.feature_name}</TableCell>
            <TableCell>
                <Badge variant="outline" className="text-xs">
                    {metric.data_type}
                </Badge>
            </TableCell>
            <TableCell className="text-right">
                <span
                    className={
                        metric.completeness_pct >= 80
                            ? "text-green-600"
                            : metric.completeness_pct >= 50
                                ? "text-yellow-600"
                                : "text-red-600"
                    }
                >
                    {metric.completeness_pct.toFixed(1)}%
                </span>
            </TableCell>
            <TableCell className="text-right">
                <span
                    className={
                        metric.validity_pct >= 90
                            ? "text-green-600"
                            : metric.validity_pct >= 70
                                ? "text-yellow-600"
                                : "text-red-600"
                    }
                >
                    {metric.validity_pct.toFixed(1)}%
                </span>
            </TableCell>
            <TableCell className="text-right">{metric.null_count}</TableCell>
            <TableCell>
                {hasIssues && (
                    <Badge variant="outline" className="bg-yellow-50 text-yellow-700">
                        {metric.issues.length}
                    </Badge>
                )}
            </TableCell>
        </TableRow>
    );
}

interface IssueRowProps {
    issue: QualityIssue;
}

function IssueRow({ issue }: IssueRowProps) {
    const getSeverityIcon = (severity: string) => {
        switch (severity) {
            case "error":
                return <AlertCircle className="h-4 w-4 text-red-500" />;
            case "warning":
                return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
            default:
                return <Info className="h-4 w-4 text-blue-500" />;
        }
    };

    const getBgColor = (severity: string): string => {
        switch (severity) {
            case "error":
                return "bg-red-50 border-red-200";
            case "warning":
                return "bg-yellow-50 border-yellow-200";
            default:
                return "bg-blue-50 border-blue-200";
        }
    };

    return (
        <div className={`p-3 border rounded-lg ${getBgColor(issue.severity)}`}>
            <div className="flex items-start gap-2">
                {getSeverityIcon(issue.severity)}
                <div className="flex-1">
                    <div className="flex items-center gap-2">
                        <Badge
                            variant="outline"
                            className="text-xs capitalize"
                        >
                            {issue.category}
                        </Badge>
                        {issue.feature_name && (
                            <span className="text-xs font-mono text-muted-foreground">
                                {issue.feature_name}
                            </span>
                        )}
                    </div>
                    <p className="text-sm mt-1">{issue.message}</p>
                </div>
            </div>
        </div>
    );
}
