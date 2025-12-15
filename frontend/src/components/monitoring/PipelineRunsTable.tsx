"use client";

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { formatDistanceToNow } from "date-fns";
import { CheckCircle, XCircle, Clock, Loader2 } from "lucide-react";

interface PipelineRun {
    id: string;
    repo_id: string;
    workflow_run_id: number;
    status: string;
    started_at: string | null;
    completed_at: string | null;
    duration_ms: number | null;
    feature_count: number;
    nodes_executed: number;
    nodes_succeeded: number;
    nodes_failed: number;
    errors: string[];
}

interface PipelineRunsTableProps {
    runs: PipelineRun[];
    total: number;
    isLoading: boolean;
}

const statusConfig: Record<
    string,
    { icon: React.ReactNode; variant: "default" | "destructive" | "secondary" | "outline" }
> = {
    completed: {
        icon: <CheckCircle className="h-3 w-3" />,
        variant: "default",
    },
    failed: {
        icon: <XCircle className="h-3 w-3" />,
        variant: "destructive",
    },
    running: {
        icon: <Loader2 className="h-3 w-3 animate-spin" />,
        variant: "secondary",
    },
    pending: {
        icon: <Clock className="h-3 w-3" />,
        variant: "outline",
    },
};

export function PipelineRunsTable({
    runs,
    total,
    isLoading,
}: PipelineRunsTableProps) {
    if (isLoading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">Pipeline Runs</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="animate-pulse space-y-2">
                        {[1, 2, 3, 4, 5].map((i) => (
                            <div key={i} className="h-10 bg-muted rounded" />
                        ))}
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">Pipeline Runs</CardTitle>
                    <Badge variant="outline">{total} total</Badge>
                </div>
            </CardHeader>
            <CardContent>
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Status</TableHead>
                            <TableHead>Workflow Run</TableHead>
                            <TableHead>Features</TableHead>
                            <TableHead>Nodes</TableHead>
                            <TableHead>Duration</TableHead>
                            <TableHead>Started</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {runs.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={6} className="text-center text-muted-foreground">
                                    No pipeline runs found
                                </TableCell>
                            </TableRow>
                        ) : (
                            runs.map((run) => {
                                const config = statusConfig[run.status] || statusConfig.pending;
                                return (
                                    <TableRow key={run.id}>
                                        <TableCell>
                                            <Badge variant={config.variant} className="gap-1">
                                                {config.icon}
                                                {run.status}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="font-mono text-xs">
                                            {run.workflow_run_id}
                                        </TableCell>
                                        <TableCell>{run.feature_count}</TableCell>
                                        <TableCell>
                                            <span className="text-green-600">{run.nodes_succeeded}</span>
                                            {run.nodes_failed > 0 && (
                                                <>
                                                    {" / "}
                                                    <span className="text-red-600">{run.nodes_failed}</span>
                                                </>
                                            )}
                                            <span className="text-muted-foreground">
                                                {" "}/ {run.nodes_executed}
                                            </span>
                                        </TableCell>
                                        <TableCell>
                                            {run.duration_ms
                                                ? `${(run.duration_ms / 1000).toFixed(1)}s`
                                                : "-"}
                                        </TableCell>
                                        <TableCell className="text-xs text-muted-foreground">
                                            {run.started_at
                                                ? formatDistanceToNow(new Date(run.started_at), {
                                                    addSuffix: true,
                                                })
                                                : "-"}
                                        </TableCell>
                                    </TableRow>
                                );
                            })
                        )}
                    </TableBody>
                </Table>
            </CardContent>
        </Card>
    );
}
