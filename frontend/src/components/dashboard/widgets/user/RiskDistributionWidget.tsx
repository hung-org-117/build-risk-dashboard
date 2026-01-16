"use client";

import { ShieldCheck, GripVertical } from "lucide-react";
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
 * Risk Distribution Widget - User Widget
 * 
 * Data Scope:
 * - User: Risk distribution from builds in their accessible repos
 * - Admin: Risk distribution from all builds
 * 
 * Calculation:
 * - Uses recentBuilds from get_recent_builds() which is RBAC-filtered
 * - Counts LOW/MEDIUM/HIGH predictions
 */
export function RiskDistributionWidget({ recentBuilds, isEditing, className }: BaseWidgetProps) {
  // Calculate risk counts from filtered recent builds
  const distCounts = { LOW: 0, MEDIUM: 0, HIGH: 0 };
  recentBuilds.forEach((b) => {
    if (b.predicted_label === "LOW") distCounts.LOW++;
    else if (b.predicted_label === "MEDIUM") distCounts.MEDIUM++;
    else if (b.predicted_label === "HIGH") distCounts.HIGH++;
  });
  const totalPredicted = distCounts.LOW + distCounts.MEDIUM + distCounts.HIGH;

  return (
    <Card className={cn("h-full overflow-hidden", isEditing && "ring-2 ring-blue-500/20 cursor-move", className)}>
      {isEditing && (
        <div className="absolute top-2 left-2 z-10">
          <GripVertical className="h-4 w-4 text-muted-foreground" />
        </div>
      )}
      <CardHeader className="pb-2">
        <CardTitle className="text-sm truncate">Risk Distribution</CardTitle>
        <CardDescription className="text-xs truncate">
          Risk level breakdown
        </CardDescription>
      </CardHeader>
      <CardContent className="flex items-center justify-center h-[calc(100%-60px)]">
        {totalPredicted > 0 ? (
          <div className="flex items-center gap-4">
            <div className="flex flex-col items-center">
              <div className="text-2xl font-bold text-green-600">{distCounts.LOW}</div>
              <div className="text-xs text-muted-foreground">Low</div>
            </div>
            <div className="flex flex-col items-center">
              <div className="text-2xl font-bold text-amber-600">{distCounts.MEDIUM}</div>
              <div className="text-xs text-muted-foreground">Medium</div>
            </div>
            <div className="flex flex-col items-center">
              <div className="text-2xl font-bold text-red-600">{distCounts.HIGH}</div>
              <div className="text-xs text-muted-foreground">High</div>
            </div>
          </div>
        ) : (
          <div className="text-center space-y-2">
            <ShieldCheck className="h-8 w-8 mx-auto text-muted-foreground/50" />
            <p className="text-xs text-muted-foreground">No predictions yet</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
