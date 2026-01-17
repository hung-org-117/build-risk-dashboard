"use client";

import { GripVertical, TrendingUp } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
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
 * Risk Trend Widget - User Widget
 * 
 * Visualization:
 * - Stacked Bar Chart showing risk levels over time (grouped by date)
 * - X-Axis: Date
 * - Y-Axis: Count of builds
 */
export function RiskTrendWidget({ recentBuilds, isEditing, className }: BaseWidgetProps) {
  // 1. Group builds by Date (YYYY-MM-DD)
  // Sort builds by date ascending first
  const sortedBuilds = [...recentBuilds].sort((a, b) =>
    new Date(a.created_at || "").getTime() - new Date(b.created_at || "").getTime()
  );

  const groupedData: Record<string, { date: string; LOW: number; MEDIUM: number; HIGH: number }> = {};

  sortedBuilds.forEach((b) => {
    if (!b.created_at) return;
    const dateObj = new Date(b.created_at);
    // Format: "Jan 17"
    const dateKey = dateObj.toLocaleDateString("en-US", { month: "short", day: "numeric" });

    if (!groupedData[dateKey]) {
      groupedData[dateKey] = { date: dateKey, LOW: 0, MEDIUM: 0, HIGH: 0 };
    }

    if (b.predicted_label === "LOW") groupedData[dateKey].LOW++;
    else if (b.predicted_label === "MEDIUM") groupedData[dateKey].MEDIUM++;
    else if (b.predicted_label === "HIGH") groupedData[dateKey].HIGH++;
  });

  const chartData = Object.values(groupedData);
  const hasRiskData = chartData.length > 0;

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
          Daily build risk volume (Last 30 Days)
        </CardDescription>
      </CardHeader>
      <CardContent className="h-[calc(100%-60px)] min-h-[160px]">
        {hasRiskData ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-muted" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10 }}
                className="text-muted-foreground"
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fontSize: 10 }}
                className="text-muted-foreground"
                tickLine={false}
                axisLine={false}
                allowDecimals={false}
              />
              <Tooltip
                cursor={{ fill: "transparent" }}
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
              <Bar dataKey="LOW" stackId="a" fill="#16a34a" name="Low" radius={[0, 0, 0, 0]} />
              <Bar dataKey="MEDIUM" stackId="a" fill="#d97706" name="Medium" radius={[0, 0, 0, 0]} />
              <Bar dataKey="HIGH" stackId="a" fill="#dc2626" name="High" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex flex-col items-center justify-center h-full space-y-2">
            <TrendingUp className="h-8 w-8 text-muted-foreground/50" />
            <p className="text-xs text-muted-foreground">No trend data available</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
