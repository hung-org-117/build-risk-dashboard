
import { Loader2, Play, RefreshCw, CheckCircle2 } from "lucide-react";
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
    const isIngesting = ["queued", "ingesting"].includes(status);
    const isProcessing = status === "processing" || processingLoading;
    const isRetryingIngestion = retryIngestionLoading;
    const isRetryingProcessing = retryProcessingLoading;

    // Calculate progress percentages
    const buildsTotal = scenario.builds_total || 0;
    const buildsIngested = scenario.builds_ingested || 0;

    // Ingestion Progress
    const ingestionPercent = buildsTotal > 0
        ? Math.round((buildsIngested / buildsTotal) * 100)
        : 0;

    // Processing Progress (Feature Extraction)
    const extractionTotal = buildsIngested || buildsTotal;
    const extractionDone = scenario.builds_features_extracted || 0;
    const extractionPercent = extractionTotal > 0
        ? Math.round((extractionDone / extractionTotal) * 100)
        : 0;
    const featureExtractionCompleted = scenario.feature_extraction_completed || extractionPercent === 100;

    // Scan Progress
    const scansTotal = scenario.scans_total || 0;
    const scansDone = scenario.scans_completed || 0;
    const scansFailed = scenario.scans_failed || 0;
    const scansPercent = scansTotal > 0
        ? Math.round((scansDone / scansTotal) * 100)
        : 0;
    const scansInProgress = scansTotal > 0 && !scenario.scan_extraction_completed;

    // Show banner conditions:
    // 1. During ingestion
    // 2. During processing (feature extraction or scans)
    // 3. When scans are still in progress (even if status is "processed")
    const showIngestionBanner = isIngesting || isRetryingIngestion;
    const showProcessingBanner = isProcessing || isRetryingProcessing || scansInProgress;

    if (!showIngestionBanner && !showProcessingBanner && status !== "failed") return null;

    // Ingestion Banner
    if (showIngestionBanner) {
        let description = "";
        if (status === "queued") {
            description = "Waiting in queue...";
        } else {
            description = `Ingesting builds: ${buildsIngested}/${buildsTotal}`;
        }

        return (
            <div className="mb-4 rounded-md border p-4 bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800">
                <div className="flex items-start gap-3">
                    <div className="mt-0.5">
                        <RefreshCw className="h-4 w-4 animate-spin text-blue-500" />
                    </div>
                    <div className="flex-1 space-y-2">
                        <p className="font-medium text-sm">
                            {isRetryingIngestion ? "Retrying Ingestion" : "Ingesting Builds"}
                        </p>
                        <p className="text-sm text-muted-foreground">{description}</p>
                        {status === "ingesting" && (
                            <div className="space-y-1">
                                <div className="flex justify-between text-xs text-muted-foreground">
                                    <span>Progress</span>
                                    <span>{ingestionPercent}%</span>
                                </div>
                                <div className="h-2 w-full overflow-hidden rounded-full bg-secondary/50">
                                    <div
                                        className="h-full bg-blue-500 transition-all duration-500 ease-in-out"
                                        style={{ width: `${ingestionPercent}%` }}
                                    />
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        );
    }

    // Processing Banner (Feature Extraction + Scans)
    if (showProcessingBanner) {
        return (
            <div className="mb-4 rounded-md border p-4 bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800">
                <div className="flex items-start gap-3">
                    <div className="mt-0.5">
                        {featureExtractionCompleted && scenario.scan_extraction_completed ? (
                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                        ) : (
                            <Play className="h-4 w-4 text-green-500" />
                        )}
                    </div>
                    <div className="flex-1 space-y-4">
                        <p className="font-medium text-sm">
                            {isRetryingProcessing ? "Retrying Processing" : "Processing"}
                        </p>

                        {/* Feature Extraction Section */}
                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium">Feature Extraction</span>
                                    {featureExtractionCompleted && (
                                        <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                                    )}
                                </div>
                                <span className="text-xs text-muted-foreground">
                                    {extractionDone}/{extractionTotal} builds
                                </span>
                            </div>
                            <div className="h-2 w-full overflow-hidden rounded-full bg-secondary/50">
                                <div
                                    className="h-full bg-emerald-500 transition-all duration-500 ease-in-out"
                                    style={{ width: `${extractionPercent}%` }}
                                />
                            </div>
                        </div>

                        {/* Scan Metrics Section */}
                        {scansTotal > 0 && (
                            <div className="space-y-2">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm font-medium">Scan Metrics</span>
                                        {scenario.scan_extraction_completed && (
                                            <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                                        )}
                                        {!scenario.scan_extraction_completed && scansTotal > 0 && (
                                            <Loader2 className="h-3.5 w-3.5 animate-spin text-violet-500" />
                                        )}
                                    </div>
                                    <span className="text-xs text-muted-foreground">
                                        {scansDone}/{scansTotal} commits
                                        {scansFailed > 0 && (
                                            <span className="text-red-500 ml-1">({scansFailed} failed)</span>
                                        )}
                                    </span>
                                </div>
                                <div className="h-2 w-full overflow-hidden rounded-full bg-secondary/50">
                                    <div
                                        className="h-full bg-violet-500 transition-all duration-500 ease-in-out"
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

    return null;
}
