"use client";

import { useState, useEffect, useCallback } from "react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
    Download,
    CheckCircle2,
    AlertCircle,
    FileText,
    FileJson,
    Clock,
} from "lucide-react";

// Export Job Status Interface
export interface ExportJobStatus {
    id: string;
    status: "pending" | "processing" | "completed" | "failed";
    progress: number;
    error_message?: string;
}

// Export Adapter Interface - Implement this for each export source
export interface ExportAdapter {
    /** Display name for the export (e.g., "Version v1.0" or "my-repo") */
    name: string;

    /** Total number of rows to export */
    totalRows: number;

    /** Download via streaming (for small datasets) */
    downloadStream: (format: "csv" | "json") => Promise<Blob>;

    /** Create async export job (for large datasets) */
    createAsyncJob: (format: "csv" | "json") => Promise<{ job_id: string }>;

    /** Get async job status */
    getJobStatus: (jobId: string) => Promise<ExportJobStatus>;

    /** Download completed async job */
    downloadJob: (jobId: string) => Promise<Blob>;
}

// Export Modal Props
interface ExportModalProps {
    isOpen: boolean;
    onClose: () => void;
    adapter: ExportAdapter;
    /** Threshold for recommending async export (default: 10000) */
    asyncThreshold?: number;
}

// Generic Export Modal Component
type ExportStatus = "idle" | "exporting" | "polling" | "completed" | "error";

export function ExportModal({
    isOpen,
    onClose,
    adapter,
    asyncThreshold = 10000,
}: ExportModalProps) {
    const [format, setFormat] = useState<"csv" | "json">("csv");
    const [status, setStatus] = useState<ExportStatus>("idle");
    const [progress, setProgress] = useState(0);
    const [jobId, setJobId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const isLargeDataset = adapter.totalRows > asyncThreshold;

    // Poll for async job status
    useEffect(() => {
        if (status !== "polling" || !jobId) return;

        const interval = setInterval(async () => {
            try {
                const job = await adapter.getJobStatus(jobId);
                setProgress(job.progress);

                if (job.status === "completed") {
                    setStatus("completed");
                    clearInterval(interval);
                } else if (job.status === "failed") {
                    setError(job.error_message || "Export failed");
                    setStatus("error");
                    clearInterval(interval);
                }
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to check status");
                setStatus("error");
                clearInterval(interval);
            }
        }, 2000);

        return () => clearInterval(interval);
    }, [status, jobId, adapter]);

    // =========================================================================
    // Stream Export Handler (for small datasets)
    // =========================================================================
    const handleStreamExport = useCallback(async () => {
        setStatus("exporting");
        setError(null);

        try {
            const blob = await adapter.downloadStream(format);
            triggerDownload(blob, `${adapter.name}.${format}`);
            setStatus("completed");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Export failed");
            setStatus("error");
        }
    }, [adapter, format]);

    // Async Export Handler (for large datasets)
    const handleAsyncExport = useCallback(async () => {
        setStatus("exporting");
        setError(null);
        setProgress(0);

        try {
            const result = await adapter.createAsyncJob(format);
            setJobId(result.job_id);
            setStatus("polling");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to create export job");
            setStatus("error");
        }
    }, [adapter, format]);

    // Download Completed Job
    const handleDownloadCompleted = useCallback(async () => {
        if (!jobId) return;

        try {
            const blob = await adapter.downloadJob(jobId);
            triggerDownload(blob, `${adapter.name}.${format}`);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Download failed");
        }
    }, [adapter, jobId, format]);

    // Main Export Handler
    const handleExport = () => {
        if (isLargeDataset) {
            handleAsyncExport();
        } else {
            handleStreamExport();
        }
    };

    // Reset & Close
    const handleClose = () => {
        setStatus("idle");
        setProgress(0);
        setJobId(null);
        setError(null);
        onClose();
    };

    return (
        <Dialog open={isOpen} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle>Export Data</DialogTitle>
                    <DialogDescription>
                        {adapter.name} • {adapter.totalRows.toLocaleString()} rows
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {/* Large dataset warning */}
                    {isLargeDataset && status === "idle" && (
                        <Alert>
                            <Clock className="h-4 w-4" />
                            <AlertDescription>
                                Large dataset detected. Export will be processed in the background.
                            </AlertDescription>
                        </Alert>
                    )}

                    {/* Format selection */}
                    {status === "idle" && (
                        <div className="space-y-3">
                            <Label>Export Format</Label>
                            <div className="grid grid-cols-2 gap-4">
                                <Button
                                    type="button"
                                    variant={format === "csv" ? "default" : "outline"}
                                    className="flex flex-col h-auto py-4 gap-2"
                                    onClick={() => setFormat("csv")}
                                >
                                    <FileText className="h-6 w-6" />
                                    <span className="text-sm font-medium">CSV</span>
                                </Button>
                                <Button
                                    type="button"
                                    variant={format === "json" ? "default" : "outline"}
                                    className="flex flex-col h-auto py-4 gap-2"
                                    onClick={() => setFormat("json")}
                                >
                                    <FileJson className="h-6 w-6" />
                                    <span className="text-sm font-medium">JSON</span>
                                </Button>
                            </div>
                        </div>
                    )}

                    {/* Progress display */}
                    {(status === "exporting" || status === "polling") && (
                        <div className="space-y-3">
                            <div className="flex items-center justify-between text-sm">
                                <span className="text-muted-foreground">
                                    {status === "exporting" ? "Preparing..." : "Processing..."}
                                </span>
                                <span className="font-medium">{Math.round(progress)}%</span>
                            </div>
                            <Progress value={progress} className="h-2" />
                        </div>
                    )}

                    {/* Completed */}
                    {status === "completed" && (
                        <div className="flex flex-col items-center gap-4 py-4">
                            <CheckCircle2 className="h-12 w-12 text-green-500" />
                            <p className="text-center text-sm text-muted-foreground">
                                Export completed!
                            </p>
                            {jobId && (
                                <Button onClick={handleDownloadCompleted} className="w-full">
                                    <Download className="mr-2 h-4 w-4" />
                                    Download File
                                </Button>
                            )}
                        </div>
                    )}

                    {/* Error */}
                    {status === "error" && (
                        <Alert variant="destructive">
                            <AlertCircle className="h-4 w-4" />
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}
                </div>

                {/* Actions */}
                <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={handleClose}>
                        {status === "completed" ? "Close" : "Cancel"}
                    </Button>
                    {status === "idle" && (
                        <Button onClick={handleExport}>
                            <Download className="mr-2 h-4 w-4" />
                            {isLargeDataset ? "Start Export" : "Download"}
                        </Button>
                    )}
                    {status === "error" && (
                        <Button onClick={handleExport} variant="outline">
                            Retry
                        </Button>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}

// Helper: Trigger browser download
function triggerDownload(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
