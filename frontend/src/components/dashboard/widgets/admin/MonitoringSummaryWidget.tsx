"use client";

import { AlertTriangle, GripVertical } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { BaseWidgetProps } from "../../types";

/**
 * Monitoring Summary Widget - Admin-Only Widget
 * 
 * Data Scope:
 * - ADMIN ONLY: Requires summary.admin_extras.monitoring
 * - Shows system-wide monitoring stats (24h errors)
 * - NULL for non-admin users
 * 
 * Backend guarantee:
 * - admin_extras.monitoring only for admins
 * - Shows error_count_24h from system logs
 */
export function MonitoringSummaryWidget({ summary, isEditing, className }: BaseWidgetProps) {
  const monitoringStats = summary?.admin_extras?.monitoring;
  const hasErrors = (monitoringStats?.error_count_24h ?? 0) > 0;

  if (!monitoringStats) {
    return (
      <Card className={cn("h-full", className)}>
        <CardContent className="flex items-center justify-center h-full">
          <p className="text-xs text-muted-foreground">Admin data not available</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn(
      "h-full overflow-hidden",
      hasErrors && "border-amber-200 bg-amber-50/50 dark:border-amber-800 dark:bg-amber-900/20",
      isEditing && "ring-2 ring-blue-500/20 cursor-move",
      className
    )}>
      {isEditing && (
        <div className="absolute top-2 left-2 z-10">
          <GripVertical className="h-4 w-4 text-muted-foreground" />
        </div>
      )}
      <CardHeader className="pb-2">
        <CardTitle className="text-sm truncate">System Health</CardTitle>
        <CardDescription className="text-xs truncate">
          Monitoring (24h)
        </CardDescription>
      </CardHeader>
      <CardContent className="flex items-center justify-center gap-4 h-[calc(100%-60px)]">
        <div className="flex flex-col items-center">
          <AlertTriangle className={cn(
            "h-6 w-6 mb-1",
            hasErrors ? "text-amber-600" : "text-green-600"
          )} />
          <div className={cn(
            "text-2xl font-bold",
            hasErrors ? "text-amber-600" : "text-green-600"
          )}>
            {monitoringStats.error_count_24h ?? 0}
          </div>
          <div className="text-xs text-muted-foreground">Errors</div>
        </div>
      </CardContent>
    </Card>
  );
}
