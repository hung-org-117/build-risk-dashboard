"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

export default function BuildsPage() {
    const params = useParams();
    const router = useRouter();
    const scenarioId = params.scenarioId as string;

    useEffect(() => {
        // Redirect to ingestion tab by default
        router.replace(`/ml-scenarios/${scenarioId}/builds/ingestion`);
    }, [scenarioId, router]);

    return null;
}
