"use client";

import { AlertCircle, Loader2, RefreshCw, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
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
    failedCount: number;
    lastSyncedAt?: string | null;
    status: string;
    onSync: () => void;
    onRetryFailed: () => void;
    syncLoading: boolean;
    retryLoading: boolean;
}

export function CollectionCard({
    fetchedCount,
    ingestedCount,
    totalCount,
    failedCount,
    lastSyncedAt,
    status,
    onSync,
    onRetryFailed,
    syncLoading,
    retryLoading,
}: CollectionCardProps) {
    const isCollecting = ["queued", "fetching", "ingesting"].includes(status.toLowerCase());
    const hasPartial = failedCount > 0;

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
                    <StatBox
                        label="Failed"
                        value={failedCount}
                        variant={failedCount > 0 ? "error" : "default"}
                    />
                    <StatBox
                        label="Last Sync"
                        value={lastSyncedAt ? formatTimestamp(lastSyncedAt) : "—"}
                    />
                </div>

                {/* Warning for partial ingestion */}
                {hasPartial && !isCollecting && (
                    <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900">
                        <AlertCircle className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
                        <span className="text-sm text-amber-700 dark:text-amber-400">
                            {failedCount} build(s) have incomplete resources. Features may contain N/A values.
                        </span>
                    </div>
                )}

                {/* Actions */}
                <div className="flex gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onSync}
                        disabled={syncLoading || isCollecting}
                    >
                        {syncLoading ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                            <RefreshCw className="mr-2 h-4 w-4" />
                        )}
                        Sync New Builds
                    </Button>
                    {failedCount > 0 && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={onRetryFailed}
                            disabled={retryLoading || isCollecting}
                        >
                            {retryLoading ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                                <RotateCcw className="mr-2 h-4 w-4" />
                            )}
                            Retry Failed
                        </Button>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
