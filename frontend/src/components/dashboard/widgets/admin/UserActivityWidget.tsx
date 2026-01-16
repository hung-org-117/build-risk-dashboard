"use client";

import { Users, GripVertical } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { BaseWidgetProps } from "../../types";

/**
 * User Activity Widget - Admin-Only Widget
 * 
 * Data Scope:
 * - ADMIN ONLY: Requires summary.admin_extras.total_users
 * - Shows total registered users in system
 * - NULL for non-admin users
 * 
 * Backend guarantee:
 * - admin_extras.total_users only for admins
 * - Count from users collection
 */
export function UserActivityWidget({ summary, isEditing, className }: BaseWidgetProps) {
  const totalUsers = summary?.admin_extras?.total_users ?? 0;

  if (!summary?.admin_extras) {
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
          User Activity
        </CardTitle>
        <Users className="h-5 w-5 text-indigo-500 flex-shrink-0" />
      </CardHeader>
      <CardContent className="pb-3 px-4 flex-1">
        <div className="text-xl font-bold truncate">
          {totalUsers}
        </div>
        <p className="text-[10px] text-muted-foreground truncate">
          Registered users
        </p>
      </CardContent>
    </Card>
  );
}
