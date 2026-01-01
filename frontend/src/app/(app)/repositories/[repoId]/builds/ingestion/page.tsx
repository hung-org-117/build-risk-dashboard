"use client";

import { useParams } from "next/navigation";
import { useState } from "react";

import { reposApi } from "@/lib/api";
import { IngestionBuildsTable } from "../../_tabs/builds/IngestionBuildsTable";

export default function IngestionPage() {
    const params = useParams();
    const repoId = params.repoId as string;
    const [retryAllLoading, setRetryAllLoading] = useState(false);

    const handleRetryAllFailed = async () => {
        setRetryAllLoading(true);
        try {
            await reposApi.reingestFailed(repoId);
        } catch (err) {
            console.error(err);
        } finally {
            setRetryAllLoading(false);
        }
    };

    return (
        <IngestionBuildsTable
            repoId={repoId}
            onRetryAllFailed={handleRetryAllFailed}
            retryAllLoading={retryAllLoading}
        />
    );
}
