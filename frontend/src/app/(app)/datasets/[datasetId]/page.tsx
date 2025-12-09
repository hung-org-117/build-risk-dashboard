"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
    ArrowLeft,
    Database,
    Download,
    FileSpreadsheet,
    Loader2,
    RefreshCw,
    Settings,
    Zap,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { datasetsApi, enrichmentApi } from "@/lib/api";
import type { DatasetRecord } from "@/types";

import { DatasetOverviewTab } from "./_components/DatasetOverviewTab";
import { DatasetFeaturesTab } from "./_components/DatasetFeaturesTab";
import { SonarFeaturesTab } from "./_components/SonarFeaturesTab";

function formatDate(value?: string | null) {
    if (!value) return "—";
    try {
        return new Intl.DateTimeFormat(undefined, {
            dateStyle: "medium",
            timeStyle: "short",
        }).format(new Date(value));
    } catch {
        return value;
    }
}

export default function DatasetDetailPage() {
    const params = useParams();
    const router = useRouter();
    const datasetId = params.datasetId as string;

    const [dataset, setDataset] = useState<DatasetRecord | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState("overview");

    const loadDataset = useCallback(async () => {
        try {
            const data = await datasetsApi.get(datasetId);
            setDataset(data);
            setError(null);
        } catch (err) {
            console.error(err);
            setError("Unable to load dataset details.");
        } finally {
            setLoading(false);
        }
    }, [datasetId]);

    useEffect(() => {
        loadDataset();
    }, [loadDataset]);

    const handleDownload = async () => {
        try {
            const blob = await enrichmentApi.download(datasetId);
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `enriched_${dataset?.file_name || "dataset"}.csv`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (err) {
            console.error("Download failed:", err);
        }
    };

    const getStatusBadge = () => {
        if (!dataset) return null;
        const hasMapping = dataset.mapped_fields?.build_id && dataset.mapped_fields?.repo_name;
        const hasFeatures = (dataset.selected_features?.length || 0) > 0;

        if (!hasMapping) {
            return <Badge variant="secondary">Pending Mapping</Badge>;
        }
        if (!hasFeatures) {
            return <Badge variant="outline" className="border-amber-500 text-amber-600">No Features</Badge>;
        }
        return <Badge variant="outline" className="border-green-500 text-green-600">Ready</Badge>;
    };

    // Count sonar features
    const sonarFeatures = dataset?.selected_features?.filter(f => f.startsWith("sonar_")) || [];
    const regularFeatures = dataset?.selected_features?.filter(f => !f.startsWith("sonar_")) || [];

    if (loading) {
        return (
            <div className="flex min-h-[60vh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (error || !dataset) {
        return (
            <div className="space-y-4">
                <Button variant="ghost" onClick={() => router.back()} className="gap-2">
                    <ArrowLeft className="h-4 w-4" /> Back
                </Button>
                <Card className="border-red-200 bg-red-50/60 dark:border-red-800 dark:bg-red-900/20">
                    <CardHeader>
                        <CardTitle className="text-red-700 dark:text-red-300">Error</CardTitle>
                        <CardDescription>{error || "Dataset not found"}</CardDescription>
                    </CardHeader>
                </Card>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                    <Button variant="ghost" size="icon" onClick={() => router.push("/datasets")}>
                        <ArrowLeft className="h-4 w-4" />
                    </Button>
                    <div>
                        <div className="flex items-center gap-3">
                            <FileSpreadsheet className="h-6 w-6 text-muted-foreground" />
                            <h1 className="text-2xl font-bold">{dataset.name}</h1>
                            {getStatusBadge()}
                        </div>
                        <p className="mt-1 text-sm text-muted-foreground">
                            {dataset.file_name} • {dataset.rows.toLocaleString()} rows • Created {formatDate(dataset.created_at)}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={loadDataset}>
                        <RefreshCw className="mr-2 h-4 w-4" /> Refresh
                    </Button>
                    <Button variant="outline" size="sm" onClick={handleDownload}>
                        <Download className="mr-2 h-4 w-4" /> Download
                    </Button>
                </div>
            </div>

            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="overview" className="gap-2">
                        <Database className="h-4 w-4" /> Overview
                    </TabsTrigger>
                    <TabsTrigger value="features" className="gap-2">
                        <Zap className="h-4 w-4" />
                        Features
                        {regularFeatures.length > 0 && (
                            <Badge variant="secondary" className="ml-1">{regularFeatures.length}</Badge>
                        )}
                    </TabsTrigger>
                    <TabsTrigger value="sonar" className="gap-2">
                        <Settings className="h-4 w-4" />
                        SonarQube
                        {sonarFeatures.length > 0 && (
                            <Badge variant="secondary" className="ml-1">{sonarFeatures.length}</Badge>
                        )}
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="overview" className="mt-6">
                    <DatasetOverviewTab dataset={dataset} onRefresh={loadDataset} />
                </TabsContent>

                <TabsContent value="features" className="mt-6">
                    <DatasetFeaturesTab
                        datasetId={datasetId}
                        features={regularFeatures}
                        mappingReady={Boolean(dataset.mapped_fields?.build_id && dataset.mapped_fields?.repo_name)}
                    />
                </TabsContent>

                <TabsContent value="sonar" className="mt-6">
                    <SonarFeaturesTab
                        datasetId={datasetId}
                        features={sonarFeatures}
                    />
                </TabsContent>
            </Tabs>
        </div>
    );
}
