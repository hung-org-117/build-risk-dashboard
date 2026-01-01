"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

export default function BuildsPage() {
    const params = useParams();
    const router = useRouter();
    const repoId = params.repoId as string;

    useEffect(() => {
        // Redirect to ingestion sub-tab
        router.replace(`/repositories/${repoId}/builds/ingestion`);
    }, [repoId, router]);

    return null;
}
