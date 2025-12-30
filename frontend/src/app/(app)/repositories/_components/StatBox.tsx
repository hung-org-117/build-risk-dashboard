"use client";

import { cn } from "@/lib/utils";

interface StatBoxProps {
    label: string;
    value: string | number;
    subValue?: string;
    variant?: "default" | "success" | "warning" | "error";
}

export function StatBox({ label, value, subValue, variant = "default" }: StatBoxProps) {
    return (
        <div className={cn(
            "flex flex-col items-center justify-center py-3 px-6 rounded-lg border min-w-[120px] flex-1",
            variant === "default" && "bg-slate-50 dark:bg-slate-900/50 border-slate-200 dark:border-slate-800",
            variant === "success" && "bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-900",
            variant === "warning" && "bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-900",
            variant === "error" && "bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-900"
        )}>
            <span className={cn(
                "text-2xl font-bold",
                variant === "default" && "text-slate-900 dark:text-slate-100",
                variant === "success" && "text-green-600 dark:text-green-400",
                variant === "warning" && "text-amber-600 dark:text-amber-400",
                variant === "error" && "text-red-600 dark:text-red-400"
            )}>
                {value}
            </span>
            <span className="text-xs text-muted-foreground mt-1">{label}</span>
            {subValue && (
                <span className="text-xs text-muted-foreground">{subValue}</span>
            )}
        </div>
    );
}
