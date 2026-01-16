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
    const isIngesting = status === "ingesting" || syncLoading || retryIngestionLoading;
    const isProcessing = status === "processing" || processingLoading || retryProcessingLoading;
    const isFailed = status === "failed";
    const isProcessed = status === "processed";
    const isIngested = status === "ingested";

    const isActive = isFetching || isIngesting || isProcessing || isIngested || isProcessed || isFailed;

    if (!isActive && status !== "queued") return null;


    // --- METRICS CALCULATION ---

    // 1. Fetching (Phase 1)
    // "import_builds.total" roughly equals fetched builds count
    const fetchedCount = progress?.import_builds.total || 0;

    // 2. Ingestion (Phase 2)
    const ingestionTotal = progress?.import_builds.total || 0;
    const ingestionDone = progress?.import_builds.ingested || 0;
    const ingestionPercent = ingestionTotal > 0
        ? Math.round((ingestionDone / ingestionTotal) * 100)
        : 0;
    const isIngestionCompleted = (status === "ingested" || status === "processing" || status === "processed") && ingestionPercent >= 100;

    // 3. Processing (Phase 3)
    const processingTotal = progress?.training_builds.total || 0; // Should match ingested
    const processingDone = (progress?.training_builds.completed || 0) + (progress?.training_builds.partial || 0);
    const processingPercent = processingTotal > 0
        ? Math.round((processingDone / processingTotal) * 100)
        : 0;
    const isProcessingCompleted = status === "processed" || (status === "processing" && processingPercent >= 100);

    // Current active phase for highlighting
    // Fetching -> Ingestion -> Processing
    let activePhase = "idle";
    if (isFetching) activePhase = "fetching";
    else if (isIngesting) activePhase = "ingestion";
    else if (isProcessing) activePhase = "processing";


    // Overall Banner State
    let bannerTitle = "Pipeline Status";
    let bannerColor = "bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800";
    let MainIcon = Loader2;
    let iconColor = "text-blue-500";
    let isSpinning = true;

    if (isFailed) {
        bannerTitle = "Pipeline Failed";
        bannerColor = "bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800";
        MainIcon = RotateCcw; // Or AlertCircle
        iconColor = "text-red-500";
        isSpinning = false;
    } else if (isProcessed) {
        bannerTitle = "Pipeline Completed";
        bannerColor = "bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800";
        MainIcon = CheckCircle2;
        iconColor = "text-green-500";
        isSpinning = false;
    } else if (isProcessing) {
        bannerTitle = "Processing Builds";
        bannerColor = "bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800";
        MainIcon = Play;
        iconColor = "text-green-500";
        isSpinning = false; // The individual items will spin/animate
    } else if (isIngesting || isFetching) {
        bannerTitle = isFetching ? "Fetching Builds" : "Ingesting Builds";
        bannerColor = "bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800";
        MainIcon = RefreshCw;
        iconColor = "text-blue-500";
        isSpinning = true;
    }

    // Reuse Retry Loading override
    if (retryIngestionLoading) {
        bannerTitle = "Retrying Ingestion";
        isSpinning = true;
    } else if (retryProcessingLoading) {
        bannerTitle = "Retrying Processing";
        isSpinning = true;
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

                    {/* --- PHASE 1: FETCHING --- */}
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <span className="text-sm font-medium">1. Fetch Builds</span>
                                {fetchedCount > 0 && !isFetching ? (
                                    <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                                ) : isFetching ? (
                                    <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />
                                ) : null}
                            </div>
                            <span className="text-xs text-muted-foreground">
                                {fetchedCount} found
                            </span>
                        </div>
                        {/* No progress bar for fetching (usually) or could use indeterminate */}
                    </div>

                    {/* --- PHASE 2: INGESTION --- */}
                    {(ingestionTotal > 0 || isIngesting || status === "ingested") && (
                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium">2. Ingestion</span>
                                    {isIngestionCompleted ? (
                                        <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                                    ) : isIngesting ? (
                                        <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />
                                    ) : null}
                                </div>
                                <span className="text-xs text-muted-foreground">
                                    {ingestionDone}/{ingestionTotal} builds
                                </span>
                            </div>
                            <div className="h-2 w-full overflow-hidden rounded-full bg-secondary/50">
                                <div
                                    className={cn(
                                        "h-full transition-all duration-500 ease-in-out",
                                        isIngestionCompleted ? "bg-green-500" : "bg-blue-500"
                                    )}
                                    style={{ width: `${ingestionPercent}%` }}
                                />
                            </div>
                        </div>
                    )}

                    {/* --- PHASE 3: PROCESSING --- */}
                    {(isProcessing || isProcessed || processingTotal > 0) && (
                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium">3. Processing</span>
                                    {isProcessingCompleted ? (
                                        <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                                    ) : isProcessing ? (
                                        <Play className="h-3.5 w-3.5 text-green-500" />
                                    ) : null}
                                </div>
                                <span className="text-xs text-muted-foreground">
                                    {processingDone}/{processingTotal} builds
                                </span>
                            </div>
                            <div className="h-2 w-full overflow-hidden rounded-full bg-secondary/50">
                                <div
                                    className={cn(
                                        "h-full transition-all duration-500 ease-in-out",
                                        isProcessingCompleted ? "bg-green-500" : "bg-emerald-500"
                                    )}
                                    style={{ width: `${processingPercent}%` }}
                                />
                            </div>
                            {/* Real-time sub-status text */}
                            {isProcessing && !isProcessingCompleted && (
                                <p className="text-xs text-muted-foreground italic">
                                    {currentPhase === "prediction"
                                        ? "Running risk predictions..."
                                        : currentPhase === "extraction"
                                            ? `Extracting features...`
                                            : "Processing pipeline running..."}
                                    {currentBuildProgress?.buildNumber && ` (Build #${currentBuildProgress.buildNumber})`}
                                </p>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
