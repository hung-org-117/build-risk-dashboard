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
    buildsProcessed: number;
    buildsIngested: number;
    buildsProcessingFailed: number;
    status: string;
    canStartProcessing: boolean;
    onStartProcessing?: () => void;
    onRetryFailed?: () => void;
    startLoading?: boolean;
    retryLoading?: boolean;
}

export function VersionProcessingCard({
    buildsProcessed,
    buildsIngested,
    buildsProcessingFailed,
    status,
    canStartProcessing,
    onStartProcessing,
    onRetryFailed,
    startLoading = false,
    retryLoading = false,
}: VersionProcessingCardProps) {
    const s = status.toLowerCase();
    const isProcessing = s === "processing";
    const isComplete = s === "processed";
    const notStarted = s === "ingested";

    const total = buildsIngested;
    const processed = buildsProcessed + buildsProcessingFailed;
    const percent = total > 0 ? Math.round((processed / total) * 100) : 0;

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
                {/* Progress */}
                <div className="p-4 rounded-lg border bg-slate-50 dark:bg-slate-900/50">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">
                            Extraction Progress
                        </span>
                        <span className={cn(
                            "text-sm",
                            isComplete ? "text-green-600" : "text-muted-foreground"
                        )}>
                            {buildsProcessed}/{total}
                        </span>
                    </div>
                    <Progress value={percent} className="h-2" />
                    <div className="flex justify-between mt-2">
                        <p className="text-xs text-muted-foreground">
                            {notStarted && "Not started"}
                            {isProcessing && "In progress..."}
                            {isComplete && "Complete"}
                        </p>
                        {buildsProcessingFailed > 0 && (
                            <p className="text-xs text-red-600">
                                {buildsProcessingFailed} failed
                            </p>
                        )}
                    </div>
                </div>

                {/* Retry Action */}
                {onRetryFailed && buildsProcessingFailed > 0 && (
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
                        Retry Failed ({buildsProcessingFailed})
                    </Button>
                )}
            </CardContent>
        </Card>
    );
}
