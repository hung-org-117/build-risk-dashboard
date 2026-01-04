"use client";

import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { formatTimestamp } from "@/lib/utils";

import { StatBox } from "./StatBox";

interface CollectionCardProps {
    fetchedCount: number;
    ingestedCount: number;
    totalCount: number;
    missingResourceCount: number;
    failedCount: number;
    lastSyncedAt?: string | null;
    status: string;
    // Checkpoint info
    hasCheckpoint?: boolean;
    checkpointAt?: string | null;
    acceptedFailedCount?: number;
}

export function CollectionCard({
    fetchedCount,
    ingestedCount,
    totalCount,
    missingResourceCount,
    failedCount,
    lastSyncedAt,
    status,
    hasCheckpoint = false,
    checkpointAt,
    acceptedFailedCount = 0,
}: CollectionCardProps) {
    const isCollecting = ["queued", "fetching", "ingesting"].includes(status.toLowerCase());
    const hasMissingResources = missingResourceCount > 0;
    const hasActualFailures = failedCount > 0;

    return (
        <Card>
            <CardHeader className="pb-4">
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="text-lg flex items-center gap-2">
                            Data Collection
                            {isCollecting && (
                                <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                            )}
                        </CardTitle>
                        <CardDescription>
                            Fetch builds and prepare resources for processing
                        </CardDescription>
                    </div>
                    {lastSyncedAt && (
                        <span className="text-xs text-muted-foreground">
                            Last sync: {formatTimestamp(lastSyncedAt)}
                        </span>
                    )}
                </div>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Stats Row */}
                <div className="flex justify-center gap-4">
                    <StatBox
                        label="Fetched"
                        value={fetchedCount}
                        variant={fetchedCount > 0 ? "success" : "default"}
                    />
                    <StatBox
                        label="Ingested"
                        value={`${ingestedCount}/${totalCount}`}
                        variant={ingestedCount === totalCount && totalCount > 0 ? "success" : "default"}
                    />
                    {missingResourceCount > 0 && (
                        <StatBox
                            label="Missing"
                            value={missingResourceCount}
                            variant="warning"
                            subValue="logs expired"
                        />
                    )}
                    <StatBox
                        label="Failed"
                        value={failedCount}
                        variant={failedCount > 0 ? "error" : "default"}
                        subValue="retryable"
                    />
                </div>

                {/* Checkpoint info */}
                {hasCheckpoint && acceptedFailedCount > 0 && (
                    <div className="flex items-start gap-2 p-3 rounded-lg bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800">
                        <CheckCircle2 className="h-4 w-4 text-slate-500 mt-0.5 flex-shrink-0" />
                        <div className="text-sm text-slate-600 dark:text-slate-400">
                            <strong>{acceptedFailedCount}</strong> failed builds accepted from previous batch
                            {checkpointAt && (
                                <span className="text-xs text-muted-foreground ml-2">
                                    (checkpoint: {formatTimestamp(checkpointAt)})
                                </span>
                            )}
                        </div>
                    </div>
                )}

                {/* Warning for missing resources */}
                {hasMissingResources && !isCollecting && (
                    <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900">
                        <AlertCircle className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
                        <span className="text-sm text-amber-700 dark:text-amber-400">
                            {missingResourceCount} build(s) have expired logs or missing commits (cannot be retried).
                        </span>
                    </div>
                )}

                {/* Warning for actual failures */}
                {hasActualFailures && !isCollecting && (
                    <div className="flex items-start gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900">
                        <AlertCircle className="h-4 w-4 text-red-600 mt-0.5 flex-shrink-0" />
                        <span className="text-sm text-red-700 dark:text-red-400">
                            {failedCount} build(s) failed with errors.
                        </span>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
