"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Loader2, RefreshCw, AlertCircle, CheckCircle, TrendingUp } from "lucide-react";
import { qualityApi, type QualityReport } from "@/lib/api";

interface QualityReportCardProps {
    datasetId: string;
    versionId: string;
    versionStatus: string;
    onViewDetails?: () => void;
}

/**
 * Card component displaying quality score summary.
 * Shows overall score and breakdown of 4 sub-scores.
 */
export function QualityReportCard({
    datasetId,
    versionId,
    versionStatus,
    onViewDetails,
}: QualityReportCardProps) {
    const [report, setReport] = useState<QualityReport | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isEvaluating, setIsEvaluating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [hasLoaded, setHasLoaded] = useState(false);

    const handleLoadReport = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const result = await qualityApi.getReport(datasetId, versionId);
            if ("available" in result && !result.available) {
                setReport(null);
            } else {
                setReport(result as QualityReport);
            }
            setHasLoaded(true);
        } catch (err) {
            setError("Failed to load quality report");
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    };

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

    const isVersionReady = versionStatus === "completed";

    // Initial load button
    if (!hasLoaded) {
        return (
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                        <TrendingUp className="h-4 w-4" />
                        Data Quality
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleLoadReport}
                        disabled={isLoading || !isVersionReady}
                        className="w-full"
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                Loading...
                            </>
                        ) : (
                            "Load Quality Report"
                        )}
                    </Button>
                    {!isVersionReady && (
                        <p className="text-xs text-muted-foreground mt-2 text-center">
                            Available after enrichment completes
                        </p>
                    )}
                </CardContent>
            </Card>
        );
    }

    // No report available
    if (!report) {
        return (
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                        <TrendingUp className="h-4 w-4" />
                        Data Quality
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    <p className="text-sm text-muted-foreground">
                        No quality report available.
                    </p>
                    <Button
                        variant="default"
                        size="sm"
                        onClick={handleEvaluate}
                        disabled={isEvaluating || !isVersionReady}
                        className="w-full"
                    >
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
                        <p className="text-xs text-red-500 flex items-center gap-1">
                            <AlertCircle className="h-3 w-3" />
                            {error}
                        </p>
                    )}
                </CardContent>
            </Card>
        );
    }

    // Report available
    const issueCount =
        (report.issue_counts?.error || 0) +
        (report.issue_counts?.warning || 0);

    return (
        <Card>
            <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                        <TrendingUp className="h-4 w-4" />
                        Data Quality
                    </CardTitle>
                    <Badge className={getScoreBadge(report.quality_score)}>
                        {report.quality_score.toFixed(1)}%
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="space-y-3">
                {/* Score Breakdown */}
                <div className="space-y-2">
                    <ScoreBar
                        label="Completeness"
                        score={report.completeness_score}
                        weight={40}
                    />
                    <ScoreBar
                        label="Validity"
                        score={report.validity_score}
                        weight={30}
                    />
                    <ScoreBar
                        label="Consistency"
                        score={report.consistency_score}
                        weight={20}
                    />
                    <ScoreBar
                        label="Coverage"
                        score={report.coverage_score}
                        weight={10}
                    />
                </div>

                {/* Issues Summary */}
                {issueCount > 0 && (
                    <div className="flex items-center gap-2 text-sm">
                        <AlertCircle className="h-4 w-4 text-yellow-500" />
                        <span className="text-muted-foreground">
                            {issueCount} issue{issueCount > 1 ? "s" : ""} detected
                        </span>
                    </div>
                )}

                {/* Actions */}
                <div className="flex gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleEvaluate}
                        disabled={isEvaluating}
                        className="flex-1"
                    >
                        {isEvaluating ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <RefreshCw className="h-4 w-4 mr-1" />
                        )}
                        Re-evaluate
                    </Button>
                    {onViewDetails && (
                        <Button
                            variant="default"
                            size="sm"
                            onClick={onViewDetails}
                            className="flex-1"
                        >
                            View Details
                        </Button>
                    )}
                </div>

                {error && (
                    <p className="text-xs text-red-500 flex items-center gap-1">
                        <AlertCircle className="h-3 w-3" />
                        {error}
                    </p>
                )}
            </CardContent>
        </Card>
    );
}

interface ScoreBarProps {
    label: string;
    score: number;
    weight: number;
}

function ScoreBar({ label, score, weight }: ScoreBarProps) {
    const getColor = (score: number): string => {
        if (score >= 80) return "bg-green-500";
        if (score >= 60) return "bg-yellow-500";
        return "bg-red-500";
    };

    return (
        <div className="flex items-center gap-2 text-xs">
            <span className="w-24 text-muted-foreground">
                {label} ({weight}%)
            </span>
            <div className="flex-1">
                <Progress value={score} className="h-2" />
            </div>
            <span className="w-10 text-right font-medium">{score.toFixed(0)}%</span>
        </div>
    );
}
