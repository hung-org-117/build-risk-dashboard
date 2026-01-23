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
 * Recent Builds Widget - Common Widget
 * 
 * Data Scope:
 * - User: Only shows recent builds from repos in github_accessible_repos
 * - Admin: Shows recent builds from all repos
 * 
 * Backend filtering in model_build_service.py get_recent_builds():
 * - For user: repo_filter["full_name"] = {"$in": accessible_repos}
 * - For admin: No repo filter (all repos)
 * - Query limited to model_repo_configs that match filter
 */
export function RecentBuildsWidget({ recentBuilds, isEditing, className }: BaseWidgetProps) {
  return (
    <Card className={cn("h-full overflow-hidden", isEditing && "ring-2 ring-blue-500/20 cursor-move", className)}>
      {isEditing && (
        <div className="absolute top-2 left-2 z-10">
          <GripVertical className="h-4 w-4 text-muted-foreground" />
        </div>
      )}
      <CardHeader className="pb-2">
        <CardTitle className="text-sm truncate">Recent Builds</CardTitle>
        <CardDescription className="text-xs truncate">
          Latest builds from repositories
        </CardDescription>
      </CardHeader>
      <CardContent className="p-0 overflow-auto flex-1">
        <table className="min-w-full divide-y divide-slate-200 text-xs dark:divide-slate-800">
          <thead className="bg-slate-50 dark:bg-slate-900/40">
            <tr>
              <th className="px-3 py-2 text-left font-semibold">Build</th>
              <th className="px-3 py-2 text-left font-semibold">Repo</th>
              <th className="px-3 py-2 text-left font-semibold">Risk</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
            {recentBuilds.length === 0 ? (
              <tr>
                <td className="px-3 py-4 text-center text-muted-foreground" colSpan={3}>
                  No recent builds.
                </td>
              </tr>
            ) : (
              recentBuilds.slice(0, 5).map((build, index) => (
                <tr
                  key={build.id || `build-${index}`}
                  className="transition hover:bg-slate-50 dark:hover:bg-slate-900/50"
                >
                  <td className="px-3 py-2 font-medium truncate max-w-[80px]">
                    #{build.build_number || build.commit_sha?.slice(0, 7) || "—"}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground truncate max-w-[120px]" title={build.repo_name}>
                    {build.repo_name || "—"}
                  </td>
                  <td className="px-3 py-2">
                    {build.predicted_label ? (
                      <span className={cn(
                        "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium",
                        build.predicted_label === "LOW" && "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
                        build.predicted_label === "MEDIUM" && "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
                        build.predicted_label === "HIGH" && "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
                        !["LOW", "MEDIUM", "HIGH"].includes(build.predicted_label) && "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400"
                      )}>
                        {build.predicted_label}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
