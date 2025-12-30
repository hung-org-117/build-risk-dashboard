"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, ChevronDown, ChevronUp, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { reposApi } from "@/lib/api";

interface FailedBuild {
    id: string;
    ci_run_id: string;
    commit_sha: string;
    ingestion_error?: string;
    resource_errors: Record<string, string>;
    fetched_at?: string;
}

interface FailedBuildsPanelProps {
    repoId: string;
    failedCount: number;
    onRetry?: () => void;
    isRetrying?: boolean;
}

export function FailedBuildsPanel({
    repoId,
    failedCount,
    onRetry,
    isRetrying,
}: FailedBuildsPanelProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [builds, setBuilds] = useState<FailedBuild[]>([]);
    const [loading, setLoading] = useState(false);
    const [loaded, setLoaded] = useState(false);

    const loadFailedBuilds = useCallback(async () => {
        if (loaded) return;
        setLoading(true);
        try {
            const data = await reposApi.getFailedImportBuilds(repoId, 20);
            setBuilds(data.failed_builds);
            setLoaded(true);
        } catch (err) {
            console.error("Failed to load failed builds:", err);
        } finally {
            setLoading(false);
        }
    }, [repoId, loaded]);

    useEffect(() => {
        if (isOpen && !loaded) {
            loadFailedBuilds();
        }
    }, [isOpen, loaded, loadFailedBuilds]);

    if (failedCount === 0) return null;

    return (
        <Card className="border-red-200 bg-red-50/50 dark:border-red-800 dark:bg-red-950/20">
            <Collapsible open={isOpen} onOpenChange={setIsOpen}>
                <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <AlertCircle className="h-5 w-5 text-red-500" />
                            <CardTitle className="text-base text-red-700 dark:text-red-400">
                                {failedCount} Failed Imports
                            </CardTitle>
                        </div>
                        <div className="flex items-center gap-2">
                            {onRetry && (
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={onRetry}
                                    disabled={isRetrying}
                                    className="border-red-300 text-red-600 hover:bg-red-100"
                                >
                                    <RefreshCw className={`h-4 w-4 mr-1 ${isRetrying ? "animate-spin" : ""}`} />
                                    Retry Failed
                                </Button>
                            )}
                            <CollapsibleTrigger asChild>
                                <Button variant="ghost" size="sm">
                                    {isOpen ? (
                                        <ChevronUp className="h-4 w-4" />
                                    ) : (
                                        <ChevronDown className="h-4 w-4" />
                                    )}
                                </Button>
                            </CollapsibleTrigger>
                        </div>
                    </div>
                    <CardDescription className="text-red-600/80 dark:text-red-400/80">
                        Click to view error details for failed imports
                    </CardDescription>
                </CardHeader>
                <CollapsibleContent>
                    <CardContent className="pt-0">
                        {loading ? (
                            <div className="flex items-center justify-center py-4">
                                <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
                            </div>
                        ) : builds.length === 0 ? (
                            <p className="text-sm text-muted-foreground py-2">
                                No failed builds found.
                            </p>
                        ) : (
                            <div className="space-y-3 max-h-64 overflow-y-auto">
                                {builds.map((build) => (
                                    <div
                                        key={build.id}
                                        className="rounded-lg border border-red-200 bg-white p-3 dark:border-red-800 dark:bg-slate-900"
                                    >
                                        <div className="flex items-center gap-2 mb-2">
                                            <Badge variant="outline" className="font-mono text-xs">
                                                {build.commit_sha}
                                            </Badge>
                                            <span className="text-xs text-muted-foreground">
                                                #{build.ci_run_id}
                                            </span>
                                        </div>
                                        {build.ingestion_error && (
                                            <p className="text-sm text-red-600 dark:text-red-400 mb-1">
                                                {build.ingestion_error}
                                            </p>
                                        )}
                                        {Object.entries(build.resource_errors).length > 0 && (
                                            <div className="space-y-1">
                                                {Object.entries(build.resource_errors).map(
                                                    ([resource, error]) => (
                                                        <div
                                                            key={resource}
                                                            className="text-xs flex gap-2"
                                                        >
                                                            <Badge
                                                                variant="secondary"
                                                                className="text-[10px] px-1"
                                                            >
                                                                {resource}
                                                            </Badge>
                                                            <span className="text-red-500">
                                                                {error}
                                                            </span>
                                                        </div>
                                                    )
                                                )}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </CollapsibleContent>
            </Collapsible>
        </Card>
    );
}
