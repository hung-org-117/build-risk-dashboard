"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import {
    trainingScenariosApi,
    TrainingExportRecord,
    TrainingScenarioRecord,
    TrainingDatasetSplitRecord,
} from "@/lib/api/training-scenarios";
import { toast } from "@/components/ui/use-toast";
import { useSSE } from "@/contexts/sse-context";
import {
    ExportsListSection,
    DatasetSummarySection,
    NotReadyState,
    LoadingState,
} from "./_components";

// =============================================================================
// Component
// =============================================================================

export default function ScenarioExportPage() {
    const params = useParams<{ scenarioId: string }>();
    const router = useRouter();
    const scenarioId = params.scenarioId;
    const { subscribe } = useSSE();

    const [scenario, setScenario] = useState<TrainingScenarioRecord | null>(null);
    const [exports, setExports] = useState<TrainingExportRecord[]>([]);
    const [loading, setLoading] = useState(true);

    // View state: "list" | "detail"
    const [viewingExport, setViewingExport] = useState<TrainingExportRecord | null>(null);
    const [viewingSplits, setViewingSplits] = useState<TrainingDatasetSplitRecord[]>([]);

    // =============================================================================
    // Derived State
    // =============================================================================

    const canGenerate = scenario?.status === "processed" || scenario?.status === "completed";

    // Scan progress tracking
    const scansCompleted = scenario?.scan_extraction_completed ?? false;
    const scansTotal = scenario?.scans_total ?? 0;
    const scansFinished = (scenario?.scans_completed ?? 0) + (scenario?.scans_failed ?? 0);
    const scansProgress = scansTotal > 0 ? Math.round((scansFinished / scansTotal) * 100) : 0;
    const scansRunning = scansTotal > 0 && !scansCompleted;

    // =============================================================================
    // Data Fetching
    // =============================================================================

    const fetchScenario = useCallback(async () => {
        try {
            const data = await trainingScenariosApi.get(scenarioId);
            setScenario(data);
            return data;
        } catch (err) {
            console.error("Failed to fetch scenario:", err);
            return null;
        }
    }, [scenarioId]);

    const fetchExports = useCallback(async () => {
        try {
            const data = await trainingScenariosApi.listExports(scenarioId);
            setExports(data.items);
        } catch (err) {
            console.error("Failed to fetch exports:", err);
        }
    }, [scenarioId]);

    const loadData = useCallback(async () => {
        setLoading(true);
        await Promise.all([fetchScenario(), fetchExports()]);
        setLoading(false);
    }, [fetchScenario, fetchExports]);

    // =============================================================================
    // Effects
    // =============================================================================

    useEffect(() => {
        loadData();
    }, [loadData]);

    // Subscribe to SSE for real-time updates
    useEffect(() => {
        const unsubscribe = subscribe("SCENARIO.UPDATED", (data: { scenario_id?: string }) => {
            if (data.scenario_id === scenarioId) {
                fetchScenario();
                fetchExports();
            }
        });
        return () => unsubscribe();
    }, [subscribe, scenarioId, fetchScenario, fetchExports]);

    // Poll while any export is generating
    useEffect(() => {
        const hasGenerating = exports.some(e => e.status === "generating");
        if (!hasGenerating) return;

        const interval = setInterval(() => {
            fetchExports();
        }, 3000);

        return () => clearInterval(interval);
    }, [exports, fetchExports]);

    // =============================================================================
    // Handlers
    // =============================================================================

    const handleCreateNew = () => {
        router.push(`/export-config/${scenarioId}`);
    };

    const handleViewExport = async (exportId: string) => {
        try {
            const exportRecord = exports.find(e => e.id === exportId);
            const splits = await trainingScenariosApi.getExportSplits(scenarioId, exportId);
            setViewingSplits(splits);
            setViewingExport(exportRecord || null);
        } catch (err) {
            console.error("Failed to fetch export splits:", err);
            toast({ variant: "destructive", title: "Failed to load export details" });
        }
    };

    const handleDeleteExport = async (exportId: string) => {
        if (!confirm("Are you sure you want to delete this export?")) return;

        try {
            await trainingScenariosApi.deleteExport(scenarioId, exportId);
            toast({ title: "Export deleted" });
            await fetchExports();
        } catch (err) {
            console.error("Failed to delete export:", err);
            toast({ variant: "destructive", title: "Failed to delete export" });
        }
    };

    const handleBackToList = () => {
        setViewingExport(null);
        setViewingSplits([]);
    };

    // =============================================================================
    // Render States
    // =============================================================================

    if (loading) {
        return <LoadingState />;
    }

    // Not ready for export (features not done)
    if (!canGenerate) {
        return (
            <NotReadyState
                status={scenario?.status}
                isProcessing={scenario?.status === "processing"}
                buildsExtracted={scenario?.builds_features_extracted}
                buildsTotal={scenario?.builds_total}
            />
        );
    }

    // Viewing specific export details
    if (viewingExport && viewingSplits.length > 0) {
        return (
            <DatasetSummarySection
                scenarioId={scenarioId}
                exportId={viewingExport.id}
                exportName={viewingExport.name}
                splits={viewingSplits}
                onBack={handleBackToList}
            />
        );
    }

    // Default: Show exports list
    return (
        <ExportsListSection
            scenarioId={scenarioId}
            exports={exports}
            onCreateNew={handleCreateNew}
            onViewExport={handleViewExport}
            onDeleteExport={handleDeleteExport}
            scansRunning={scansRunning}
            scansProgress={scansProgress}
        />
    );
}
