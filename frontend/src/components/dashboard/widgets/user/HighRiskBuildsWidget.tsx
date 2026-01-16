"use client";

import { ShieldCheck, GripVertical } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { BaseWidgetProps } from "../../types";

/**
 * High Risk Builds Widget - User Widget
 * 
 * Data Scope:
 * - User: High risk count from builds in their accessible repos
 * - Admin: High risk count from all builds
 * 
 * Highlights count of HIGH risk predictions from filtered data
 */
export function HighRiskBuildsWidget({ recentBuilds, isEditing, className }: BaseWidgetProps) {
  const highRiskCount = recentBuilds.filter((b) => b.predicted_label === "HIGH").length;

  return (
    <Card className={cn(
      "relative flex flex-col",
      highRiskCount > 0 && "border-red-200 bg-red-50/50 dark:border-red-800 dark:bg-red-900/20",
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
          High Risk Builds
        </CardTitle>
        <ShieldCheck className={cn(
          "h-5 w-5 flex-shrink-0",
          highRiskCount > 0 ? "text-red-500" : "text-muted-foreground"
        )} />
      </CardHeader>
      <CardContent className="pb-3 px-4 flex-1">
        <div className="text-xl font-bold truncate">
          {highRiskCount}
        </div>
        <p className="text-[10px] text-muted-foreground truncate">
          Predicted as HIGH risk
        </p>
      </CardContent>
    </Card>
  );
}
