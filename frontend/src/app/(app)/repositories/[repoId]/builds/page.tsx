"use client";

import { useParams } from "next/navigation";
import { useState } from "react";

import { reposApi } from "@/lib/api";
import { UnifiedBuildsTable } from "../_tabs/builds/UnifiedBuildsTable";
import { useRepo } from "../repo-context";
import { ActionProgressBanner } from "../../_components/ActionProgressBanner";

export default function BuildsPage() {
    const params = useParams();
    const repoId = params.repoId as string;
    const { repo, progress, syncLoading, startProcessingLoading } = useRepo();

    const [retryIngestionLoading, setRetryIngestionLoading] = useState(false);
    const [retryProcessingLoading, setRetryProcessingLoading] = useState(false);

    const handleRetryIngestion = async () => {
        setRetryIngestionLoading(true);
        try {
            await reposApi.reingestFailed(repoId);
        } catch (err) {
            console.error("Failed to retry ingestion:", err);
        } finally {
            setRetryIngestionLoading(false);
        }
    };

    const handleRetryProcessing = async () => {
        setRetryProcessingLoading(true);
        try {
            await reposApi.reprocessFailed(repoId);
        } catch (err) {
            console.error("Failed to retry processing:", err);
        } finally {
            setRetryProcessingLoading(false);
        }
    };

    // Syncing status check - hide retry buttons during ingestion
    const isSyncing = ["queued", "fetching", "ingesting"].includes(repo?.status?.toLowerCase() || "");

    // Failed ingestion count: use the failed count from progress API
    // Hide during syncing for cleaner UX
    const failedIngestionCount = isSyncing ? 0 :
        (progress?.import_builds.total || 0) -
        (progress?.import_builds.ingested || 0) -
        (progress?.import_builds.missing_resource || 0) -
        (progress?.import_builds.pending || 0) -
        (progress?.import_builds.fetched || 0) -
        (progress?.import_builds.ingesting || 0);

    // Failed processing count: all failed extraction + prediction
    // Hide failed count while processing is in progress (confusing UX)
    const isProcessing = repo?.status?.toLowerCase() === "processing";
    const failedProcessingCount = isProcessing ? 0 :
        (progress?.training_builds.failed || 0) + (progress?.training_builds.prediction_failed || 0);

    return (
        <div className="space-y-0">
            {/* Action Progress Banner */}
            <ActionProgressBanner
                repoStatus={repo?.status || ""}
                progress={progress}
                syncLoading={syncLoading}
                processingLoading={startProcessingLoading}
                retryIngestionLoading={retryIngestionLoading}
                retryProcessingLoading={retryProcessingLoading}
            />

            {/* Builds Table */}
            <UnifiedBuildsTable
                repoId={repoId}
                onRetryIngestion={handleRetryIngestion}
                onRetryProcessing={handleRetryProcessing}
                retryIngestionLoading={retryIngestionLoading}
                retryProcessingLoading={retryProcessingLoading}
                failedIngestionCount={failedIngestionCount > 0 ? failedIngestionCount : 0}
                failedProcessingCount={failedProcessingCount}
            />
        </div>
    );
}
