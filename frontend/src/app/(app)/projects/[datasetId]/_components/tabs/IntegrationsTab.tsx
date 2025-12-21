"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { api } from "@/lib/api";
import {
    AlertCircle,
    CheckCircle2,
    ChevronDown,
    ChevronUp,
    Clock,
    Loader2,
    RefreshCw,
    RotateCcw,
    Shield,
    Settings,
    XCircle,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

interface IntegrationsTabProps {
    datasetId: string;
}

interface DatasetVersion {
    id: string;
    version_number: number;
    name: string;
    status: string;
    scan_metrics: {
        sonarqube?: string[];
        trivy?: string[];
    };
}

interface CommitScan {
    id: string;
    commit_sha: string;
    repo_full_name: string;
    status: string;
    error_message: string | null;
    builds_affected: number;
    retry_count: number;
    started_at: string | null;
    completed_at: string | null;
    component_key?: string;
}

interface CommitScansResponse {
    trivy: CommitScan[];
    sonarqube: CommitScan[];
}

// =============================================================================
// Component
// =============================================================================

export function IntegrationsTab({ datasetId }: IntegrationsTabProps) {
    const [versions, setVersions] = useState<DatasetVersion[]>([]);
    const [loading, setLoading] = useState(true);
    const [expandedVersionId, setExpandedVersionId] = useState<string | null>(null);
    const [commitScans, setCommitScans] = useState<CommitScansResponse | null>(null);
    const [loadingScans, setLoadingScans] = useState(false);
    const [retryingCommit, setRetryingCommit] = useState<string | null>(null);

    // Load versions with scan_metrics
    const loadVersions = useCallback(async () => {
        try {
            setLoading(true);
            const response = await api.get<{ versions: DatasetVersion[] }>(
                `/datasets/${datasetId}/versions`
            );
            // Filter to versions that have scan metrics configured
            const versionsWithScans = response.data.versions.filter(
                (v) =>
                    (v.scan_metrics?.sonarqube?.length || 0) > 0 ||
                    (v.scan_metrics?.trivy?.length || 0) > 0
            );
            setVersions(versionsWithScans);
        } catch {
            setVersions([]);
        } finally {
            setLoading(false);
        }
    }, [datasetId]);

    // Load commit scans for a version
    const loadCommitScans = async (versionId: string) => {
        if (expandedVersionId === versionId) {
            setExpandedVersionId(null);
            setCommitScans(null);
            return;
        }

        setLoadingScans(true);
        try {
            const response = await api.get<CommitScansResponse>(
                `/datasets/${datasetId}/versions/${versionId}/commit-scans`
            );
            setCommitScans(response.data);
            setExpandedVersionId(versionId);
        } catch (error) {
            console.error("Failed to load commit scans:", error);
        } finally {
            setLoadingScans(false);
        }
    };

    // Retry a specific commit scan
    const handleRetry = async (versionId: string, commitSha: string, toolType: string) => {
        setRetryingCommit(`${commitSha}-${toolType}`);
        try {
            await api.post(
                `/datasets/${datasetId}/versions/${versionId}/commits/${commitSha}/retry/${toolType}`
            );
            // Reload scans
            await loadCommitScans(versionId);
        } catch (error) {
            console.error("Failed to retry scan:", error);
        } finally {
            setRetryingCommit(null);
        }
    };

    useEffect(() => {
        loadVersions();
    }, [loadVersions]);

    // Render status badge
    const renderStatus = (status: string) => {
        switch (status) {
            case "completed":
                return (
                    <Badge className="bg-green-500">
                        <CheckCircle2 className="h-3 w-3 mr-1" />
                        Completed
                    </Badge>
                );
            case "scanning":
                return (
                    <Badge className="bg-blue-500">
                        <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                        Scanning
                    </Badge>
                );
            case "pending":
                return (
                    <Badge variant="secondary">
                        <Clock className="h-3 w-3 mr-1" />
                        Pending
                    </Badge>
                );
            case "failed":
                return (
                    <Badge variant="destructive">
                        <XCircle className="h-3 w-3 mr-1" />
                        Failed
                    </Badge>
                );
            default:
                return <Badge variant="outline">{status}</Badge>;
        }
    };

    // Render scan table
    const renderScanTable = (scans: CommitScan[], toolType: string, versionId: string) => {
        if (scans.length === 0) {
            return (
                <p className="text-sm text-muted-foreground py-4 text-center">
                    No {toolType} scans found
                </p>
            );
        }

        return (
            <table className="min-w-full text-sm">
                <thead className="bg-slate-50 dark:bg-slate-800">
                    <tr>
                        <th className="px-3 py-2 text-left font-medium">Commit</th>
                        <th className="px-3 py-2 text-left font-medium">Repository</th>
                        <th className="px-3 py-2 text-left font-medium">Status</th>
                        <th className="px-3 py-2 text-left font-medium">Builds</th>
                        <th className="px-3 py-2 text-left font-medium">Actions</th>
                    </tr>
                </thead>
                <tbody className="divide-y">
                    {scans.map((scan) => (
                        <tr key={scan.id}>
                            <td className="px-3 py-2 font-mono text-xs">
                                {scan.commit_sha.slice(0, 8)}
                            </td>
                            <td className="px-3 py-2 text-muted-foreground">
                                {scan.repo_full_name}
                            </td>
                            <td className="px-3 py-2">
                                {renderStatus(scan.status)}
                                {scan.retry_count > 0 && (
                                    <span className="ml-2 text-xs text-muted-foreground">
                                        (retry #{scan.retry_count})
                                    </span>
                                )}
                            </td>
                            <td className="px-3 py-2">{scan.builds_affected}</td>
                            <td className="px-3 py-2">
                                {scan.status === "failed" && (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => handleRetry(versionId, scan.commit_sha, toolType)}
                                        disabled={retryingCommit === `${scan.commit_sha}-${toolType}`}
                                    >
                                        {retryingCommit === `${scan.commit_sha}-${toolType}` ? (
                                            <Loader2 className="h-3 w-3 animate-spin" />
                                        ) : (
                                            <RotateCcw className="h-3 w-3" />
                                        )}
                                        <span className="ml-1">Retry</span>
                                    </Button>
                                )}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        );
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (versions.length === 0) {
        return (
            <Card>
                <CardContent className="py-12 text-center">
                    <AlertCircle className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                    <h3 className="font-semibold mb-2">No Scan-Enabled Versions</h3>
                    <p className="text-muted-foreground">
                        Create a version with SonarQube or Trivy metrics selected to see scan status here.
                    </p>
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Commit Scan Status</h2>
                <Button variant="outline" size="sm" onClick={loadVersions}>
                    <RefreshCw className="h-4 w-4" />
                </Button>
            </div>

            {/* Version Cards */}
            {versions.map((version) => (
                <Card key={version.id}>
                    <CardHeader
                        className="cursor-pointer"
                        onClick={() => loadCommitScans(version.id)}
                    >
                        <div className="flex items-center justify-between">
                            <div>
                                <CardTitle className="text-base">
                                    Version {version.version_number}
                                    {version.name && ` - ${version.name}`}
                                </CardTitle>
                                <CardDescription className="flex items-center gap-2 mt-1">
                                    {version.scan_metrics?.trivy?.length ? (
                                        <Badge variant="secondary" className="text-xs">
                                            <Shield className="h-3 w-3 mr-1" />
                                            Trivy
                                        </Badge>
                                    ) : null}
                                    {version.scan_metrics?.sonarqube?.length ? (
                                        <Badge variant="secondary" className="text-xs">
                                            <Settings className="h-3 w-3 mr-1" />
                                            SonarQube
                                        </Badge>
                                    ) : null}
                                </CardDescription>
                            </div>
                            <div className="flex items-center gap-2">
                                <Badge variant="outline">{version.status}</Badge>
                                {loadingScans && expandedVersionId === version.id ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : expandedVersionId === version.id ? (
                                    <ChevronUp className="h-4 w-4" />
                                ) : (
                                    <ChevronDown className="h-4 w-4" />
                                )}
                            </div>
                        </div>
                    </CardHeader>

                    {/* Expanded Content */}
                    {expandedVersionId === version.id && commitScans && (
                        <CardContent className="pt-0">
                            <div className="space-y-6">
                                {/* Trivy Scans */}
                                {version.scan_metrics?.trivy?.length ? (
                                    <div>
                                        <h4 className="font-medium mb-2 flex items-center gap-2">
                                            <Shield className="h-4 w-4" />
                                            Trivy Scans ({commitScans.trivy.length})
                                        </h4>
                                        <div className="border rounded-lg overflow-hidden">
                                            {renderScanTable(commitScans.trivy, "trivy", version.id)}
                                        </div>
                                    </div>
                                ) : null}

                                {/* SonarQube Scans */}
                                {version.scan_metrics?.sonarqube?.length ? (
                                    <div>
                                        <h4 className="font-medium mb-2 flex items-center gap-2">
                                            <Settings className="h-4 w-4" />
                                            SonarQube Scans ({commitScans.sonarqube.length})
                                        </h4>
                                        <div className="border rounded-lg overflow-hidden">
                                            {renderScanTable(commitScans.sonarqube, "sonarqube", version.id)}
                                        </div>
                                    </div>
                                ) : null}
                            </div>
                        </CardContent>
                    )}
                </Card>
            ))}
        </div>
    );
}
