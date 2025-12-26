"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
    Database,
    CheckCircle2,
    TrendingUp,
    Layers,
    AlertTriangle,
    ArrowRight,
} from "lucide-react";
import { statisticsApi, qualityApi, type VersionStatisticsResponse } from "@/lib/api";

interface VersionDashboardProps {
    datasetId: string;
    versionId: string;
    versionStatus: string;
    onNavigateToAnalysis?: () => void;
}

interface DashboardData {
    totalBuilds: number;
    enrichedBuilds: number;
    enrichmentRate: number;
    qualityScore: number | null;
    featuresSelected: number;
    buildStatusBreakdown: { status: string; count: number; percentage: number }[];
    topIssues: { message: string; severity: string }[];
}

export function VersionDashboard({
    datasetId,
    versionId,
    versionStatus,
    onNavigateToAnalysis,
}: VersionDashboardProps) {
    const [data, setData] = useState<DashboardData | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    const fetchDashboardData = useCallback(async () => {
        if (!versionId) return;

        setIsLoading(true);
        try {
            // Fetch statistics
            const statsResponse = await statisticsApi.getVersionStatistics(datasetId, versionId);

            let qualityScore: number | null = null;
            let topIssues: { message: string; severity: string }[] = [];

            // Fetch quality report if version is completed
            if (versionStatus === "completed") {
                try {
                    const qualityResponse = await qualityApi.getReport(datasetId, versionId);
                    if (!("available" in qualityResponse) || qualityResponse.available !== false) {
                        qualityScore = (qualityResponse as { quality_score: number }).quality_score;
                        topIssues = ((qualityResponse as { issues?: { message: string; severity: string }[] }).issues || []).slice(0, 3);
                    }
                } catch {
                    // Quality report not available
                }
            }

            setData({
                totalBuilds: statsResponse.statistics.total_builds,
                enrichedBuilds: statsResponse.statistics.enriched_builds,
                enrichmentRate: statsResponse.statistics.enrichment_rate,
                qualityScore,
                featuresSelected: statsResponse.statistics.total_features_selected,
                buildStatusBreakdown: statsResponse.build_status_breakdown,
                topIssues,
            });
        } catch (err) {
            console.error("Failed to fetch dashboard data:", err);
        } finally {
            setIsLoading(false);
        }
    }, [datasetId, versionId, versionStatus]);

    useEffect(() => {
        fetchDashboardData();
    }, [fetchDashboardData]);

    if (isLoading || !data) {
        return (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 animate-pulse">
                {[...Array(4)].map((_, i) => (
                    <Card key={i}>
                        <CardContent className="pt-4">
                            <div className="h-4 bg-muted rounded w-24 mb-2" />
                            <div className="h-8 bg-muted rounded w-16" />
                        </CardContent>
                    </Card>
                ))}
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* KPI Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <KPICard
                    icon={Database}
                    label="Total Builds"
                    value={data.totalBuilds.toLocaleString()}
                    variant="default"
                />
                <KPICard
                    icon={CheckCircle2}
                    label="Enriched"
                    value={`${data.enrichmentRate.toFixed(1)}%`}
                    subValue={`${data.enrichedBuilds} builds`}
                    variant="success"
                />
                <KPICard
                    icon={TrendingUp}
                    label="Quality Score"
                    value={data.qualityScore !== null ? data.qualityScore.toFixed(1) : "—"}
                    variant={data.qualityScore !== null ? (data.qualityScore >= 80 ? "success" : data.qualityScore >= 60 ? "warning" : "error") : "default"}
                />
                <KPICard
                    icon={Layers}
                    label="Features"
                    value={data.featuresSelected.toString()}
                    variant="default"
                />
            </div>

            {/* Build Status + Issues Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Build Status Mini Bar */}
                <Card>
                    <CardContent className="pt-4">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-medium">Build Status</span>
                        </div>
                        <div className="flex h-3 rounded-full overflow-hidden bg-muted mb-2">
                            {data.buildStatusBreakdown.map((item) => (
                                <div
                                    key={item.status}
                                    className={getStatusColor(item.status)}
                                    style={{ width: `${item.percentage}%` }}
                                    title={`${item.status}: ${item.count}`}
                                />
                            ))}
                        </div>
                        <div className="flex flex-wrap gap-3 text-xs">
                            {data.buildStatusBreakdown.map((item) => (
                                <div key={item.status} className="flex items-center gap-1">
                                    <div className={`w-2 h-2 rounded-full ${getStatusColor(item.status)}`} />
                                    <span className="capitalize">{item.status}</span>
                                    <span className="text-muted-foreground">({item.count})</span>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>

                {/* Top Issues */}
                <Card>
                    <CardContent className="pt-4">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-medium">Top Issues</span>
                            {data.topIssues.length > 0 && onNavigateToAnalysis && (
                                <button
                                    onClick={onNavigateToAnalysis}
                                    className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                                >
                                    View All <ArrowRight className="h-3 w-3" />
                                </button>
                            )}
                        </div>
                        {data.topIssues.length > 0 ? (
                            <div className="space-y-2">
                                {data.topIssues.map((issue, idx) => (
                                    <div key={idx} className="flex items-start gap-2 text-sm">
                                        <AlertTriangle className={`h-4 w-4 mt-0.5 shrink-0 ${issue.severity === "error" ? "text-red-500" : "text-yellow-500"
                                            }`} />
                                        <span className="text-muted-foreground line-clamp-1">{issue.message}</span>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <CheckCircle2 className="h-4 w-4 text-green-500" />
                                <span>No issues detected</span>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}

// =============================================================================
// Sub-components
// =============================================================================

interface KPICardProps {
    icon: React.ElementType;
    label: string;
    value: string;
    subValue?: string;
    variant?: "default" | "success" | "warning" | "error";
}

function KPICard({ icon: Icon, label, value, subValue, variant = "default" }: KPICardProps) {
    const variantStyles = {
        default: "",
        success: "border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-900/10",
        warning: "border-yellow-200 dark:border-yellow-800 bg-yellow-50/50 dark:bg-yellow-900/10",
        error: "border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10",
    };

    const iconStyles = {
        default: "text-muted-foreground",
        success: "text-green-600",
        warning: "text-yellow-600",
        error: "text-red-600",
    };

    return (
        <Card className={variantStyles[variant]}>
            <CardContent className="pt-4">
                <div className="flex items-center gap-2 mb-1">
                    <Icon className={`h-4 w-4 ${iconStyles[variant]}`} />
                    <span className="text-sm text-muted-foreground">{label}</span>
                </div>
                <div className="flex items-baseline gap-2">
                    <span className="text-2xl font-bold">{value}</span>
                    {subValue && (
                        <span className="text-xs text-muted-foreground">{subValue}</span>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}

function getStatusColor(status: string): string {
    switch (status) {
        case "completed":
        case "success":
            return "bg-green-500";
        case "failed":
        case "error":
            return "bg-red-500";
        case "partial":
            return "bg-yellow-500";
        case "pending":
            return "bg-gray-400";
        default:
            return "bg-blue-500";
    }
}
