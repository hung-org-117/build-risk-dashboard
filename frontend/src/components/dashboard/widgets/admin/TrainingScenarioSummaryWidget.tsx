"use client";

import { Rocket, Layers, CheckCircle2, GripVertical } from "lucide-react";
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
 * Training Scenario Summary Widget - Admin-Only Widget
 * 
 * Data Scope:
 * - ADMIN ONLY: Requires summary.admin_extras.dataset_enrichment
 * - Shows system-wide Training Scenario / Dataset Enrichment stats
 * - NULL for non-admin users
 * 
 * Backend guarantee:
 * - admin_extras only populated if user.role === "admin"
 * - Shows scenarios, datasets, exports counts
 */
export function TrainingScenarioSummaryWidget({ summary, isEditing, className }: BaseWidgetProps) {
  const enrichmentStats = summary?.admin_extras?.dataset_enrichment;

  if (!enrichmentStats) {
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
        <CardTitle className="text-sm truncate">Dataset Enrichment</CardTitle>
        <CardDescription className="text-xs truncate">
          Training Scenario Pipeline
        </CardDescription>
      </CardHeader>
      <CardContent className="flex items-center justify-around gap-2 h-[calc(100%-60px)] px-2">
        <div className="flex flex-col items-center min-w-0">
          <Rocket className="h-5 w-5 text-blue-500 mb-1" />
          <div className="text-xl font-bold text-blue-600">
            {enrichmentStats.active_scenarios ?? 0}
          </div>
          <div className="text-[10px] text-muted-foreground truncate">Scenarios</div>
        </div>
        <div className="flex flex-col items-center min-w-0">
          <Layers className="h-5 w-5 text-indigo-500 mb-1" />
          <div className="text-xl font-bold text-indigo-600">
            {enrichmentStats.total_datasets ?? 0}
          </div>
          <div className="text-[10px] text-muted-foreground truncate">Datasets</div>
        </div>
        <div className="flex flex-col items-center min-w-0">
          <CheckCircle2 className="h-5 w-5 text-green-500 mb-1" />
          <div className="text-xl font-bold text-green-600">
            {enrichmentStats.exported_datasets ?? 0}
          </div>
          <div className="text-[10px] text-muted-foreground truncate">Exported</div>
        </div>
      </CardContent>
    </Card>
  );
}
