"use client";

import { Badge } from "@/components/ui/badge";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { DatasetRecord } from "@/types";
import { CheckCircle2, Clock, Database, FileSpreadsheet, MapPin } from "lucide-react";

interface DatasetOverviewTabProps {
    dataset: DatasetRecord;
    onRefresh: () => void;
}

export function DatasetOverviewTab({ dataset, onRefresh }: DatasetOverviewTabProps) {
    const hasMapping = dataset.mapped_fields?.build_id && dataset.mapped_fields?.repo_name;
    const totalFeatures = dataset.selected_features?.length || 0;
    const sonarFeatures = dataset.selected_features?.filter(f => f.startsWith("sonar_")).length || 0;
    const regularFeatures = totalFeatures - sonarFeatures;

    return (
        <div className="space-y-6">
            {/* Statistics Cards */}
            <div className="grid gap-4 md:grid-cols-4">
                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription>Total Rows</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-center gap-2">
                            <FileSpreadsheet className="h-5 w-5 text-muted-foreground" />
                            <span className="text-2xl font-bold">{dataset.rows.toLocaleString()}</span>
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription>Selected Features</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-center gap-2">
                            <Database className="h-5 w-5 text-muted-foreground" />
                            <span className="text-2xl font-bold">{totalFeatures}</span>
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground">
                            {regularFeatures} regular, {sonarFeatures} sonar
                        </p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription>Columns</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-center gap-2">
                            <span className="text-2xl font-bold">{dataset.columns?.length || 0}</span>
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription>Mapping Status</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-center gap-2">
                            {hasMapping ? (
                                <>
                                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                                    <span className="font-medium text-green-600">Configured</span>
                                </>
                            ) : (
                                <>
                                    <Clock className="h-5 w-5 text-amber-500" />
                                    <span className="font-medium text-amber-600">Pending</span>
                                </>
                            )}
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Column Mapping */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <MapPin className="h-5 w-5" /> Column Mapping
                    </CardTitle>
                    <CardDescription>Required field mappings for enrichment</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="grid gap-3 md:grid-cols-3">
                        <div className="flex items-center justify-between rounded-lg bg-slate-50 px-4 py-3 dark:bg-slate-800">
                            <span className="text-sm text-muted-foreground">Build ID</span>
                            <span className="font-medium">
                                {dataset.mapped_fields?.build_id || (
                                    <span className="text-amber-600">Not mapped</span>
                                )}
                            </span>
                        </div>
                        <div className="flex items-center justify-between rounded-lg bg-slate-50 px-4 py-3 dark:bg-slate-800">
                            <span className="text-sm text-muted-foreground">Repo Name</span>
                            <span className="font-medium">
                                {dataset.mapped_fields?.repo_name || (
                                    <span className="text-amber-600">Not mapped</span>
                                )}
                            </span>
                        </div>
                        <div className="flex items-center justify-between rounded-lg bg-slate-50 px-4 py-3 dark:bg-slate-800">
                            <span className="text-sm text-muted-foreground">Commit SHA</span>
                            <span className="font-medium">
                                {dataset.mapped_fields?.commit_sha || (
                                    <span className="text-slate-400">Optional</span>
                                )}
                            </span>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Data Preview */}
            <Card>
                <CardHeader>
                    <CardTitle>Data Preview</CardTitle>
                    <CardDescription>First 5 rows of the dataset</CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                    <div className="max-h-80 overflow-auto">
                        <table className="min-w-full text-sm">
                            <thead className="sticky top-0 bg-slate-50 dark:bg-slate-800">
                                <tr>
                                    {dataset.columns?.slice(0, 8).map((col) => (
                                        <th key={col} className="px-4 py-2 text-left font-medium">
                                            {col}
                                        </th>
                                    ))}
                                    {(dataset.columns?.length || 0) > 8 && (
                                        <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                                            +{(dataset.columns?.length || 0) - 8} more
                                        </th>
                                    )}
                                </tr>
                            </thead>
                            <tbody className="divide-y">
                                {dataset.preview?.slice(0, 5).map((row, idx) => (
                                    <tr key={idx}>
                                        {dataset.columns?.slice(0, 8).map((col) => (
                                            <td key={col} className="px-4 py-2 text-muted-foreground">
                                                {String(row[col] || "—").slice(0, 40)}
                                            </td>
                                        ))}
                                        {(dataset.columns?.length || 0) > 8 && (
                                            <td className="px-4 py-2 text-muted-foreground">...</td>
                                        )}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
