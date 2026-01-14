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
import { Download, RefreshCw } from "lucide-react";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { TrainingDatasetSplitRecord } from "@/lib/api/training-scenarios";
import { formatBytes } from "@/lib/utils";

interface DatasetSummarySectionProps {
    scenarioId: string;
    splits: TrainingDatasetSplitRecord[];
    onRegenerate: () => void;
}

export function DatasetSummarySection({
    scenarioId,
    splits,
    onRegenerate,
}: DatasetSummarySectionProps) {
    const totalRecords = splits.reduce((sum, s) => sum + s.record_count, 0);
    const totalSize = splits.reduce((sum, s) => sum + s.file_size_bytes, 0);

    return (
        <div className="space-y-6">
            {/* Summary Card */}
            <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                        <CardTitle>Dataset Summary</CardTitle>
                        <CardDescription>Generated splits ready for download</CardDescription>
                    </div>
                    <div className="flex gap-2">
                        <Button variant="outline" size="sm" asChild>
                            <a
                                href={`/api/training-scenarios/${scenarioId}/splits/download-all?file_format=parquet`}
                            >
                                <Download className="mr-2 h-4 w-4" />
                                All (Parquet)
                            </a>
                        </Button>
                        <Button variant="outline" size="sm" asChild>
                            <a
                                href={`/api/training-scenarios/${scenarioId}/splits/download-all?file_format=csv`}
                            >
                                <Download className="mr-2 h-4 w-4" />
                                All (CSV)
                            </a>
                        </Button>
                        <Button variant="outline" size="sm" onClick={onRegenerate}>
                            <RefreshCw className="mr-2 h-4 w-4" />
                            Regenerate
                        </Button>
                    </div>
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
                                    <TableCell className="text-right">
                                        <Button size="sm" variant="outline" asChild>
                                            <a
                                                href={`/api/training-scenarios/${scenarioId}/splits/${split.id}/download`}
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
        </div>
    );
}
