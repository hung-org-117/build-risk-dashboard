"use client";

import { Workflow, GripVertical } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { BaseWidgetProps } from "../../types";

/**
 * Total Builds Widget - Common Widget
 * 
 * Data Scope:
 * - User: Total builds from repos in their github_accessible_repos
 * - Admin: Total builds from all repos
 * 
 * Backend filters in dashboard_service.py:
 * - User: repo_filter["full_name"] = {"$in": accessible_repos}
 * - Admin: All repos
 */
export function TotalBuildsWidget({ summary, isEditing, className }: BaseWidgetProps) {
  const totalBuilds = summary.metrics.total_builds;

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
          Total Builds
        </CardTitle>
        <Workflow className="h-5 w-5 text-blue-500 flex-shrink-0" />
      </CardHeader>
      <CardContent className="pb-3 px-4 flex-1">
        <div className="text-xl font-bold truncate">
          {totalBuilds.toLocaleString()}
        </div>
        <p className="text-[10px] text-muted-foreground truncate">
          All tracked builds
        </p>
      </CardContent>
    </Card>
  );
}
