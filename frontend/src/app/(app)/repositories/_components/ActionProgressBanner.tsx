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
            pending: number;
            total: number;
            with_prediction?: number;
            pending_prediction?: number;
        };

    } | null;
    syncLoading?: boolean;
    processingLoading?: boolean;
    retryIngestionLoading?: boolean;
    retryProcessingLoading?: boolean;
    // Real-time progress from SSE
    currentPhase?: "ingestion" | "extraction" | "prediction";
    currentBuildProgress?: {
        buildNumber?: number;
        featureCount?: number;
        expectedFeatureCount?: number;
        extractionStatus?: string;
        predictionStatus?: string;
    };
}

export function ActionProgressBanner({
    repoStatus,
    progress,
    syncLoading = false,
    processingLoading = false,
    retryIngestionLoading = false,
    retryProcessingLoading = false,
    currentPhase,
    currentBuildProgress,
}: ActionProgressBannerProps) {
    const status = repoStatus.toLowerCase();

    // Determine what action is in progress
    const isFetching = status === "fetching" || status === "queued";
    const isFetched = status === "fetched";
    const isIngesting = status === "ingesting" || syncLoading || retryIngestionLoading;
    const isProcessing = status === "processing" || processingLoading || retryProcessingLoading;
    const isFailed = status === "failed";

    // Show banner ONLY if active or failed. 
    // "ingested" and "processed" are considered idle/done and hidden.
    const isActive = isFetching || isFetched || isIngesting || isProcessing || isFailed;

    if (!isActive) return null;

    // --- METRICS CALCULATION ---
    const fetchedCount = progress?.import_builds.total || 0;

    const ingestionTotal = progress?.import_builds.total || 0;
    const ingestionDone = progress?.import_builds.ingested || 0;
    const ingestionPercent = ingestionTotal > 0
        ? Math.round((ingestionDone / ingestionTotal) * 100)
        : 0;

    const processingTotal = progress?.training_builds.total || 0;
    const processingDone = (progress?.training_builds.completed || 0) + (progress?.training_builds.partial || 0);
    const processingPercent = processingTotal > 0
        ? Math.round((processingDone / processingTotal) * 100)
        : 0;


    // --- DISPLAY CONFIGURATION ---
    let bannerTitle = "Pipeline Status";
    let bannerColor = "bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800";
    let MainIcon = Loader2;
    let iconColor = "text-blue-500";
    let isSpinning = true;
    let Content = null;

    if (isFailed) {
        bannerTitle = "Pipeline Failed";
        bannerColor = "bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800";
        MainIcon = RotateCcw;
        iconColor = "text-red-500";
        isSpinning = false;

        Content = (
            <div className="text-sm text-muted-foreground">
                <p>The pipeline encountered an error. Please check the logs or try retrying the failed step.</p>
            </div>
        );

    } else if (isProcessing) {
        bannerTitle = retryProcessingLoading ? "Retrying Processing" : "Processing Builds";
        bannerColor = "bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800";
        MainIcon = Play;
        iconColor = "text-green-500";
        isSpinning = false;

        Content = (
            <div className="space-y-2">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">Progress</span>
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-green-500" />
                    </div>
                    <span className="text-xs text-muted-foreground">
                        {processingDone}/{processingTotal} builds
                    </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-secondary/50">
                    <div
                        className="h-full bg-emerald-500 transition-all duration-500 ease-in-out"
                        style={{ width: `${processingPercent}%` }}
                    />
                </div>
                {/* Real-time sub-status text */}
                <p className="text-xs text-muted-foreground italic">
                    {currentPhase === "prediction"
                        ? "Running risk predictions..."
                        : currentPhase === "extraction"
                            ? `Extracting features...`
                            : "Processing pipeline running..."}
                    {currentBuildProgress?.buildNumber && ` (Build #${currentBuildProgress.buildNumber})`}
                </p>
            </div>
        );

    } else if (isIngesting) {
        bannerTitle = retryIngestionLoading ? "Retrying Ingestion" : "Ingesting Builds";
        bannerColor = "bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800";
        MainIcon = RefreshCw;
        iconColor = "text-blue-500";
        isSpinning = true;

        Content = (
            <div className="space-y-2">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">Progress</span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                        {ingestionDone}/{ingestionTotal} builds
                    </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-secondary/50">
                    <div
                        className="h-full bg-blue-500 transition-all duration-500 ease-in-out"
                        style={{ width: `${ingestionPercent}%` }}
                    />
                </div>
            </div>
        );

    } else if (isFetched) {
        bannerTitle = "Fetch Complete";
        bannerColor = "bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800";
        MainIcon = CheckCircle2;
        iconColor = "text-green-500";
        isSpinning = false;

        Content = (
            <div className="space-y-2">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">Fetched</span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                        {fetchedCount} builds ready for ingestion
                    </span>
                </div>
                <p className="text-xs text-muted-foreground italic">
                    Starting ingestion phase...
                </p>
            </div>
        );

    } else if (isFetching) {
        bannerTitle = "Fetching Builds";
        bannerColor = "bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800";
        MainIcon = Loader2;
        iconColor = "text-blue-500";
        isSpinning = true;

        Content = (
            <div className="space-y-2">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">Found</span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                        {fetchedCount} builds
                    </span>
                </div>
            </div>
        );
    }

    return (
        <div className={cn("rounded-lg border p-4 mb-4", bannerColor)}>
            <div className="flex items-start gap-3">
                <div className="mt-0.5">
                    <MainIcon className={cn("h-5 w-5", iconColor, isSpinning && "animate-spin")} />
                </div>
                <div className="flex-1 space-y-4">
                    <div className="flex items-center justify-between">
                        <p className="font-medium text-sm">{bannerTitle}</p>
                        {status && (
                            <span className="text-xs uppercase px-2 py-0.5 rounded-full bg-background/50 border font-mono">
                                {status}
                            </span>
                        )}
                    </div>
                    {Content}
                </div>
            </div>
        </div>
    );
}
