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

    // Failed ingestion count: only count failed AFTER checkpoint (not missing_resource)
    // Progress API counts builds after checkpoint already
    const failedIngestionCount = progress?.import_builds.total
        ? progress.import_builds.total - progress.import_builds.ingested - (progress.import_builds.missing_resource || 0)
        : 0;

    // Failed processing count: all failed extraction + prediction
    const failedProcessingCount = (progress?.training_builds.failed || 0) +
        (progress?.training_builds.prediction_failed || 0);

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
