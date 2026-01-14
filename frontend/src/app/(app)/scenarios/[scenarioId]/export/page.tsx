"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Download, Loader2, Plus, RefreshCw, Trash2, AlertTriangle, Play, Eye } from "lucide-react";
import {
    trainingScenariosApi,
    TrainingExportRecord,
    TrainingScenarioRecord,
} from "@/lib/api/training-scenarios";
import { formatBytes } from "@/lib/utils";
import { toast } from "@/components/ui/use-toast";
import { useSSE } from "@/contexts/sse-context";

// =============================================================================
// Status Badge Component
// =============================================================================

function ExportStatusBadge({ status }: { status: string }) {
    const variants: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
        queued: "outline",
        generating: "secondary",
        completed: "default",
        failed: "destructive",
    };
    const labels: Record<string, string> = {
        queued: "Queued",
        generating: "Generating...",
        completed: "Completed",
        failed: "Failed",
    };
    return (
        <Badge variant={variants[status] || "outline"}>
            {status === "generating" && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
            {labels[status] || status}
        </Badge>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export default function ScenarioExportPage() {
    const params = useParams<{ scenarioId: string }>();
    const router = useRouter();
    const scenarioId = params.scenarioId;
    const { subscribe } = useSSE();

    const [scenario, setScenario] = useState<TrainingScenarioRecord | null>(null);
    const [exports, setExports] = useState<TrainingExportRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [generatingId, setGeneratingId] = useState<string | null>(null);

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

    useEffect(() => {
        loadData();
    }, [loadData]);

    // Subscribe to SSE for real-time updates
    useEffect(() => {
        const unsubscribe = subscribe("SCENARIO_UPDATE", (data: { scenario_id?: string }) => {
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

    const handleDelete = async (exportId: string) => {
        setDeletingId(exportId);
        try {
            await trainingScenariosApi.deleteExport(scenarioId, exportId);
            toast({ title: "Export deleted" });
            await fetchExports();
        } catch (err) {
            console.error("Failed to delete export:", err);
            toast({ variant: "destructive", title: "Failed to delete export" });
        } finally {
            setDeletingId(null);
        }
    };

    const handleGenerate = async (exportId: string) => {
        setGeneratingId(exportId);
        try {
            await trainingScenariosApi.generateExport(scenarioId, exportId);
            toast({ title: "Dataset generation started" });
            await fetchExports();
        } catch (err) {
            console.error("Failed to generate:", err);
            toast({ variant: "destructive", title: "Failed to start generation" });
        } finally {
            setGeneratingId(null);
        }
    };

    const canCreateExport = scenario?.status === "processed" || scenario?.status === "completed";

    if (loading) {
        return (
            <div className="flex min-h-[400px] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    // Not ready for export
    if (!canCreateExport) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>Dataset Exports</CardTitle>
                    <CardDescription>Complete processing phase first</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="p-8 border rounded-lg bg-muted/50 flex flex-col items-center gap-4">
                        <AlertTriangle className="h-12 w-12 text-amber-500" />
                        <p className="text-muted-foreground text-center">
                            Dataset export requires the processing phase to be completed.
                        </p>
                        <Badge variant="outline" className="text-sm">
                            Current status: {scenario?.status}
                        </Badge>
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                        <CardTitle>Dataset Exports</CardTitle>
                        <CardDescription>
                            Create and manage dataset exports with different configurations
                        </CardDescription>
                    </div>
                    <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={() => fetchExports()}>
                            <RefreshCw className="mr-2 h-4 w-4" />
                            Refresh
                        </Button>
                        <Button onClick={() => router.push(`/scenarios/${scenarioId}/export/create`)}>
                            <Plus className="mr-2 h-4 w-4" />
                            Create New Export
                        </Button>
                    </div>
                </CardHeader>
            </Card>

            {/* Export List */}
            {exports.length === 0 ? (
                <Card>
                    <CardContent className="p-12">
                        <div className="flex flex-col items-center gap-4 text-center">
                            <div className="p-4 rounded-full bg-muted">
                                <Download className="h-8 w-8 text-muted-foreground" />
                            </div>
                            <div>
                                <h3 className="font-semibold">No Exports Yet</h3>
                                <p className="text-sm text-muted-foreground mt-1">
                                    Create your first dataset export with custom splitting and preprocessing configurations.
                                </p>
                            </div>
                            <Button onClick={() => router.push(`/scenarios/${scenarioId}/export/create`)}>
                                <Plus className="mr-2 h-4 w-4" />
                                Create New Export
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            ) : (
                <Card>
                    <CardContent className="p-0">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Name</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead className="text-right">Train</TableHead>
                                    <TableHead className="text-right">Val</TableHead>
                                    <TableHead className="text-right">Test</TableHead>
                                    <TableHead className="text-right">Features</TableHead>
                                    <TableHead>Created</TableHead>
                                    <TableHead className="text-right">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {exports.map((exp) => (
                                    <TableRow key={exp.id}>
                                        <TableCell className="font-medium">
                                            {exp.name || `Export ${exp.id.slice(0, 8)}`}
                                        </TableCell>
                                        <TableCell>
                                            <ExportStatusBadge status={exp.status} />
                                            {exp.error_message && (
                                                <p className="text-xs text-destructive mt-1 truncate max-w-[200px]">
                                                    {exp.error_message}
                                                </p>
                                            )}
                                        </TableCell>
                                        <TableCell className="text-right">
                                            {exp.train_count > 0 ? exp.train_count.toLocaleString() : "-"}
                                        </TableCell>
                                        <TableCell className="text-right">
                                            {exp.val_count > 0 ? exp.val_count.toLocaleString() : "-"}
                                        </TableCell>
                                        <TableCell className="text-right">
                                            {exp.test_count > 0 ? exp.test_count.toLocaleString() : "-"}
                                        </TableCell>
                                        <TableCell className="text-right">
                                            {exp.feature_count > 0 ? exp.feature_count : "-"}
                                        </TableCell>
                                        <TableCell className="text-muted-foreground text-sm">
                                            {new Date(exp.created_at).toLocaleDateString()}
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <div className="flex gap-1 justify-end">
                                                {/* Generate button for queued exports */}
                                                {exp.status === "queued" && (
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        onClick={() => handleGenerate(exp.id)}
                                                        disabled={generatingId === exp.id}
                                                    >
                                                        {generatingId === exp.id ? (
                                                            <Loader2 className="h-4 w-4 animate-spin" />
                                                        ) : (
                                                            <Play className="h-4 w-4" />
                                                        )}
                                                    </Button>
                                                )}

                                                {/* Download button for completed exports */}
                                                {exp.status === "completed" && (
                                                    <Button size="sm" variant="outline" asChild>
                                                        <a href={`/api/training-scenarios/${scenarioId}/exports/${exp.id}/download-all`}>
                                                            <Download className="h-4 w-4" />
                                                        </a>
                                                    </Button>
                                                )}

                                                {/* Delete button */}
                                                <AlertDialog>
                                                    <AlertDialogTrigger asChild>
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            disabled={deletingId === exp.id || exp.status === "generating"}
                                                        >
                                                            {deletingId === exp.id ? (
                                                                <Loader2 className="h-4 w-4 animate-spin" />
                                                            ) : (
                                                                <Trash2 className="h-4 w-4 text-destructive" />
                                                            )}
                                                        </Button>
                                                    </AlertDialogTrigger>
                                                    <AlertDialogContent>
                                                        <AlertDialogHeader>
                                                            <AlertDialogTitle>Delete Export</AlertDialogTitle>
                                                            <AlertDialogDescription>
                                                                Are you sure you want to delete this export? This action cannot be undone.
                                                            </AlertDialogDescription>
                                                        </AlertDialogHeader>
                                                        <AlertDialogFooter>
                                                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                                                            <AlertDialogAction onClick={() => handleDelete(exp.id)}>
                                                                Delete
                                                            </AlertDialogAction>
                                                        </AlertDialogFooter>
                                                    </AlertDialogContent>
                                                </AlertDialog>
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
