"use client";

import { redirect } from "next/navigation";
import { useParams } from "next/navigation";

export default function BuildsPage() {
    const params = useParams<{ scenarioId: string }>();
    redirect(`/scenarios/${params.scenarioId}/builds/ingestion`);
}
