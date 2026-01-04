"use client";

import { Loader2, RefreshCw, Play, RotateCcw, CheckCircle2 } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface ActionProgressBannerProps {
    repoStatus: string;
    progress: {
        import_builds: {
            ingested: number;
            total: number;
            missing_resource?: number;
        };
        training_builds: {
            completed: number;
            partial: number;
            total: number;
            with_prediction?: number;
        };
    } | null;
    syncLoading?: boolean;
    processingLoading?: boolean;
    retryIngestionLoading?: boolean;
    retryProcessingLoading?: boolean;
}

export function ActionProgressBanner({
    repoStatus,
    progress,
    syncLoading = false,
    processingLoading = false,
    retryIngestionLoading = false,
    retryProcessingLoading = false,
}: ActionProgressBannerProps) {
    const status = repoStatus.toLowerCase();

    // Determine what action is in progress
    const isSyncing = ["queued", "fetching", "ingesting"].includes(status) || syncLoading;
    const isProcessing = status === "processing" || processingLoading;
    const isRetryingIngestion = retryIngestionLoading;
    const isRetryingProcessing = retryProcessingLoading;

    const isAnyActionInProgress = isSyncing || isProcessing || isRetryingIngestion || isRetryingProcessing;

    if (!isAnyActionInProgress) return null;

    // Calculate progress percentages
    const ingestionPercent = progress?.import_builds.total
        ? Math.round((progress.import_builds.ingested / progress.import_builds.total) * 100)
        : 0;

    const extractionTotal = progress?.training_builds.total || 0;
    const extractionDone = (progress?.training_builds.completed || 0) + (progress?.training_builds.partial || 0);
    const extractionPercent = extractionTotal > 0 ? Math.round((extractionDone / extractionTotal) * 100) : 0;

    // Determine banner content
    let icon = <Loader2 className="h-4 w-4 animate-spin" />;
    let title = "Working...";
    let description = "";
    let progressValue = 0;
    let bgColor = "bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800";

    if (isSyncing) {
        icon = <RefreshCw className="h-4 w-4 animate-spin text-blue-500" />;
        title = "Syncing Builds";
        // Show different messages based on actual status
        if (status === "fetching") {
            description = "Fetching new builds from CI...";
        } else if (status === "ingesting") {
            description = `Ingesting builds: ${progress?.import_builds.ingested || 0}/${progress?.import_builds.total || 0}`;
            progressValue = ingestionPercent;
        } else {
            description = "Checking for new builds...";
        }
        bgColor = "bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800";
    } else if (isProcessing) {
        icon = <Play className="h-4 w-4 text-green-500" />;
        title = "Processing Builds";
        description = `Extracting features: ${extractionDone}/${extractionTotal}`;
        progressValue = extractionPercent;
        bgColor = "bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800";
    } else if (isRetryingIngestion) {
        icon = <RotateCcw className="h-4 w-4 animate-spin text-amber-500" />;
        title = "Retrying Failed Ingestion";
        description = "Re-running failed ingestion tasks...";
        progressValue = 0;
        bgColor = "bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800";
    } else if (isRetryingProcessing) {
        icon = <RotateCcw className="h-4 w-4 animate-spin text-amber-500" />;
        title = "Retrying Failed Processing";
        description = "Re-running failed extraction/prediction tasks...";
        progressValue = 0;
        bgColor = "bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800";
    }

    return (
        <div className={cn("rounded-lg border p-4 mb-4", bgColor)}>
            <div className="flex items-center gap-3 mb-2">
                {icon}
                <div className="flex-1">
                    <div className="flex items-center justify-between">
                        <span className="font-medium text-sm">{title}</span>
                        {progressValue > 0 && (
                            <span className="text-xs text-muted-foreground">{progressValue}%</span>
                        )}
                    </div>
                    <p className="text-xs text-muted-foreground">{description}</p>
                </div>
            </div>
            {progressValue > 0 && (
                <Progress value={progressValue} className="h-1.5" />
            )}
        </div>
    );
}
