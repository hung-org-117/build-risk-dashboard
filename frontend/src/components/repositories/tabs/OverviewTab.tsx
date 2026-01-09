"use client";

import { ArrowRight, GitBranch, ExternalLink, Globe, Lock, CheckCircle2, XCircle, Clock, GitCommit, AlertCircle } from "lucide-react";
import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { formatTimestamp } from "@/lib/utils";
import type { Build, RepoDetail } from "@/types";

import { MiniStepper } from "@/app/(app)/repositories/_components/MiniStepper";
import { CollectionCard } from "@/app/(app)/repositories/_components/CollectionCard";
import { ProcessingCard } from "@/app/(app)/repositories/_components/ProcessingCard";
import { CurrentPhaseCard } from "@/app/(app)/repositories/_components/CurrentPhaseCard"; // Not used in the pasted code but imported

import { ImportProgress } from "../RepoContext";

interface OverviewTabProps {
    repo: RepoDetail;
    progress: ImportProgress | null;
    builds: Build[];
    // Action handlers - optional for read-only views
    onSync?: () => void;
    onRetryIngestion?: () => void;
    onStartProcessing?: () => void;
    onRetryFailed?: () => void;
    // Loading states - optional
    syncLoading?: boolean;
    retryIngestionLoading?: boolean;
    startProcessingLoading?: boolean;
    retryFailedLoading?: boolean;
}

export function OverviewTab({
    repo,
    progress,
    builds,
    onSync,
    onRetryIngestion,
    onStartProcessing,
    onRetryFailed,
    syncLoading,
    retryIngestionLoading,
    startProcessingLoading,
    retryFailedLoading,
}: OverviewTabProps) {
    const router = useRouter();
    const status = repo.status || "queued";

    return (
        <div className="space-y-6">
            {/* Mini Stepper */}
            <MiniStepper status={status} progress={progress} />

            {/* Collection Card - read-only view */}
            <CollectionCard
                fetchedCount={progress?.import_builds.total || 0}
                ingestedCount={progress?.import_builds.ingested || 0}
                totalCount={progress?.import_builds.total || 0}
                missingResourceCount={progress?.import_builds.missing_resource || 0}
                failedCount={0}
                lastSyncedAt={repo.last_synced_at}
                status={status}
                // Checkpoint props
                hasCheckpoint={progress?.checkpoint?.has_checkpoint || false}
                checkpointAt={progress?.checkpoint?.last_checkpoint_at}
                acceptedFailedCount={progress?.checkpoint?.accepted_failed || 0}
            />

            {/* Processing Card - read-only view */}
            <ProcessingCard
                extractedCount={(progress?.training_builds.completed || 0) + (progress?.training_builds.partial || 0)}
                extractedTotal={progress?.training_builds.total || progress?.import_builds.ingested || 0}
                predictedCount={progress?.training_builds.with_prediction || 0}
                predictedTotal={(progress?.training_builds.completed || 0) + (progress?.training_builds.partial || 0)}
                failedExtractionCount={progress?.training_builds.failed || 0}
                failedPredictionCount={progress?.training_builds.prediction_failed || 0}
                status={status}
                lastProcessedBuildId={progress?.checkpoint?.current_processing_build_number}
            />

            {/* Repository Info */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg">Repository Info</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex flex-wrap gap-6 text-sm">
                        <div className="flex items-center gap-2">
                            <GitBranch className="h-4 w-4 text-muted-foreground" />
                            <span className="text-muted-foreground">Default:</span>
                            <span className="font-medium">{repo.default_branch || "main"}</span>
                        </div>
                        {repo.main_lang && (
                            <div className="flex items-center gap-2">
                                <span className="text-muted-foreground">Language:</span>
                                <Badge variant="outline">{repo.main_lang}</Badge>
                            </div>
                        )}
                        <div className="flex items-center gap-2">
                            <span className="text-muted-foreground">CI:</span>
                            <Badge variant="outline">{repo.ci_provider}</Badge>
                        </div>
                        <div className="flex items-center gap-2">
                            {repo.is_private ? <Lock className="h-4 w-4" /> : <Globe className="h-4 w-4" />}
                            <span>{repo.is_private ? "Private" : "Public"}</span>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
