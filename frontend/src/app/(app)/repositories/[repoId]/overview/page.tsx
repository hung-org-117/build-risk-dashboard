"use client";

import { useRepo } from "@/components/repositories/RepoContext";
import { OverviewTab } from "@/components/repositories/tabs/OverviewTab";

export default function OverviewPage() {
    const {
        repo,
        progress,
        builds,
        handleSync,
        handleRetryIngestion,
        handleStartProcessing,
        handleRetryProcessing,
        syncLoading,
        retryIngestionLoading,
        startProcessingLoading,
        retryProcessingLoading,
    } = useRepo();

    if (!repo) return null;

    return (
        <OverviewTab
            repo={repo}
            progress={progress}
            builds={builds}
            onSync={handleSync}
            onRetryIngestion={handleRetryIngestion}
            onStartProcessing={handleStartProcessing}
            onRetryFailed={handleRetryProcessing}
            syncLoading={syncLoading}
            retryIngestionLoading={retryIngestionLoading}
            startProcessingLoading={startProcessingLoading}
            retryFailedLoading={retryProcessingLoading}
        />
    );
}
