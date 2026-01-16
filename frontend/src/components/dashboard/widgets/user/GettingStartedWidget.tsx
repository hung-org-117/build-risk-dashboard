"use client";

import { ShieldCheck, GripVertical } from "lucide-react";
import { useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { BaseWidgetProps } from "../../types";

/**
 * Getting Started Widget - User Widget
 * 
 * Shows quick start guide for users who don't have data yet
 * Auto-hides when user has repos and builds
 * 
 * Data Scope:
 * - Uses filtered summary.active_repos and summary.metrics.total_builds
 * - Both values are RBAC-filtered by backend
 */
export function GettingStartedWidget({ summary, isEditing, className }: BaseWidgetProps) {
  const router = useRouter();
  const hasRepos = summary.active_repos > 0;
  const hasBuilds = summary.metrics.total_builds > 0;

  // If user has data, show success state
  if (hasRepos && hasBuilds) {
    return (
      <Card className={cn("h-full", className)}>
        <CardContent className="flex items-center justify-center h-full">
          <div className="text-center space-y-2">
            <ShieldCheck className="h-8 w-8 mx-auto text-green-500" />
            <p className="text-sm font-medium text-green-600">You&apos;re all set!</p>
            <p className="text-xs text-muted-foreground">
              {summary.active_repos} repos, {summary.metrics.total_builds} builds
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Otherwise show onboarding steps
  return (
    <Card className={cn(
      "h-full overflow-hidden border-blue-200 bg-blue-50/50 dark:border-blue-800 dark:bg-blue-900/20",
      isEditing && "ring-2 ring-blue-500/20 cursor-move",
      className
    )}>
      {isEditing && (
        <div className="absolute top-2 left-2 z-10">
          <GripVertical className="h-4 w-4 text-muted-foreground" />
        </div>
      )}
      <CardHeader className="pb-2">
        <CardTitle className="text-sm truncate">Getting Started</CardTitle>
        <CardDescription className="text-xs truncate">
          Quick start guide
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 overflow-auto">
        <div className="flex items-center gap-2">
          <div className={cn(
            "w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold",
            hasRepos ? "bg-green-500 text-white" : "bg-blue-500 text-white"
          )}>
            {hasRepos ? "✓" : "1"}
          </div>
          <span className={cn(
            "text-sm",
            hasRepos && "line-through text-muted-foreground"
          )}>
            Import a repository
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className={cn(
            "w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold",
            hasBuilds ? "bg-green-500 text-white" : "bg-slate-300 text-slate-600"
          )}>
            {hasBuilds ? "✓" : "2"}
          </div>
          <span className={cn(
            "text-sm",
            hasBuilds ? "line-through text-muted-foreground" : "text-muted-foreground"
          )}>
            Wait for ingestion
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold bg-slate-300 text-slate-600">
            3
          </div>
          <span className="text-sm text-muted-foreground">Start processing</span>
        </div>
        {!hasRepos && !isEditing && (
          <button
            onClick={() => router.push("/repositories/import")}
            className="mt-2 w-full px-3 py-1.5 text-xs font-medium text-white bg-blue-500 rounded hover:bg-blue-600 transition"
          >
            Import Repository
          </button>
        )}
      </CardContent>
    </Card>
  );
}
