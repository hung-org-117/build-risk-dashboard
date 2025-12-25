"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
} from "recharts";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface MetricsBucket {
    timestamp: string;
    ERROR: number;
    WARNING: number;
    INFO: number;
    DEBUG: number;
}

interface MetricsData {
    time_buckets: MetricsBucket[];
    level_totals: {
        ERROR: number;
        WARNING: number;
        INFO: number;
        DEBUG: number;
    };
    hours: number;
    bucket_minutes: number;
}

interface MetricsChartProps {
    className?: string;
}

export function MetricsChart({ className }: MetricsChartProps) {
    const [metricsData, setMetricsData] = useState<MetricsData | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [hours, setHours] = useState("24");

    const fetchMetrics = useCallback(async () => {
        try {
            const res = await fetch(
                `${API_BASE}/monitoring/metrics?hours=${hours}&bucket_minutes=60`,
                { credentials: "include" }
            );
            if (res.ok) {
                const data = await res.json();
                setMetricsData(data);
            }
        } catch (error) {
            console.error("Failed to fetch metrics:", error);
        } finally {
            setIsLoading(false);
        }
    }, [hours]);

    useEffect(() => {
        fetchMetrics();
    }, [fetchMetrics]);

    const formatTime = (timestamp: string) => {
        const date = new Date(timestamp);
        return date.toLocaleTimeString("en-US", {
            hour: "2-digit",
            minute: "2-digit",
        });
    };

    const chartData = metricsData?.time_buckets.map((bucket) => ({
        ...bucket,
        time: formatTime(bucket.timestamp),
    })) || [];

    return (
        <Card className={className}>
            <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">Log Metrics</CardTitle>
                    <div className="flex items-center gap-4">
                        {metricsData && (
                            <div className="flex items-center gap-2">
                                <Badge variant="destructive">
                                    {metricsData.level_totals.ERROR} errors
                                </Badge>
                                <Badge variant="secondary" className="bg-yellow-100 text-yellow-800">
                                    {metricsData.level_totals.WARNING} warnings
                                </Badge>
                            </div>
                        )}
                        <Select value={hours} onValueChange={setHours}>
                            <SelectTrigger className="w-[120px]">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="6">Last 6h</SelectItem>
                                <SelectItem value="24">Last 24h</SelectItem>
                                <SelectItem value="48">Last 48h</SelectItem>
                                <SelectItem value="168">Last 7d</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                {isLoading ? (
                    <div className="h-[250px] flex items-center justify-center text-muted-foreground">
                        Loading metrics...
                    </div>
                ) : chartData.length === 0 ? (
                    <div className="h-[250px] flex items-center justify-center text-muted-foreground">
                        No log data available for selected period
                    </div>
                ) : (
                    <ResponsiveContainer width="100%" height={250}>
                        <LineChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                            <XAxis
                                dataKey="time"
                                tick={{ fontSize: 12 }}
                                className="text-muted-foreground"
                            />
                            <YAxis
                                tick={{ fontSize: 12 }}
                                className="text-muted-foreground"
                            />
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: "hsl(var(--popover))",
                                    border: "1px solid hsl(var(--border))",
                                    borderRadius: "8px",
                                }}
                            />
                            <Legend />
                            <Line
                                type="monotone"
                                dataKey="ERROR"
                                stroke="#ef4444"
                                strokeWidth={2}
                                dot={false}
                                name="Errors"
                            />
                            <Line
                                type="monotone"
                                dataKey="WARNING"
                                stroke="#eab308"
                                strokeWidth={2}
                                dot={false}
                                name="Warnings"
                            />
                        </LineChart>
                    </ResponsiveContainer>
                )}
            </CardContent>
        </Card>
    );
}
