"use client";

import { FolderGit2, Database, CheckCircle2, GripVertical } from "lucide-react";
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
 * Model Pipeline Summary Widget - Admin-Only Widget
 * 
 * Data Scope:
 * - ADMIN ONLY: Requires summary.admin_extras.model_pipeline
 * - Shows system-wide Build Risk Evaluation pipeline stats
 * - NULL for non-admin users (admin_extras is null)
 * 
 * Backend guarantee:
 * - admin_extras only populated if user.role === "admin"
 * - dashboard_service.py: admin_extras = _fetch_admin_pipeline_stats() if is_admin else None
 */
export function ModelPipelineSummaryWidget({ summary, isEditing, className }: BaseWidgetProps) {
  const pipelineStats = summary?.admin_extras?.model_pipeline;

  if (!pipelineStats) {
    return (
      <Card className={cn("h-full", className)}>
        <CardContent className="flex items-center justify-center h-full">
          <p className="text-xs text-muted-foreground">Admin data not available</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn("h-full overflow-hidden", isEditing && "ring-2 ring-blue-500/20 cursor-move", className)}>
      {isEditing && (
        <div className="absolute top-2 left-2 z-10">
          <GripVertical className="h-4 w-4 text-muted-foreground" />
        </div>
      )}
      <CardHeader className="pb-2">
        <CardTitle className="text-sm truncate">Build Risk Evaluation</CardTitle>
        <CardDescription className="text-xs truncate">
          Model Pipeline Status
        </CardDescription>
      </CardHeader>
      <CardContent className="flex items-center justify-around gap-2 h-[calc(100%-60px)] px-2">
        <div className="flex flex-col items-center min-w-0">
          <FolderGit2 className="h-5 w-5 text-slate-500 mb-1" />
          <div className="text-xl font-bold text-slate-600">
            {pipelineStats.imported_repos ?? 0}
          </div>
          <div className="text-[10px] text-muted-foreground truncate">Imported</div>
        </div>
        <div className="flex flex-col items-center min-w-0">
          <Database className="h-5 w-5 text-purple-500 mb-1" />
          <div className="text-xl font-bold text-purple-600">
            {pipelineStats.ingested_repos_distinct ?? 0}
          </div>
          <div className="text-[10px] text-muted-foreground truncate">Ingested</div>
        </div>
        <div className="flex flex-col items-center min-w-0">
          <CheckCircle2 className="h-5 w-5 text-green-500 mb-1" />
          <div className="text-xl font-bold text-green-600">
            {pipelineStats.processed_repos ?? 0}
          </div>
          <div className="text-[10px] text-muted-foreground truncate">Processed</div>
        </div>
      </CardContent>
    </Card>
  );
}
