"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { reposApi } from "@/lib/api";
import { UnifiedBuildsTable } from "../_tabs/builds/UnifiedBuildsTable";
import { useRepo } from "@/components/repositories/RepoContext";
import { useSSE } from "@/contexts/sse-context";
import { ActionProgressBanner } from "../../_components/ActionProgressBanner";

export default function BuildsPage() {
    const params = useParams();
    const repoId = params.repoId as string;
    const { repo, progress, syncLoading, startProcessingLoading } = useRepo();
    const { subscribe } = useSSE();

    const [retryIngestionLoading, setRetryIngestionLoading] = useState(false);
    const [retryProcessingLoading, setRetryProcessingLoading] = useState(false);
    
    // Track current phase and build-level progress for ActionProgressBanner
    const [currentPhase, setCurrentPhase] = useState<"ingestion" | "extraction" | "prediction">();
    const [currentBuildProgress, setCurrentBuildProgress] = useState<{
        buildNumber?: number;
        featureCount?: number;
        expectedFeatureCount?: number;
        extractionStatus?: string;
        predictionStatus?: string;
    }>();

    // Subscribe to SSE events for real-time progress tracking
    useEffect(() => {
        const unsubscribeProcessing = subscribe("MODEL.PROCESSING.UPDATED", (payload: {
            repo_id: string;
            build_id: string;
            extraction_status: string;
            feature_count?: number;
            expected_feature_count?: number;
        }) => {
            if (payload.repo_id === repoId && payload.extraction_status === "in_progress") {
                setCurrentPhase("extraction");
                setCurrentBuildProgress({
                    featureCount: payload.feature_count,
                    expectedFeatureCount: payload.expected_feature_count,
                    extractionStatus: payload.extraction_status,
                });
            } else if (payload.repo_id === repoId && ["completed", "failed", "partial"].includes(payload.extraction_status)) {
                // Clear current progress when extraction completes
                setCurrentBuildProgress(undefined);
            }
        });

        const unsubscribePrediction = subscribe("MODEL.PREDICTION.UPDATED", (payload: {
            repo_id: string;
            build_id: string;
            prediction_status: string;
        }) => {
            if (payload.repo_id === repoId && payload.prediction_status === "in_progress") {
                setCurrentPhase("prediction");
                setCurrentBuildProgress({
                    predictionStatus: payload.prediction_status,
                });
            } else if (payload.repo_id === repoId && ["completed", "failed"].includes(payload.prediction_status)) {
                setCurrentBuildProgress(undefined);
            }
        });

        const unsubscribeIngestion = subscribe("MODEL.INGESTION.PROGRESS", (payload: {
            repo_id: string;
            status: string;
        }) => {
            if (payload.repo_id === repoId && payload.status === "in_progress") {
                setCurrentPhase("ingestion");
            }
        });

        return () => {
            unsubscribeProcessing();
            unsubscribePrediction();
            unsubscribeIngestion();
        };
    }, [subscribe, repoId]);

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
                currentPhase={currentPhase}
                currentBuildProgress={currentBuildProgress}
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
