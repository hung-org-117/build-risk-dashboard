"use client";

import { GripVertical } from "lucide-react";
import { useRouter } from "next/navigation";
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
 * Repo Distribution Widget - Common Widget
 * 
 * Data Scope:
 * - User: Only shows repos from github_accessible_repos with build counts
 * - Admin: Shows all repos with build counts
 * 
 * Backend filters in dashboard_service.py:
 * - _calculate_repo_distribution() uses pre-filtered repos_map
 * - repos_map contains only accessible repos for the user
 */
export function RepoDistributionWidget({ summary, isEditing, className }: BaseWidgetProps) {
  const router = useRouter();
  const repoDistribution = summary.repo_distribution || [];

  return (
    <Card className={cn("h-full overflow-hidden", isEditing && "ring-2 ring-blue-500/20 cursor-move", className)}>
      {isEditing && (
        <div className="absolute top-2 left-2 z-10">
          <GripVertical className="h-4 w-4 text-muted-foreground" />
        </div>
      )}
      <CardHeader className="pb-2">
        <CardTitle className="text-sm truncate">Repository Distribution</CardTitle>
        <CardDescription className="text-xs truncate">
          Build count per repository
        </CardDescription>
      </CardHeader>
      <CardContent className="p-0 overflow-auto flex-1">
        <table className="min-w-full divide-y divide-slate-200 text-xs dark:divide-slate-800">
          <thead className="bg-slate-50 dark:bg-slate-900/40">
            <tr>
              <th className="px-3 py-2 text-left font-semibold">Repository</th>
              <th className="px-3 py-2 text-left font-semibold">Builds</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
            {repoDistribution.length === 0 ? (
              <tr>
                <td className="px-3 py-4 text-center text-muted-foreground" colSpan={2}>
                  No repositories connected yet.
                </td>
              </tr>
            ) : (
              repoDistribution.slice(0, 5).map((repo) => (
                <tr
                  key={repo.id}
                  className="cursor-pointer transition hover:bg-slate-50 dark:hover:bg-slate-900/50"
                  onClick={() => !isEditing && router.push(`/repositories/${repo.id}/builds`)}
                >
                  <td className="px-3 py-2 font-medium truncate max-w-[150px]">
                    {repo.repository}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {repo.builds.toLocaleString()}
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
