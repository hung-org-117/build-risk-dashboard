"use client";

import { useParams, usePathname } from "next/navigation";
import Link from "next/link";
import { ReactNode, useState, useEffect } from "react";
import {
    ArrowLeft,
    Loader2,
    CheckCircle2,
    XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { trainingScenariosApi, TrainingScenarioRecord } from "@/lib/api/training-scenarios";
import { useSSE } from "@/contexts/sse-context";
import { ScenarioActionProgressBanner } from "./_components/ScenarioActionProgressBanner";

// Status config
const getStatusConfig = (status: string) => {
    const key = status.toLowerCase();
    const config: Record<string, { icon: typeof CheckCircle2; color: string; bgColor: string }> = {
        queued: { icon: Loader2, color: "text-slate-600", bgColor: "bg-slate-100" },
        filtering: { icon: Loader2, color: "text-blue-600", bgColor: "bg-blue-100" },
        ingesting: { icon: Loader2, color: "text-blue-600", bgColor: "bg-blue-100" },
        ingested: { icon: CheckCircle2, color: "text-emerald-600", bgColor: "bg-emerald-100" },
        processing: { icon: Loader2, color: "text-purple-600", bgColor: "bg-purple-100" },
        processed: { icon: CheckCircle2, color: "text-green-600", bgColor: "bg-green-100" },
        splitting: { icon: Loader2, color: "text-amber-600", bgColor: "bg-amber-100" },
        completed: { icon: CheckCircle2, color: "text-green-600", bgColor: "bg-green-100" },
        failed: { icon: XCircle, color: "text-red-600", bgColor: "bg-red-100" },
    };
    return config[key] || config.failed;
};

export default function ScenarioLayout({ children }: { children: ReactNode }) {
    const params = useParams<{ scenarioId: string }>();
    const pathname = usePathname();
    const scenarioId = params.scenarioId;
    const { subscribe } = useSSE();

    const [scenario, setScenario] = useState<TrainingScenarioRecord | null>(null);
    const [loading, setLoading] = useState(true);

    // Determine active tab from pathname
    const getActiveTab = () => {
        if (pathname.includes("/builds")) return "builds";
        if (pathname.includes("/analysis")) return "analysis";
        if (pathname.includes("/export")) return "export";
        return "overview";
    };
    const activeTab = getActiveTab();

    // Fetch scenario data
    useEffect(() => {
        async function fetchScenario() {
            setLoading(true);
            try {
                const data = await trainingScenariosApi.get(scenarioId);
                setScenario(data);
            } catch (err) {
                console.error("Failed to fetch scenario:", err);
            } finally {
                setLoading(false);
            }
        }
        fetchScenario();
    }, [scenarioId]);

    // Subscribe to SSE for real-time updates
    useEffect(() => {
        const unsubscribe = subscribe("SCENARIO.UPDATED", (data: Partial<TrainingScenarioRecord> & { scenario_id?: string }) => {
            if (data.scenario_id === scenarioId && data.status) {
                setScenario((prev) =>
                    prev
                        ? {
                            ...prev,
                            status: data.status || prev.status,
                            builds_total: data.builds_total ?? prev.builds_total,
                            builds_ingested: data.builds_ingested ?? prev.builds_ingested,
                            builds_features_extracted: data.builds_features_extracted ?? prev.builds_features_extracted,
                            builds_ingestion_failed: (data as any).builds_ingestion_failed ?? prev.builds_ingestion_failed,
                            builds_features_extracted_failed: (data as any).builds_features_extracted_failed ?? prev.builds_features_extracted_failed,
                            scans_total: data.scans_total ?? prev.scans_total,
                            scans_completed: data.scans_completed ?? prev.scans_completed,
                            scans_failed: (data as any).scans_failed ?? prev.scans_failed,
                            feature_extraction_completed: (data as any).feature_extraction_completed ?? prev.feature_extraction_completed,
                            scan_extraction_completed: (data as any).scan_extraction_completed ?? prev.scan_extraction_completed,
                        }
                        : prev
                );
            }
        });
        return () => unsubscribe();
    }, [subscribe, scenarioId]);

    if (loading || !scenario) {
        return (
            <div className="flex min-h-[400px] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    const statusConfig = getStatusConfig(scenario.status);
    const StatusIcon = statusConfig.icon;

    const basePath = `/scenarios/${scenarioId}`;

    return (
        <div className="space-y-6 p-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Link href="/scenarios">
                        <Button variant="ghost" size="sm">
                            <ArrowLeft className="mr-2 h-4 w-4" />
                            Back
                        </Button>
                    </Link>
                    <div>
                        <h1 className="text-2xl font-bold">{scenario.name}</h1>
                        {scenario.description && (
                            <p className="text-sm text-muted-foreground">
                                {scenario.description}
                            </p>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <Badge
                        className={`${statusConfig.bgColor} ${statusConfig.color} hover:${statusConfig.bgColor} cursor-default`}
                    >
                        <StatusIcon
                            className={`mr-1 h-3 w-3 ${["queued", "filtering", "ingesting", "processing", "splitting"].includes(
                                scenario.status
                            )
                                ? "animate-spin"
                                : ""
                                }`}
                        />
                        {scenario.status.charAt(0).toUpperCase() + scenario.status.slice(1)}
                    </Badge>
                </div>
            </div>

            {/* Tab Navigation */}
            <Tabs value={activeTab}>
                <TabsList className="grid w-full grid-cols-4 mb-4">
                    <TabsTrigger value="overview" asChild>
                        <Link href={basePath} className="gap-2">
                            Overview
                        </Link>
                    </TabsTrigger>
                    <TabsTrigger value="builds" asChild>
                        <Link href={`${basePath}/builds`} className="gap-2">
                            Builds
                        </Link>
                    </TabsTrigger>
                    <TabsTrigger value="analysis" asChild>
                        <Link href={`${basePath}/analysis`} className="gap-2">
                            Analysis
                        </Link>
                    </TabsTrigger>
                    <TabsTrigger value="export" asChild>
                        <Link href={`${basePath}/export`} className="gap-2">
                            Export
                        </Link>
                    </TabsTrigger>
                </TabsList>
            </Tabs>

            {/* Progress Banner (shown across all tabs during active operations) */}
            <ScenarioActionProgressBanner scenario={scenario} />

            {/* Page Content */}
            {children}
        </div>
    );
}
