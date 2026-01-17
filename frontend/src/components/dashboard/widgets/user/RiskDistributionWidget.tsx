"use client";

import { ShieldCheck, GripVertical } from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts";
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

  const data = [
    { name: "Low", value: distCounts.LOW, color: "#16a34a" }, // green-600
    { name: "Medium", value: distCounts.MEDIUM, color: "#d97706" }, // amber-600
    { name: "High", value: distCounts.HIGH, color: "#dc2626" }, // red-600
  ].filter(d => d.value > 0);

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
      <CardContent className="h-[calc(100%-60px)] min-h-[160px]">
        {totalPredicted > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={60}
                paddingAngle={2}
                dataKey="value"
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} strokeWidth={0} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--popover))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
                itemStyle={{ color: "hsl(var(--popover-foreground))" }}
              />
              <Legend
                verticalAlign="bottom"
                height={36}
                iconType="circle"
                wrapperStyle={{ fontSize: "11px", paddingTop: "10px" }}
              />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex flex-col items-center justify-center h-full space-y-2">
            <ShieldCheck className="h-8 w-8 text-muted-foreground/50" />
            <p className="text-xs text-muted-foreground">No predictions yet</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

