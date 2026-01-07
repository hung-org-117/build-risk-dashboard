"use client";

import { Loader2, Play, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface VersionProcessingCardProps {
    buildsExtracted: number;
    buildsIngested: number;
    buildsExtractionFailed: number;
    status: string;
    canStartProcessing: boolean;
    onStartProcessing?: () => void;
    onRetryFailed?: () => void;
    startLoading?: boolean;
    retryLoading?: boolean;
    // Scan tracking
    scansCompleted?: number;
    scansTotal?: number;
    scansFailed?: number;
}

export function VersionProcessingCard({
    buildsExtracted,
    buildsIngested,
    buildsExtractionFailed,
    status,
    canStartProcessing,
    onStartProcessing,
    onRetryFailed,
    startLoading = false,
    retryLoading = false,
    scansCompleted = 0,
    scansTotal = 0,
    scansFailed = 0,
}: VersionProcessingCardProps) {
    const s = status.toLowerCase();
    const isProcessing = s === "processing";
    const isComplete = s === "processed";
    const notStarted = s === "ingested";

    const total = buildsIngested;
    const processed = buildsExtracted + buildsExtractionFailed;
    const percent = total > 0 ? Math.round((processed / total) * 100) : 0;

    // Scan progress
    const scansDone = scansCompleted + scansFailed;
    const scanPercent = scansTotal > 0 ? Math.round((scansDone / scansTotal) * 100) : 0;
    const hasScans = scansTotal > 0;

    return (
        <Card>
            <CardHeader className="pb-4">
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="text-lg flex items-center gap-2">
                            Feature Extraction
                            {isProcessing && (
                                <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                            )}
                        </CardTitle>
                        <CardDescription>
                            Extract features from ingested builds
                        </CardDescription>
                    </div>
                    {canStartProcessing && notStarted && onStartProcessing && (
                        <Button
                            onClick={onStartProcessing}
                            disabled={startLoading}
                            className="gap-2"
                        >
                            {startLoading ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <Play className="h-4 w-4" />
                            )}
                            Start Processing
                        </Button>
                    )}
                </div>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Feature Extraction Progress */}
                <div className="p-4 rounded-lg border bg-slate-50 dark:bg-slate-900/50">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">
                            Extraction Progress
                        </span>
                        <span className={cn(
                            "text-sm",
                            isComplete ? "text-green-600" : "text-muted-foreground"
                        )}>
                            {buildsExtracted}/{total}
                        </span>
                    </div>
                    <Progress value={percent} className="h-2" />
                    <div className="flex justify-between mt-2">
                        <p className="text-xs text-muted-foreground">
                            {notStarted && "Not started"}
                            {isProcessing && "In progress..."}
                            {isComplete && "Complete"}
                        </p>
                        {buildsExtractionFailed > 0 && (
                            <p className="text-xs text-red-600">
                                {buildsExtractionFailed} failed
                            </p>
                        )}
                    </div>
                </div>

                {/* Scan Metrics Progress (only show if scans configured) */}
                {hasScans && (
                    <div className="p-4 rounded-lg border bg-slate-50 dark:bg-slate-900/50">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-medium flex items-center gap-2">
                                🔍 Scan Metrics
                                {isProcessing && scanPercent < 100 && (
                                    <Loader2 className="h-3 w-3 animate-spin text-blue-500" />
                                )}
                            </span>
                            <span className={cn(
                                "text-sm",
                                scanPercent === 100 ? "text-green-600" : "text-muted-foreground"
                            )}>
                                {scansCompleted}/{scansTotal}
                            </span>
                        </div>
                        <Progress value={scanPercent} className="h-2" />
                        <div className="flex justify-between mt-2">
                            <p className="text-xs text-muted-foreground">
                                Trivy + SonarQube
                            </p>
                            {scansFailed > 0 && (
                                <p className="text-xs text-red-600">
                                    {scansFailed} failed
                                </p>
                            )}
                        </div>
                    </div>
                )}

                {/* Retry Action */}
                {onRetryFailed && buildsExtractionFailed > 0 && (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onRetryFailed}
                        disabled={retryLoading || isProcessing}
                    >
                        {retryLoading ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                            <RotateCcw className="mr-2 h-4 w-4" />
                        )}
                        Retry Failed ({buildsExtractionFailed})
                    </Button>
                )}
            </CardContent>
        </Card>
    );
}
