"use client";

import { useParams, usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
    ArrowLeft,
    ExternalLink,
    Globe,
    Loader2,
    Lock,
} from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useSSE } from "@/contexts/sse-context";
import { useToast } from "@/components/ui/use-toast";
import { buildApi, reposApi } from "@/lib/api";
import type { Build, RepoDetail } from "@/types";
import { RepoContext, type ImportProgress, type RepoContextType } from "@/components/repositories/RepoContext";

export default function RepoLayout({ children }: { children: React.ReactNode }) {
    const params = useParams();
    const router = useRouter();
    const pathname = usePathname();
    const repoId = params.repoId as string;

    const [repo, setRepo] = useState<RepoDetail | null>(null);
    const [progress, setProgress] = useState<ImportProgress | null>(null);
    const [builds, setBuilds] = useState<Build[]>([]);
    const [loading, setLoading] = useState(true);

    // Action loading states
    const [startProcessingLoading, setStartProcessingLoading] = useState(false);
    const [syncLoading, setSyncLoading] = useState(false);
    const [retryIngestionLoading, setRetryIngestionLoading] = useState(false);
    const [retryProcessingLoading, setRetryProcessingLoading] = useState(false);

    const { subscribe } = useSSE();
    const { toast } = useToast();

    const loadRepo = useCallback(async () => {
        try {
            const data = await reposApi.get(repoId);
            setRepo(data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, [repoId]);

    const loadProgress = useCallback(async () => {
        try {
            const data = await reposApi.getImportProgress(repoId);
            setProgress({
                checkpoint: data.checkpoint,
                import_builds: data.import_builds,
                resource_status: data.resource_status,
                training_builds: data.training_builds,
            });
        } catch (err) {
            console.error(err);
        }
    }, [repoId]);

    const loadBuilds = useCallback(async () => {
        try {
            const data = await buildApi.getByRepo(repoId, { skip: 0, limit: 5 });
            setBuilds(data.items);
        } catch (err) {
            console.error(err);
        }
    }, [repoId]);

    useEffect(() => {
        loadRepo();
        loadProgress();
        loadBuilds();
    }, [loadRepo, loadProgress, loadBuilds]);

    // Debounced refresh for SSE updates (only for full refetch scenarios)
    const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
    const debouncedRefresh = useMemo(() => {
        return () => {
            if (debounceTimerRef.current) {
                clearTimeout(debounceTimerRef.current);
            }
            debounceTimerRef.current = setTimeout(() => {
                loadRepo();
                loadProgress();
                loadBuilds();
            }, 1000);
        };
    }, [loadRepo, loadProgress, loadBuilds]);

    // Cleanup debounce timer on unmount
    useEffect(() => {
        return () => {
            if (debounceTimerRef.current) {
                clearTimeout(debounceTimerRef.current);
            }
        };
    }, []);

    // SSE subscription for MODEL.REPO.UPDATED with delta merge
    useEffect(() => {
        const unsubscribe = subscribe("MODEL.REPO.UPDATED", (data: {
            repo_id: string;
            status?: string;
            message?: string;
            stats?: {
                builds_fetched?: number;
                builds_ingested?: number;
                builds_processing?: number;
                builds_processed?: number;
                [key: string]: number | undefined;
            };
        }) => {
            if (data.repo_id === repoId) {
                // Delta merge for repo status
                if (data.status) {
                    setRepo((prev) => prev ? { ...prev, status: data.status as RepoDetail["status"] } : prev);
                }

                // Delta merge for progress stats if provided
                if (data.stats) {
                    setProgress((prev) => {
                        if (!prev) return prev;
                        return {
                            ...prev,
                            import_builds: {
                                ...prev.import_builds,
                                fetched: data.stats?.builds_fetched ?? prev.import_builds.fetched,
                                ingested: data.stats?.builds_ingested ?? prev.import_builds.ingested,
                            },
                            training_builds: {
                                ...prev.training_builds,
                                completed: data.stats?.builds_processed ?? prev.training_builds.completed,
                            },
                        };
                    });
                }

                // Debounced full refresh for status changes that affect overall state
                if (data.status && ["ingested", "processed", "failed", "idle"].includes(data.status)) {
                    debouncedRefresh();
                }
            }
        });
        return () => unsubscribe();
    }, [subscribe, debouncedRefresh, repoId]);

    // Optimistic progress updates for granular events
    useEffect(() => {
        const unsubscribeProcessing = subscribe("MODEL.PROCESSING.UPDATED", (data: {
            repo_id: string;
            extraction_status: string;
        }) => {
            if (data.repo_id === repoId) {
                // Update training builds count on completion/failure
                if (["completed", "failed", "partial"].includes(data.extraction_status)) {
                    setProgress((prev) => {
                        if (!prev) return prev;
                        // Avoid double counting if rapid updates come in
                        const current = prev.training_builds;
                        // Simple heuristic: if we receive a completion event, assume one moved from pending to completed
                        // Ideally we'd track build IDs, but for a simple counter update this is usually sufficient visual feedback
                        return {
                            ...prev,
                            training_builds: {
                                ...current,
                                pending: Math.max(0, current.pending - 1),
                                completed: data.extraction_status === "completed" ? current.completed + 1 : current.completed,
                                partial: data.extraction_status === "partial" ? current.partial + 1 : current.partial,
                                failed: data.extraction_status === "failed" ? current.failed + 1 : current.failed,
                            }
                        };
                    });
                }
            }
        });

        const unsubscribePrediction = subscribe("MODEL.PREDICTION.UPDATED", (data: {
            repo_id: string;
            prediction_status: string;
        }) => {
            if (data.repo_id === repoId) {
                if (["completed", "failed"].includes(data.prediction_status)) {
                    setProgress((prev) => {
                        if (!prev) return prev;
                        const current = prev.training_builds;
                        return {
                            ...prev,
                            training_builds: {
                                ...current,
                                pending_prediction: Math.max(0, (current.pending_prediction || 0) - 1),
                                with_prediction: data.prediction_status === "completed" ? (current.with_prediction || 0) + 1 : current.with_prediction,
                                prediction_failed: data.prediction_status === "failed" ? (current.prediction_failed || 0) + 1 : current.prediction_failed,
                            }
                        };
                    });
                }
            }
        });

        return () => {
            unsubscribeProcessing();
            unsubscribePrediction();
        };
    }, [subscribe, repoId]);

    // Listen for INGESTION_ERROR events
    useEffect(() => {
        const handleIngestionError = (event: CustomEvent<{
            repo_id: string;
            resource: string;
            chunk_index: number;
            error: string;
        }>) => {
            // Check if error is for this repo (by id)
            if (repo?.id === event.detail.repo_id) {
                toast({
                    variant: "destructive",
                    title: `Ingestion Error (${event.detail.resource})`,
                    description: event.detail.error.slice(0, 150),
                });
                loadProgress();
            }
        };

        window.addEventListener("INGESTION_ERROR", handleIngestionError as EventListener);
        return () => {
            window.removeEventListener("INGESTION_ERROR", handleIngestionError as EventListener);
        };
    }, [repo?.id, loadProgress, toast]);


    // Action handlers
    const handleStartProcessing = async () => {
        setStartProcessingLoading(true);
        try {
            await reposApi.startProcessing(repoId);
            loadRepo();
            loadProgress();
        } catch (err) {
            console.error(err);
        } finally {
            setStartProcessingLoading(false);
        }
    };

    const handleSync = async () => {
        setSyncLoading(true);
        try {
            await reposApi.triggerLazySync(repoId);
            loadRepo();
        } catch (err) {
            console.error(err);
        } finally {
            setSyncLoading(false);
        }
    };

    const handleRetryIngestion = async () => {
        setRetryIngestionLoading(true);
        try {
            await reposApi.reingestFailed(repoId);
            loadRepo();
            loadProgress();
        } catch (err) {
            console.error(err);
        } finally {
            setRetryIngestionLoading(false);
        }
    };

    const handleRetryProcessing = async () => {
        setRetryProcessingLoading(true);
        try {
            await reposApi.reprocessFailed(repoId);
            loadRepo();
            loadProgress();
        } catch (err) {
            console.error(err);
        } finally {
            setRetryProcessingLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="flex min-h-[60vh] items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (!repo) {
        return (
            <div className="flex min-h-[60vh] items-center justify-center">
                <Card className="w-full max-w-md">
                    <CardHeader>
                        <CardTitle>Repository not found</CardTitle>
                        <CardDescription>
                            The repository you are looking for does not exist.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Button onClick={() => router.push("/repositories")}>
                            <ArrowLeft className="mr-2 h-4 w-4" />
                            Back to Repositories
                        </Button>
                    </CardContent>
                </Card>
            </div>
        );
    }

    // Determine active tab from pathname
    const isOverviewActive = pathname === `/repositories/${repoId}` || pathname.endsWith("/overview");
    const isBuildsActive = pathname.includes("/builds");
    const isAnalyticsActive = pathname.includes("/analytics");
    // Check if we're on a build detail page (hide tabs for cleaner UI)
    const isBuildDetailPage = pathname.includes("/build/") && pathname.split("/").length > 4;

    const contextValue: RepoContextType = {
        repo,
        progress,
        builds,
        loading,
        repoId,
        loadRepo,
        loadProgress,
        loadBuilds,
        handleStartProcessing,
        handleSync,
        handleRetryIngestion,
        handleRetryProcessing,
        startProcessingLoading,
        syncLoading,
        retryIngestionLoading,
        retryProcessingLoading,
    };

    return (
        <RepoContext.Provider value={contextValue}>
            <div className="space-y-6">
                {/* Header - simplified on build detail page */}
                {!isBuildDetailPage && (
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => router.push("/repositories")}
                                className="gap-2"
                            >
                                <ArrowLeft className="h-4 w-4" />
                                Back
                            </Button>
                            <div>
                                <div className="flex items-center gap-3">
                                    <h1 className="text-2xl font-bold tracking-tight">
                                        {repo.full_name}
                                    </h1>
                                    <Badge
                                        variant={repo.is_private ? "secondary" : "outline"}
                                        className="gap-1"
                                    >
                                        {repo.is_private ? (
                                            <Lock className="h-3 w-3" />
                                        ) : (
                                            <Globe className="h-3 w-3" />
                                        )}
                                        {repo.is_private ? "Private" : "Public"}
                                    </Badge>
                                </div>
                                {repo.metadata?.description && (
                                    <p className="text-muted-foreground mt-1">
                                        {repo.metadata.description}
                                    </p>
                                )}
                            </div>
                        </div>
                        {repo.metadata?.html_url && (
                            <a
                                href={repo.metadata.html_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                            >
                                <ExternalLink className="h-4 w-4" />
                                View on GitHub
                            </a>
                        )}
                    </div>
                )}

                {/* Tab Navigation - hide on build detail page */}
                {!isBuildDetailPage && (
                    <div className="border-b w-full">
                        <nav className="flex w-full">
                            <Link
                                href={`/repositories/${repoId}/overview`}
                                className={cn(
                                    "flex-1 text-center pb-3 text-sm font-medium transition-colors border-b-2",
                                    isOverviewActive
                                        ? "border-primary text-primary"
                                        : "border-transparent text-muted-foreground hover:text-foreground"
                                )}
                            >
                                Overview
                            </Link>
                            <Link
                                href={`/repositories/${repoId}/builds`}
                                className={cn(
                                    "flex-1 text-center pb-3 text-sm font-medium transition-colors border-b-2",
                                    isBuildsActive
                                        ? "border-primary text-primary"
                                        : "border-transparent text-muted-foreground hover:text-foreground"
                                )}
                            >
                                Builds
                            </Link>
                            <Link
                                href={`/repositories/${repoId}/analytics`}
                                className={cn(
                                    "flex-1 text-center pb-3 text-sm font-medium transition-colors border-b-2",
                                    isAnalyticsActive
                                        ? "border-primary text-primary"
                                        : "border-transparent text-muted-foreground hover:text-foreground"
                                )}
                            >
                                Analytics
                            </Link>
                        </nav>
                    </div>
                )}

                {/* Page Content */}
                {children}
            </div>
        </RepoContext.Provider>
    );
}
