"use client";

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { formatDistanceToNow } from "date-fns";
import { Download, Search, FlaskConical } from "lucide-react";

interface ExportJob {
    id: string;
    status: string;
    format: string;
    total_rows: number;
    processed_rows: number;
    created_at: string | null;
}

interface ScanJob {
    id: string;
    dataset_id: string;
    tool_type: string;
    status: string;
    total_commits: number;
    scanned_commits: number;
    created_at: string | null;
}

interface EnrichmentJob {
    id: string;
    dataset_id: string;
    status: string;
    total_rows: number;
    processed_rows: number;
    created_at: string | null;
}

interface BackgroundJobsData {
    exports: ExportJob[];
    scans: ScanJob[];
    enrichments: EnrichmentJob[];
    summary: {
        active_exports: number;
        active_scans: number;
        active_enrichments: number;
    };
}

interface BackgroundJobsTableProps {
    jobs: BackgroundJobsData | null;
    isLoading: boolean;
}

function JobProgress({ current, total }: { current: number; total: number }) {
    const percent = total > 0 ? Math.round((current / total) * 100) : 0;
    return (
        <div className="flex items-center gap-2">
            <Progress value={percent} className="w-16 h-2" />
            <span className="text-xs text-muted-foreground">{percent}%</span>
        </div>
    );
}

export function BackgroundJobsTable({
    jobs,
    isLoading,
}: BackgroundJobsTableProps) {
    if (isLoading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">Background Jobs</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="animate-pulse space-y-2">
                        {[1, 2, 3].map((i) => (
                            <div key={i} className="h-12 bg-muted rounded" />
                        ))}
                    </div>
                </CardContent>
            </Card>
        );
    }

    if (!jobs) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">Background Jobs</CardTitle>
                </CardHeader>
                <CardContent>
                    <p className="text-muted-foreground text-center">
                        Failed to load jobs
                    </p>
                </CardContent>
            </Card>
        );
    }

    const totalActive =
        jobs.summary.active_exports +
        jobs.summary.active_scans +
        jobs.summary.active_enrichments;

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">Background Jobs</CardTitle>
                    <Badge variant={totalActive > 0 ? "default" : "secondary"}>
                        {totalActive} active
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Exports */}
                <div>
                    <div className="flex items-center gap-2 mb-2">
                        <Download className="h-4 w-4" />
                        <span className="font-medium text-sm">Exports</span>
                        <Badge variant="outline" className="text-xs">
                            {jobs.exports.length}
                        </Badge>
                    </div>
                    {jobs.exports.length === 0 ? (
                        <p className="text-xs text-muted-foreground pl-6">No active exports</p>
                    ) : (
                        <div className="space-y-2 pl-6">
                            {jobs.exports.map((job) => (
                                <div
                                    key={job.id}
                                    className="flex items-center justify-between text-sm"
                                >
                                    <div className="flex items-center gap-2">
                                        <Badge variant="secondary" className="text-xs">
                                            {job.format.toUpperCase()}
                                        </Badge>
                                        <span className="text-muted-foreground">
                                            {job.total_rows} rows
                                        </span>
                                    </div>
                                    <JobProgress
                                        current={job.processed_rows}
                                        total={job.total_rows}
                                    />
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Scans */}
                <div>
                    <div className="flex items-center gap-2 mb-2">
                        <Search className="h-4 w-4" />
                        <span className="font-medium text-sm">Scans</span>
                        <Badge variant="outline" className="text-xs">
                            {jobs.scans.length}
                        </Badge>
                    </div>
                    {jobs.scans.length === 0 ? (
                        <p className="text-xs text-muted-foreground pl-6">No active scans</p>
                    ) : (
                        <div className="space-y-2 pl-6">
                            {jobs.scans.map((scan) => (
                                <div
                                    key={scan.id}
                                    className="flex items-center justify-between text-sm"
                                >
                                    <div className="flex items-center gap-2">
                                        <Badge variant="secondary" className="text-xs">
                                            {scan.tool_type}
                                        </Badge>
                                        <span className="text-muted-foreground">
                                            {scan.total_commits} commits
                                        </span>
                                    </div>
                                    <JobProgress
                                        current={scan.scanned_commits}
                                        total={scan.total_commits}
                                    />
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Enrichments */}
                <div>
                    <div className="flex items-center gap-2 mb-2">
                        <FlaskConical className="h-4 w-4" />
                        <span className="font-medium text-sm">Enrichments</span>
                        <Badge variant="outline" className="text-xs">
                            {jobs.enrichments.length}
                        </Badge>
                    </div>
                    {jobs.enrichments.length === 0 ? (
                        <p className="text-xs text-muted-foreground pl-6">
                            No active enrichments
                        </p>
                    ) : (
                        <div className="space-y-2 pl-6">
                            {jobs.enrichments.map((job) => (
                                <div
                                    key={job.id}
                                    className="flex items-center justify-between text-sm"
                                >
                                    <div className="flex items-center gap-2">
                                        <span className="text-muted-foreground">
                                            {job.total_rows} rows
                                        </span>
                                    </div>
                                    <JobProgress
                                        current={job.processed_rows}
                                        total={job.total_rows}
                                    />
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
