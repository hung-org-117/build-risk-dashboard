"use client";

import { useParams } from "next/navigation";
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
import { Download, FileDown, Loader2 } from "lucide-react";
import {
    trainingScenariosApi,
    TrainingDatasetSplitRecord,
} from "@/lib/api/training-scenarios";
import { formatBytes } from "@/lib/utils";


export default function ScenarioExportPage() {
    const params = useParams<{ scenarioId: string }>();
    const scenarioId = params.scenarioId;

    const [splits, setSplits] = useState<TrainingDatasetSplitRecord[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchSplits = useCallback(async () => {
        try {
            const data = await trainingScenariosApi.getSplits(scenarioId);
            setSplits(data);
        } catch (err) {
            console.error("Failed to fetch splits:", err);
        } finally {
            setLoading(false);
        }
    }, [scenarioId]);

    useEffect(() => {
        fetchSplits();
    }, [fetchSplits]);

    if (loading) {
        return (
            <div className="flex min-h-[400px] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (splits.length === 0) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>Export Dataset</CardTitle>
                    <CardDescription>No splits generated yet</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="p-8 border rounded-lg bg-muted/50 flex flex-col items-center justify-center gap-4">
                        <FileDown className="h-12 w-12 text-muted-foreground" />
                        <p className="text-muted-foreground text-center">
                            Dataset splits will be available here after the Generate Dataset phase completes.
                        </p>
                    </div>
                </CardContent>
            </Card>
        );
    }

    // Calculate totals
    const totalRecords = splits.reduce((sum, s) => sum + s.record_count, 0);
    const totalSize = splits.reduce((sum, s) => sum + s.file_size_bytes, 0);

    return (
        <div className="space-y-6">
            {/* Summary Card */}
            <Card>
                <CardHeader>
                    <CardTitle>Dataset Summary</CardTitle>
                    <CardDescription>
                        Generated splits ready for download
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="grid gap-4 md:grid-cols-4">
                        <div className="p-4 border rounded-lg">
                            <p className="text-sm text-muted-foreground">Total Splits</p>
                            <p className="text-2xl font-bold">{splits.length}</p>
                        </div>
                        <div className="p-4 border rounded-lg">
                            <p className="text-sm text-muted-foreground">Total Records</p>
                            <p className="text-2xl font-bold">{totalRecords.toLocaleString()}</p>
                        </div>
                        <div className="p-4 border rounded-lg">
                            <p className="text-sm text-muted-foreground">Features</p>
                            <p className="text-2xl font-bold">{splits[0]?.feature_count || 0}</p>
                        </div>
                        <div className="p-4 border rounded-lg">
                            <p className="text-sm text-muted-foreground">Total Size</p>
                            <p className="text-2xl font-bold">{formatBytes(totalSize)}</p>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Splits Table */}
            <Card>
                <CardHeader>
                    <CardTitle>Split Files</CardTitle>
                </CardHeader>
                <CardContent>
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Split</TableHead>
                                <TableHead>Records</TableHead>
                                <TableHead>Features</TableHead>
                                <TableHead>Size</TableHead>
                                <TableHead>Format</TableHead>
                                <TableHead>Generated</TableHead>
                                <TableHead className="text-right">Action</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {splits.map((split) => (
                                <TableRow key={split.id}>
                                    <TableCell>
                                        <Badge variant="outline" className="capitalize">
                                            {split.split_type}
                                        </Badge>
                                    </TableCell>
                                    <TableCell>{split.record_count.toLocaleString()}</TableCell>
                                    <TableCell>{split.feature_count}</TableCell>
                                    <TableCell>{formatBytes(split.file_size_bytes)}</TableCell>
                                    <TableCell>
                                        <Badge variant="secondary">{split.file_format.toUpperCase()}</Badge>
                                    </TableCell>
                                    <TableCell className="text-sm text-muted-foreground">
                                        {split.generated_at
                                            ? new Date(split.generated_at).toLocaleString()
                                            : "-"}
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <Button size="sm" variant="outline" asChild>
                                            <a
                                                href={split.file_path}
                                                download={`${split.split_type}.${split.file_format}`}
                                            >
                                                <Download className="mr-2 h-4 w-4" />
                                                Download
                                            </a>
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>

            {/* Class Distribution */}
            {splits.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>Class Distribution by Split</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="grid gap-4 md:grid-cols-3">
                            {splits.map((split) => (
                                <div key={split.id} className="p-4 border rounded-lg">
                                    <p className="font-medium capitalize mb-2">{split.split_type}</p>
                                    <div className="space-y-1 text-sm">
                                        {Object.entries(split.class_distribution || {}).map(([cls, count]) => (
                                            <div key={cls} className="flex justify-between">
                                                <span className="text-muted-foreground">{cls}:</span>
                                                <span className="font-medium">{count}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
