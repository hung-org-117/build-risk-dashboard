"use client";

import { GitBranch, GripVertical } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { BaseWidgetProps } from "../../types";

/**
 * Active Repos Widget - Common Widget
 * 
 * Data Scope:
 * - User: Count of repos they have access to (github_accessible_repos)
 * - Admin: Count of all repos
 * 
 * Backend filtering in dashboard_service.py:
 * - active_repos = len(repos_map) where repos are pre-filtered by RBAC
 */
export function ActiveReposWidget({ summary, isEditing, className }: BaseWidgetProps) {
  const activeRepos = summary.active_repos;

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
          Active Repos
        </CardTitle>
        <GitBranch className="h-5 w-5 text-purple-500 flex-shrink-0" />
      </CardHeader>
      <CardContent className="pb-3 px-4 flex-1">
        <div className="text-xl font-bold truncate">
          {activeRepos}
        </div>
        <p className="text-[10px] text-muted-foreground truncate">
          Connected via GitHub
        </p>
      </CardContent>
    </Card>
  );
}
