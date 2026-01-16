"use client";

import { ShieldCheck, GripVertical } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { BaseWidgetProps } from "../../types";

/**
 * Success Rate Widget - Common Widget
 * 
 * Data Scope:
 * - User: Success rate calculated from their accessible repos only
 * - Admin: Success rate from all repos
 * 
 * Calculation in dashboard_service.py:
 * - Filters builds by repo_ids based on user permissions
 * - successful_builds / total_builds * 100
 */
export function SuccessRateWidget({ summary, isEditing, className }: BaseWidgetProps) {
  const successRate = summary.metrics.success_rate;

  return (
    <Card className={cn(
      "relative flex flex-col",
      isEditing && "ring-2 ring-blue-500/20 cursor-move",
      className
    )}>
      {isEditing && (
        <div className="absolute top-2 left-2 z-10">
          <GripVertical className="h-4 w-4 text-muted-foreground" />
        </div>
      )}
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1 pt-3 px-4">
        <CardTitle className="text-xs font-medium text-muted-foreground truncate pr-2">
          Success Rate
        </CardTitle>
        <ShieldCheck className="h-5 w-5 text-emerald-500 flex-shrink-0" />
      </CardHeader>
      <CardContent className="pb-3 px-4 flex-1">
        <div className="text-xl font-bold truncate">
          {successRate.toFixed(1)}%
        </div>
        <p className="text-[10px] text-muted-foreground truncate">
          Build success ratio
        </p>
      </CardContent>
    </Card>
  );
}
