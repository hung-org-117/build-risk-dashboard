"use client";

import { useParams } from "next/navigation";
import { useState } from "react";

import { reposApi } from "@/lib/api";
import { ProcessingBuildsTable } from "../../_tabs/builds/ProcessingBuildsTable";

export default function ProcessingPage() {
    const params = useParams();
    const repoId = params.repoId as string;
    const [retryAllLoading, setRetryAllLoading] = useState(false);

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
        />
    );
}
