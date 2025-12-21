"use client";

import { useCallback } from "react";
import { Loader2, AlertCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { DatasetRecord } from "@/types";
import { FeatureSelectionCard } from "../FeatureSelection";
import { VersionHistory } from "../VersionHistory";
import { useDatasetVersions } from "../../_hooks/useDatasetVersions";

interface EnrichmentTabProps {
    datasetId: string;
    dataset: DatasetRecord;
    onEnrichmentStatusChange?: (hasActiveJob: boolean) => void;
}

export function EnrichmentTab({
    datasetId,
    dataset,
    onEnrichmentStatusChange,
}: EnrichmentTabProps) {
    const {
        versions,
        activeVersion,
        loading,
        creating,
        error,
        refresh,
        createVersion,
        cancelVersion,
        deleteVersion,
        downloadVersion,
    } = useDatasetVersions(datasetId);

    // Notify parent when active version status changes
    const hasActiveVersion = !!activeVersion;
    // Using useCallback to avoid re-renders
    const notifyParent = useCallback(() => {
        onEnrichmentStatusChange?.(hasActiveVersion);
    }, [hasActiveVersion, onEnrichmentStatusChange]);

    // Check if dataset is validated
    const isValidated = dataset.validation_status === "completed";
    const mappingReady = Boolean(
        dataset.mapped_fields?.build_id && dataset.mapped_fields?.repo_name
    );

    // Handle create version
    const handleCreateVersion = async (
        features: string[],
        featureConfigs: {
            global: Record<string, unknown>;
            repos: Record<string, { source_languages: string[]; test_frameworks: string[] }>;
        },
        scanData: {
            metrics: { sonarqube: string[]; trivy: string[] };
            config: {
                sonarqube: { projectKey?: string; sonarToken?: string; sonarUrl?: string; extraProperties?: string };
                trivy: { severity?: string; scanners?: string; extraArgs?: string };
            };
        },
        name?: string
    ) => {
        // Flatten configs for API: merge global + repos into single object
        const flatConfigs: Record<string, unknown> = {
            ...featureConfigs.global,
            repo_configs: featureConfigs.repos,
        };
        const version = await createVersion({
            selected_features: features,
            feature_configs: flatConfigs,
            scan_metrics: scanData.metrics,
            scan_config: scanData.config,
            name,
        });
        if (version) {
            notifyParent();
        }
    };



    // Handle cancel
    const handleCancel = async (versionId: string) => {
        await cancelVersion(versionId);
        notifyParent();
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    // Show warning if not validated
    if (!isValidated) {
        return (
            <Alert variant="destructive" className="my-4">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                    Dataset validation must be completed before creating enriched
                    versions. Please go to the Configuration tab to validate.
                </AlertDescription>
            </Alert>
        );
    }

    // Show warning if mapping not ready
    if (!mappingReady) {
        return (
            <Alert variant="destructive" className="my-4">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                    Dataset must have <code>build_id</code> and{" "}
                    <code>repo_name</code> columns mapped before enrichment.
                </AlertDescription>
            </Alert>
        );
    }

    return (
        <div className="space-y-6">
            {/* Error Alert */}
            {error && (
                <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>{error}</AlertDescription>
                </Alert>
            )}

            {/* Feature Selection Card */}
            <FeatureSelectionCard
                datasetId={datasetId}
                rowCount={dataset.rows || 0}
                onCreateVersion={handleCreateVersion}
                isCreating={creating}
                hasActiveVersion={hasActiveVersion}
            />

            {/* Version History */}
            <VersionHistory
                datasetId={datasetId}
                versions={versions}
                loading={loading}
                onRefresh={refresh}
                onDownload={downloadVersion}
                onDelete={deleteVersion}
                onCancel={handleCancel}
            />
        </div>
    );
}
