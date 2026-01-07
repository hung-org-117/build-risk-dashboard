"use client";

import { AlertTriangle, CheckCircle2, Circle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface ImportProgress {
    import_builds: {
        pending: number;
        fetched: number;
        ingesting: number;
        ingested: number;
        missing_resource: number;
        total: number;
    };
    training_builds: {
        pending: number;
        completed: number;
        partial: number;
        failed: number;
        total: number;
        with_prediction?: number;
        pending_prediction?: number;
        prediction_failed?: number;
    };
}

type StepState = "completed" | "active" | "pending" | "warning";

interface Step {
    id: string;
    label: string;
    getCurrent: (p: ImportProgress | null) => number;
    getTotal: (p: ImportProgress | null) => number;
    getState: (status: string, p: ImportProgress | null) => StepState;
}

const STEPS: Step[] = [
    {
        id: "fetch",
        label: "Fetch",
        getCurrent: (p) => p?.import_builds.total || 0,
        getTotal: (p) => p?.import_builds.total || 0,
        getState: (status, p) => {
            if (p && p.import_builds.total > 0) return "completed";
            if (["queued", "fetching"].includes(status.toLowerCase())) return "active";
            return "pending";
        },
    },
    {
        id: "ingest",
        label: "Ingest",
        getCurrent: (p) => (p?.import_builds.ingested || 0) + (p?.import_builds.missing_resource || 0),
        getTotal: (p) => p?.import_builds.total || 0,
        getState: (status, p) => {
            const s = status.toLowerCase();
            // Ingested/processing/processed means ingestion phase is done
            if (["ingested", "processing", "processed"].includes(s)) {
                // Check if all ingested or has missing resources
                const ingested = p?.import_builds.ingested || 0;
                const missing = p?.import_builds.missing_resource || 0;
                const total = p?.import_builds.total || 0;
                // If has missing resources, show warning state
                if (missing > 0 && ingested < total) return "warning";
                return "completed";
            }
            if (s === "ingesting") return "active";
            return "pending";
        },
    },
    {
        id: "extract",
        label: "Extract",
        getCurrent: (p) => (p?.training_builds.completed || 0) + (p?.training_builds.partial || 0),
        getTotal: (p) => p?.training_builds.total || p?.import_builds.ingested || 0,
        getState: (status, p) => {
            const current = (p?.training_builds.completed || 0) + (p?.training_builds.partial || 0);
            const total = p?.training_builds.total || p?.import_builds.ingested || 0;
            const s = status.toLowerCase();

            // If no ingested builds, can't extract
            if (total === 0) return "pending";

            // All extracted
            if (current >= total && total > 0) return "completed";

            // Actively processing
            if (s === "processing") return "active";

            // Some extracted but not all (partial)
            if (current > 0 && current < total) return "active";

            return "pending";
        },
    },
    {
        id: "predict",
        label: "Predict",
        getCurrent: (p) => p?.training_builds.with_prediction || 0,
        getTotal: (p) => (p?.training_builds.completed || 0) + (p?.training_builds.partial || 0),
        getState: (status, p) => {
            const done = p?.training_builds.with_prediction || 0;
            const total = (p?.training_builds.completed || 0) + (p?.training_builds.partial || 0);

            // No extraction done yet, prediction is pending
            if (total === 0) return "pending";

            // All predictions done
            if (done >= total && total > 0) return "completed";

            // If has predictions but not all
            if (done > 0 && done < total) return "active";

            // Waiting for predictions
            if (p?.training_builds.pending_prediction && p.training_builds.pending_prediction > 0) return "active";

            return "pending";
        },
    },
];

function StepIcon({ state }: { state: StepState }) {
    if (state === "completed") return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    if (state === "warning") return <AlertTriangle className="h-4 w-4 text-amber-500" />;
    if (state === "active") return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
    return <Circle className="h-4 w-4 text-slate-300 dark:text-slate-600" />;
}

interface MiniStepperProps {
    status: string;
    progress: ImportProgress | null;
}

export function MiniStepper({ status, progress }: MiniStepperProps) {
    return (
        <div className="flex items-center justify-center py-4 px-6 bg-slate-50 dark:bg-slate-900/50 rounded-lg w-full">
            <div className="flex items-center gap-2 max-w-3xl w-full">
                {STEPS.map((step, i) => {
                    const state = step.getState(status, progress);
                    const current = step.getCurrent(progress);
                    const total = step.getTotal(progress);
                    const isLast = i === STEPS.length - 1;

                    return (
                        <div key={step.id} className="flex items-center flex-1">
                            <div className="flex items-center gap-2">
                                <StepIcon state={state} />
                                <div className="flex flex-col">
                                    <span className={cn(
                                        "text-sm font-medium",
                                        state === "completed" && "text-green-600",
                                        state === "warning" && "text-amber-600",
                                        state === "active" && "text-blue-600",
                                        state === "pending" && "text-slate-400"
                                    )}>
                                        {step.label}
                                    </span>
                                    <span className="text-xs text-muted-foreground">
                                        {total > 0 ? `${current}/${total}` : "—"}
                                    </span>
                                </div>
                            </div>
                            {!isLast && (
                                <div className={cn(
                                    "flex-1 h-0.5 mx-3",
                                    state === "completed" && "bg-green-500",
                                    state === "warning" && "bg-amber-500",
                                    state !== "completed" && state !== "warning" && "bg-slate-200 dark:bg-slate-700"
                                )} />
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
