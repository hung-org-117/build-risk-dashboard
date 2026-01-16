"use client";

import { GripVertical } from "lucide-react";
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
 * Risk Trend Widget - User Widget
 * 
 * Data Scope:
 * - User: Risk trend from builds in their accessible repos
 * - Admin: Risk trend from all builds
 * 
 * Uses RBAC-filtered recentBuilds to show horizontal bar chart
 */
export function RiskTrendWidget({ recentBuilds, isEditing, className }: BaseWidgetProps) {
  // Calculate risk counts
  const riskCounts = { LOW: 0, MEDIUM: 0, HIGH: 0 };
  recentBuilds.forEach((b) => {
    if (b.predicted_label === "LOW") riskCounts.LOW++;
    else if (b.predicted_label === "MEDIUM") riskCounts.MEDIUM++;
    else if (b.predicted_label === "HIGH") riskCounts.HIGH++;
  });
  const hasRiskData = riskCounts.LOW + riskCounts.MEDIUM + riskCounts.HIGH > 0;

  return (
    <Card className={cn("h-full overflow-hidden", isEditing && "ring-2 ring-blue-500/20 cursor-move", className)}>
      {isEditing && (
        <div className="absolute top-2 left-2 z-10">
          <GripVertical className="h-4 w-4 text-muted-foreground" />
        </div>
      )}
      <CardHeader className="pb-2">
        <CardTitle className="text-sm truncate">Risk Trend</CardTitle>
        <CardDescription className="text-xs truncate">
          Recent build risk levels
        </CardDescription>
      </CardHeader>
      <CardContent className="flex items-center justify-center h-[calc(100%-60px)]">
        {hasRiskData ? (
          <div className="w-full space-y-2 px-2">
            <div className="flex items-center gap-2">
              <span className="text-xs w-12">LOW</span>
              <div className="flex-1 h-4 bg-slate-100 dark:bg-slate-800 rounded overflow-hidden">
                <div
                  className="h-full bg-green-500"
                  style={{ width: `${(riskCounts.LOW / recentBuilds.length) * 100}%` }}
                />
              </div>
              <span className="text-xs w-6 text-right">{riskCounts.LOW}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs w-12">MED</span>
              <div className="flex-1 h-4 bg-slate-100 dark:bg-slate-800 rounded overflow-hidden">
                <div
                  className="h-full bg-amber-500"
                  style={{ width: `${(riskCounts.MEDIUM / recentBuilds.length) * 100}%` }}
                />
              </div>
              <span className="text-xs w-6 text-right">{riskCounts.MEDIUM}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs w-12">HIGH</span>
              <div className="flex-1 h-4 bg-slate-100 dark:bg-slate-800 rounded overflow-hidden">
                <div
                  className="h-full bg-red-500"
                  style={{ width: `${(riskCounts.HIGH / recentBuilds.length) * 100}%` }}
                />
              </div>
              <span className="text-xs w-6 text-right">{riskCounts.HIGH}</span>
            </div>
          </div>
        ) : (
          <div className="text-center space-y-2">
            <p className="text-xs text-muted-foreground">
              No prediction data available
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
