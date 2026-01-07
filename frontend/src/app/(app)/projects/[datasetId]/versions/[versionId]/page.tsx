"use client";

import { useCallback, useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { Loader2, Lock } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { datasetVersionApi } from "@/lib/api";
import { VersionMiniStepper, VersionIngestionCard, VersionProcessingCard, VersionDashboard } from "./_components";

interface VersionData {
    id: string;
    name: string;
    version_number: number;
    status: string;
    builds_total: number;
    builds_ingested: number;
    builds_missing_resource: number;
    builds_ingestion_failed: number;
    builds_features_extracted: number;
    builds_extraction_failed: number;
    selected_features: string[];
    created_at: string | null;
    completed_at: string | null;
    // Scan tracking
    scans_total?: number;
    scans_completed?: number;
    scans_failed?: number;
}

export default function VersionOverviewPage() {
    const params = useParams<{ datasetId: string; versionId: string }>();
    const datasetId = params.datasetId;
    const versionId = params.versionId;

    const [version, setVersion] = useState<VersionData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function fetchVersion() {
            setLoading(true);
            try {
                const response = await datasetVersionApi.getVersionData(
                    datasetId,
                    versionId,
                    1,
                    1,
                    false
                );
                setVersion(response.version);
            } catch (err) {
                console.error("Failed to fetch version:", err);
            } finally {
                setLoading(false);
            }
        }
        fetchVersion();
    }, [datasetId, versionId]);

    if (loading || !version) {
        return (
            <div className="flex min-h-[200px] items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex justify-center">
                <VersionMiniStepper
                    status={version.status}
                    progress={{
                        builds_total: version.builds_total,
                        builds_ingested: version.builds_ingested,
                        builds_missing_resource: version.builds_missing_resource,
                        builds_features_extracted: version.builds_features_extracted,
                        builds_extraction_failed: version.builds_extraction_failed,
                    }}
                />
            </div>
            <div className="grid md:grid-cols-2 gap-6">
                <VersionIngestionCard
                    buildsIngested={version.builds_ingested}
                    buildsTotal={version.builds_total}
                    buildsMissingResource={version.builds_missing_resource}
                    buildsIngestionFailed={version.builds_ingestion_failed || 0}
                    status={version.status}
                />
                <VersionProcessingCard
                    buildsExtracted={version.builds_features_extracted}
                    buildsIngested={version.builds_ingested}
                    buildsExtractionFailed={version.builds_extraction_failed}
                    status={version.status}
                    canStartProcessing={version.status === "ingested"}
                    scansCompleted={version.scans_completed}
                    scansTotal={version.scans_total}
                    scansFailed={version.scans_failed}
                />
            </div>

            <VersionDashboard
                datasetId={datasetId}
                versionId={versionId}
                versionStatus={version.status}
            />
        </div>
    );
}
