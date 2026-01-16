"use client";

import { useMemo } from "react";
import {
    Bar,
    BarChart,
    CartesianGrid,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NumericDistribution } from "@/lib/api/statistics";

interface FeatureDistributionChartProps {
    featureName: string;
    distribution: NumericDistribution;
}

export function FeatureDistributionChart({
    featureName,
    distribution,
}: FeatureDistributionChartProps) {
    const chartData = useMemo(() => {
        return distribution.bins.map((bin) => ({
            name: `${bin.min_value.toFixed(1)}-${bin.max_value.toFixed(1)}`,
            count: bin.count,
            min: bin.min_value,
            max: bin.max_value,
        }));
    }, [distribution.bins]);

    const stats = distribution.stats;

    return (
        <Card className="flex flex-col h-full">
            <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-base font-medium truncate" title={featureName}>
                        {featureName}
                    </CardTitle>
                    <CardDescription className="font-mono text-xs">
                        {distribution.data_type}
                    </CardDescription>
                </div>
            </CardHeader>
            <CardContent className="flex-1 pb-2">
                <div className="h-[200px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.5} />
                            <XAxis
                                dataKey="name"
                                stroke="#888888"
                                fontSize={10}
                                tickLine={false}
                                axisLine={false}
                                tickFormatter={(value, index) => {
                                    // Show only first, middle, last ticks to avoid clutter
                                    if (index === 0 || index === chartData.length - 1 || index === Math.floor(chartData.length / 2)) {
                                        return value;
                                    }
                                    return "";
                                }}
                            />
                            <YAxis
                                stroke="#888888"
                                fontSize={10}
                                tickLine={false}
                                axisLine={false}
                                allowDecimals={false}
                            />
                            <Tooltip
                                cursor={{ fill: "hsl(var(--muted))", opacity: 0.2 }}
                                content={({ active, payload, label }) => {
                                    if (active && payload && payload.length) {
                                        return (
                                            <div className="rounded-lg border bg-background p-2 shadow-sm">
                                                <div className="grid grid-cols-2 gap-2">
                                                    <div className="flex flex-col">
                                                        <span className="text-[0.70rem] uppercase text-muted-foreground">
                                                            Range
                                                        </span>
                                                        <span className="font-bold text-muted-foreground">
                                                            {label}
                                                        </span>
                                                    </div>
                                                    <div className="flex flex-col">
                                                        <span className="text-[0.70rem] uppercase text-muted-foreground">
                                                            Count
                                                        </span>
                                                        <span className="font-bold">
                                                            {payload[0].value}
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    }
                                    return null;
                                }}
                            />
                            <Bar
                                dataKey="count"
                                fill="currentColor"
                                radius={[4, 4, 0, 0]}
                                className="fill-blue-600"
                            />
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                {stats && (
                    <div className="mt-4 grid grid-cols-4 gap-2 text-xs border-t pt-2">
                        <div className="flex flex-col">
                            <span className="text-muted-foreground">Min</span>
                            <span className="font-mono font-medium">{stats.min.toFixed(2)}</span>
                        </div>
                        <div className="flex flex-col">
                            <span className="text-muted-foreground">Max</span>
                            <span className="font-mono font-medium">{stats.max.toFixed(2)}</span>
                        </div>
                        <div className="flex flex-col">
                            <span className="text-muted-foreground">Mean</span>
                            <span className="font-mono font-medium">{stats.mean.toFixed(2)}</span>
                        </div>
                        <div className="flex flex-col">
                            <span className="text-muted-foreground">Std</span>
                            <span className="font-mono font-medium">{stats.std.toFixed(2)}</span>
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
