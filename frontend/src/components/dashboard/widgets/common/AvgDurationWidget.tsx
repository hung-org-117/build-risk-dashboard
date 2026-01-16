"use client";

import { Timer, GripVertical } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn, formatDuration } from "@/lib/utils";
import type { BaseWidgetProps } from "../../types";

/**
 * Average Duration Widget - Common Widget
 * 
 * Data Scope:
 * - User: Avg duration from builds in their accessible repos
 * - Admin: Avg duration from all builds
 * 
 * Backend calculates from filtered builds only
 */
export function AvgDurationWidget({ summary, isEditing, className }: BaseWidgetProps) {
  const avgDuration = summary.metrics.average_duration_minutes;

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
          Avg Duration
        </CardTitle>
        <Timer className="h-5 w-5 text-orange-500 flex-shrink-0" />
      </CardHeader>
      <CardContent className="pb-3 px-4 flex-1">
        <div className="text-xl font-bold truncate">
          {formatDuration(avgDuration)}
        </div>
        <p className="text-[10px] text-muted-foreground truncate">
          Average build duration
        </p>
      </CardContent>
    </Card>
  );
}
