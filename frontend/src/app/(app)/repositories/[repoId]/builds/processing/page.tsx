"use client";

import { useParams } from "next/navigation";
import { useState } from "react";

import { reposApi } from "@/lib/api";
import { ProcessingBuildsTable } from "../../_tabs/builds/ProcessingBuildsTable";
import { useRepo } from "../../repo-context";

export default function ProcessingPage() {
    const params = useParams();
    const repoId = params.repoId as string;
    const [retryAllLoading, setRetryAllLoading] = useState(false);

    const { progress } = useRepo();

    // Get total failed count from progress API (extraction + prediction failures)
    const totalFailedCount = (progress?.training_builds.failed || 0) +
        (progress?.training_builds.prediction_failed || 0);

    const handleRetryAllFailed = async () => {
        setRetryAllLoading(true);
        try {
            await reposApi.reprocessFailed(repoId);
        } catch (err) {
            console.error(err);
        } finally {
            setRetryAllLoading(false);
        }
    };

    return (
        <ProcessingBuildsTable
            repoId={repoId}
            onRetryAllFailed={handleRetryAllFailed}
            retryAllLoading={retryAllLoading}
            totalFailedCount={totalFailedCount}
        />
    );
}
