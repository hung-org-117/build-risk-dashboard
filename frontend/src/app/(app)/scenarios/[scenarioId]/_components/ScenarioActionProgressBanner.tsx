
import { Loader2, Play, RefreshCw, AlertCircle } from "lucide-react";
import { TrainingScenarioRecord } from "@/lib/api/training-scenarios";

interface ScenarioActionProgressBannerProps {
    scenario: TrainingScenarioRecord;
    processingLoading?: boolean;
    retryIngestionLoading?: boolean;
    retryProcessingLoading?: boolean;
}

export function ScenarioActionProgressBanner({
    scenario,
    processingLoading = false,
    retryIngestionLoading = false,
    retryProcessingLoading = false,
}: ScenarioActionProgressBannerProps) {
    const status = scenario.status.toLowerCase();

    // Determine what action is in progress
    const isIngesting = ["queued", "filtering", "ingesting"].includes(status);
    const isProcessing = status === "processing" || processingLoading;
    const isRetryingIngestion = retryIngestionLoading;
    const isRetryingProcessing = retryProcessingLoading;

    const isAnyActionInProgress = isIngesting || isProcessing || isRetryingIngestion || isRetryingProcessing;

    if (!isAnyActionInProgress && status !== "failed") return null;

    // Calculate progress percentages
    const buildsTotal = scenario.builds_total || 0;
    const buildsIngested = scenario.builds_ingested || 0;

    // Ingestion Progress
    const ingestionPercent = buildsTotal > 0
        ? Math.round((buildsIngested / buildsTotal) * 100)
        : 0;

    // Processing Progress (Feature Extraction)
    // Note: total for extraction is ingestion count (or total if ingestion done)
    const extractionTotal = buildsIngested || buildsTotal;
    const extractionDone = scenario.builds_features_extracted || 0;
    const extractionPercent = extractionTotal > 0
        ? Math.round((extractionDone / extractionTotal) * 100)
        : 0;

    // Scan Progress
    const scansTotal = scenario.scans_total || 0;
    const scansDone = scenario.scans_completed || 0;
    const scansPercent = scansTotal > 0
        ? Math.round((scansDone / scansTotal) * 100)
        : 0;


    // Determine banner content
    let icon = <Loader2 className="h-4 w-4 animate-spin" />;
    let title = "Working...";
    let description = "";
    let progressValue = 0;
    let bgColor = "bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800";
    let showScanProgress = false;

    if (isIngesting || isRetryingIngestion) {
        icon = <RefreshCw className="h-4 w-4 animate-spin text-blue-500" />;
        title = isRetryingIngestion ? "Retrying Ingestion" : "Ingesting Builds";

        if (status === "queued") {
            description = "Waiting in queue...";
        } else if (status === "filtering") {
            description = "Filtering builds from warehouse...";
        } else {
            description = `Ingesting builds: ${buildsIngested}/${buildsTotal}`;
            progressValue = ingestionPercent;
        }
        bgColor = "bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800";
    }
    else if (isProcessing || isRetryingProcessing) {
        icon = <Play className="h-4 w-4 text-green-500" />;
        title = isRetryingProcessing ? "Retrying Processing" : "Processing Scenario";

        const parts: string[] = [];

        // Check if feature extraction is active (builds_features_extracted > 0 or not yet completed)
        const hasFeatureExtraction = extractionTotal > 0 && (!scenario.feature_extraction_completed || extractionDone < extractionTotal);

        // Check if scans are active
        const hasScans = scansTotal > 0;

        if (hasFeatureExtraction) {
            parts.push(`Features: ${extractionDone}/${extractionTotal}`);
        }

        if (hasScans) {
            parts.push(`Scans: ${scansDone}/${scansTotal}`);
            showScanProgress = true;
        }

        // Determine main progress value
        if (hasFeatureExtraction && hasScans) {
            // Both active: show feature progress as main, scans as secondary
            progressValue = extractionPercent;
        } else if (hasFeatureExtraction) {
            // Only features
            progressValue = extractionPercent;
            showScanProgress = false;
        } else if (hasScans) {
            // Only scans: show scan progress as main
            progressValue = scansPercent;
            showScanProgress = false;
        }

        description = parts.length > 0 ? parts.join(" • ") : "Processing...";

        bgColor = "bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800";
    }

    return (
        <div className={`mb-4 rounded-md border p-4 ${bgColor}`}>
            <div className="flex items-start gap-3">
                <div className="mt-0.5">{icon}</div>
                <div className="flex-1 space-y-2">
                    <div className="flex items-center justify-between">
                        <p className="font-medium text-sm">{title}</p>
                        <span className="text-xs text-muted-foreground">{progressValue}%</span>
                    </div>
                    <p className="text-sm text-muted-foreground">{description}</p>

                    {/* Main Progress Bar (Ingestion or Feature Extraction) */}
                    <div className="h-2 w-full overflow-hidden rounded-full bg-secondary/50">
                        <div
                            className="h-full bg-primary transition-all duration-500 ease-in-out"
                            style={{ width: `${progressValue}%` }}
                        />
                    </div>

                    {/* Secondary Progress Bar for Scans (only if active and during processing) */}
                    {showScanProgress && (
                        <div className="mt-1">
                            <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                                <span>Scan Progress</span>
                                <span>{scansPercent}%</span>
                            </div>
                            <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary/50">
                                <div
                                    className="h-full bg-purple-500 transition-all duration-500 ease-in-out"
                                    style={{ width: `${scansPercent}%` }}
                                />
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
