"use client";

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
import { Download, Plus, Loader2, Trash2, Eye } from "lucide-react";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { TrainingExportRecord } from "@/lib/api/training-scenarios";
import { formatDistanceToNow } from "date-fns";

interface ExportsListSectionProps {
    scenarioId: string;
    exports: TrainingExportRecord[];
    onCreateNew: () => void;
    onViewExport: (exportId: string) => void;
    onDeleteExport: (exportId: string) => void;
    scansRunning?: boolean;
    scansProgress?: number;
}

function getStatusBadge(status: string) {
    switch (status) {
        case "completed":
            return <Badge className="bg-green-500">Completed</Badge>;
        case "generating":
            return (
                <Badge className="bg-blue-500">
                    <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                    Generating
                </Badge>
            );
        case "failed":
            return <Badge variant="destructive">Failed</Badge>;
        case "queued":
            return <Badge variant="secondary">Queued</Badge>;
        default:
            return <Badge variant="outline">{status}</Badge>;
    }
}

export function ExportsListSection({
    scenarioId,
    exports,
    onCreateNew,
    onViewExport,
    onDeleteExport,
    scansRunning = false,
    scansProgress = 0,
}: ExportsListSectionProps) {
    const completedExports = exports.filter(e => e.status === "completed");
    const hasGenerating = exports.some(e => e.status === "generating");

    return (
        <div className="space-y-6">
            {/* Header */}
            <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                        <CardTitle>Dataset Exports</CardTitle>
                        <CardDescription>
                            {exports.length === 0
                                ? "No exports yet. Create one to generate train/val/test splits."
                                : `${completedExports.length} of ${exports.length} exports completed`
                            }
                        </CardDescription>
                    </div>
                    <Button onClick={onCreateNew} disabled={hasGenerating} className="bg-green-600 hover:bg-green-700 text-white">
                        <Plus className="mr-2 h-4 w-4" />
                        Create New Export
                    </Button>
                </CardHeader>

                {/* Scan Warning if running */}
                {scansRunning && (
                    <CardContent className="pt-0">
                        <div className="p-3 bg-amber-50 dark:bg-amber-950/50 rounded-lg border border-amber-200 dark:border-amber-800">
                            <p className="text-sm text-amber-700 dark:text-amber-300">
                                <Loader2 className="inline mr-2 h-4 w-4 animate-spin" />
                                Scans still running ({scansProgress}% complete).
                                Exports will include available scan metrics.
                            </p>
                        </div>
                    </CardContent>
                )}
            </Card>

            {/* Empty State */}
            {exports.length === 0 && (
                <Card>
                    <CardContent className="py-12">
                        <div className="flex flex-col items-center gap-4 text-center">
                            <div className="p-4 rounded-full bg-muted">
                                <Download className="h-8 w-8 text-muted-foreground" />
                            </div>
                            <div>
                                <h3 className="font-semibold">No Exports Yet</h3>
                                <p className="text-sm text-muted-foreground mt-1">
                                    Create your first export to generate train/val/test dataset splits.
                                </p>
                            </div>
                            <Button onClick={onCreateNew} className="bg-green-600 hover:bg-green-700 text-white">
                                <Plus className="mr-2 h-4 w-4" />
                                Create Export
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Exports Table */}
            {exports.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>Export History</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Name</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead>Strategy</TableHead>
                                    <TableHead>Records</TableHead>
                                    <TableHead>Created</TableHead>
                                    <TableHead className="text-right">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {exports.map((exp) => (
                                    <TableRow key={exp.id}>
                                        <TableCell className="font-medium">{exp.name}</TableCell>
                                        <TableCell>{getStatusBadge(exp.status)}</TableCell>
                                        <TableCell>
                                            <Badge variant="outline">
                                                {exp.splitting_config?.strategy || "N/A"}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            {exp.status === "completed"
                                                ? `${(exp.train_count + exp.val_count + exp.test_count).toLocaleString()}`
                                                : "—"
                                            }
                                        </TableCell>
                                        <TableCell className="text-muted-foreground">
                                            {exp.created_at
                                                ? formatDistanceToNow(new Date(exp.created_at), { addSuffix: true })
                                                : "—"
                                            }
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <div className="flex justify-end gap-2">
                                                {exp.status === "completed" && (
                                                    <>
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => onViewExport(exp.id)}
                                                        >
                                                            <Eye className="mr-1 h-4 w-4" />
                                                            View
                                                        </Button>
                                                        <Button size="sm" variant="outline" asChild>
                                                            <a href={`/api/training-scenarios/${scenarioId}/exports/${exp.id}/download-all`}>
                                                                <Download className="mr-1 h-4 w-4" />
                                                                Download
                                                            </a>
                                                        </Button>
                                                    </>
                                                )}
                                                {exp.status === "failed" && (
                                                    <Badge variant="destructive" className="text-xs">
                                                        {exp.error_message || "Generation failed"}
                                                    </Badge>
                                                )}
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    className="text-destructive hover:text-destructive"
                                                    onClick={() => onDeleteExport(exp.id)}
                                                    disabled={exp.status === "generating"}
                                                >
                                                    <Trash2 className="h-4 w-4" />
                                                </Button>
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
