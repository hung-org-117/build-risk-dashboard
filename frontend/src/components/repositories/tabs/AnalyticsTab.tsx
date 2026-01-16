"use client";

import { useEffect, useState } from "react";
import {
    AlertCircle,
    CheckCircle2,
    TrendingDown,
    TrendingUp,
    Loader2,
    ShieldCheck,
} from "lucide-react";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { buildApi } from "@/lib/api";
import { useRepo } from "../RepoContext";
import type { UnifiedBuild } from "@/types";
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend,
    PieChart,
    Pie,
    Cell,
} from "recharts";

export function AnalyticsTab() {
    const { repoId, repo } = useRepo();
    const [builds, setBuilds] = useState<UnifiedBuild[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function loadBuilds() {
            try {
                // Load more builds for analytics
                const response = await buildApi.getUnifiedBuilds(repoId, {
                    skip: 0,
                    limit: 100,
                });
                setBuilds(response.items);
            } catch (err) {
                console.error("Failed to load builds for analytics:", err);
            } finally {
                setLoading(false);
            }
        }
        loadBuilds();
    }, [repoId]);

    if (loading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    // Calculate risk statistics
    const buildsWithPredictions = builds.filter((b) => b.predicted_label);
    const riskCounts = { LOW: 0, MEDIUM: 0, HIGH: 0 };
    buildsWithPredictions.forEach((b) => {
        if (b.predicted_label === "LOW") riskCounts.LOW++;
        else if (b.predicted_label === "MEDIUM") riskCounts.MEDIUM++;
        else if (b.predicted_label === "HIGH") riskCounts.HIGH++;
    });

    const totalPredicted = buildsWithPredictions.length;
    const predictionCoverage =
        builds.length > 0 ? (totalPredicted / builds.length) * 100 : 0;

    // Calculate average confidence
    const avgConfidence =
        buildsWithPredictions.length > 0
            ? buildsWithPredictions.reduce(
                (sum, b) => sum + (b.prediction_confidence || 0),
                0
            ) / buildsWithPredictions.length
            : 0;

    // Group builds by date for trend analysis
    const buildsByDate: Record<string, { LOW: number; MEDIUM: number; HIGH: number }> = {};
    buildsWithPredictions.forEach((b) => {
        if (b.created_at) {
            const date = b.created_at.split("T")[0];
            if (!buildsByDate[date]) {
                buildsByDate[date] = { LOW: 0, MEDIUM: 0, HIGH: 0 };
            }
            if (b.predicted_label === "LOW") buildsByDate[date].LOW++;
            else if (b.predicted_label === "MEDIUM") buildsByDate[date].MEDIUM++;
            else if (b.predicted_label === "HIGH") buildsByDate[date].HIGH++;
        }
    });

    // Sort dates and get last 30 days
    const sortedDates = Object.keys(buildsByDate).sort().slice(-30);

    // Calculate risk trend (is it improving or worsening?)
    const recentBuilds = sortedDates.slice(-7);
    const olderBuilds = sortedDates.slice(0, Math.max(0, sortedDates.length - 7));

    const recentHighRisk = recentBuilds.reduce((sum, d) => sum + buildsByDate[d].HIGH, 0);
    const olderHighRisk = olderBuilds.reduce((sum, d) => sum + buildsByDate[d].HIGH, 0);
    const isImproving = recentHighRisk < olderHighRisk;

    // Risk by branch
    const riskByBranch: Record<string, { LOW: number; MEDIUM: number; HIGH: number; total: number }> = {};
    buildsWithPredictions.forEach((b) => {
        const branch = b.branch || "unknown";
        if (!riskByBranch[branch]) {
            riskByBranch[branch] = { LOW: 0, MEDIUM: 0, HIGH: 0, total: 0 };
        }
        if (b.predicted_label === "LOW") riskByBranch[branch].LOW++;
        else if (b.predicted_label === "MEDIUM") riskByBranch[branch].MEDIUM++;
        else if (b.predicted_label === "HIGH") riskByBranch[branch].HIGH++;
        riskByBranch[branch].total++;
    });

    // Get top 5 branches by build count
    const topBranches = Object.entries(riskByBranch)
        .sort((a, b) => b[1].total - a[1].total)
        .slice(0, 5);

    return (
        <div className="space-y-8">
            {/* Key Metrics Row */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <Card className="shadow-sm">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">
                            Prediction Coverage
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">
                            {predictionCoverage.toFixed(1)}%
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                            {totalPredicted} of {builds.length} builds
                        </p>
                    </CardContent>
                </Card>

                <Card className="shadow-sm">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">
                            Average Confidence
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold">
                            {(avgConfidence * 100).toFixed(1)}%
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                            Model prediction certainty
                        </p>
                    </CardContent>
                </Card>

                <Card className={`shadow-sm ${riskCounts.HIGH > 0 ? "border-red-200 bg-red-50/40 dark:border-red-900/50 dark:bg-red-950/20" : ""}`}>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">
                            High Risk Builds
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className={`text-3xl font-bold ${riskCounts.HIGH > 0 ? "text-red-600 dark:text-red-400" : ""}`}>
                            {riskCounts.HIGH}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                            {totalPredicted > 0 ? ((riskCounts.HIGH / totalPredicted) * 100).toFixed(1) : 0}% of predictions
                        </p>
                    </CardContent>
                </Card>

                <Card className="shadow-sm">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">
                            Risk Trend
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-center gap-2">
                            {sortedDates.length >= 2 ? (
                                <>
                                    {isImproving ? (
                                        <div className="bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 px-2 py-1 rounded-full flex items-center gap-1 text-sm font-medium">
                                            <TrendingDown className="h-4 w-4" />
                                            Improving
                                        </div>
                                    ) : (
                                        <div className="bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 px-2 py-1 rounded-full flex items-center gap-1 text-sm font-medium">
                                            <TrendingUp className="h-4 w-4" />
                                            Worsening
                                        </div>
                                    )}
                                </>
                            ) : (
                                <span className="text-muted-foreground text-sm font-medium">Not enough data</span>
                            )}
                        </div>
                        <p className="text-xs text-muted-foreground mt-2">
                            Compared to last 7 days
                        </p>
                    </CardContent>
                </Card>
            </div>

            {/* Risk Distribution & Risk by Branch */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Risk Distribution - Donut Chart */}
                <Card className="shadow-sm">
                    <CardHeader>
                        <CardTitle>Risk Distribution</CardTitle>
                        <CardDescription>Breakdown of predicted risk levels</CardDescription>
                    </CardHeader>
                    <CardContent className="flex flex-col items-center justify-center">
                        {totalPredicted > 0 ? (
                            <div className="w-full h-[250px] relative">
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie
                                            data={[
                                                { name: "Low Risk", value: riskCounts.LOW, color: "#22c55e" },
                                                { name: "Medium Risk", value: riskCounts.MEDIUM, color: "#f59e0b" },
                                                { name: "High Risk", value: riskCounts.HIGH, color: "#ef4444" },
                                            ]}
                                            cx="50%"
                                            cy="50%"
                                            innerRadius={60}
                                            outerRadius={80}
                                            paddingAngle={5}
                                            dataKey="value"
                                        >
                                            <Cell key="cell-0" fill="#22c55e" />
                                            <Cell key="cell-1" fill="#f59e0b" />
                                            <Cell key="cell-2" fill="#ef4444" />
                                        </Pie>
                                        <Tooltip
                                            formatter={(value: number) => [`${value} builds`, 'Count']}
                                            contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                        />
                                        <Legend verticalAlign="bottom" height={36} />
                                    </PieChart>
                                </ResponsiveContainer>
                                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                                    <div className="text-center">
                                        <div className="text-3xl font-bold">{totalPredicted}</div>
                                        <div className="text-xs text-muted-foreground uppercase tracking-wider">Total</div>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center py-12 text-center h-[250px]">
                                <ShieldCheck className="h-12 w-12 text-muted-foreground/30 mb-3" />
                                <p className="text-muted-foreground">No data available</p>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Risk by Branch */}
                <Card className="shadow-sm">
                    <CardHeader>
                        <CardTitle>Risk by Branch</CardTitle>
                        <CardDescription>
                            Top 5 branches by build count with risk breakdown
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        {topBranches.length > 0 ? (
                            <div className="space-y-4">
                                {topBranches.map(([branch, data]) => (
                                    <div key={branch} className="space-y-2">
                                        <div className="flex items-center justify-between">
                                            <span className="text-sm font-medium truncate max-w-[200px]" title={branch}>
                                                {branch}
                                            </span>
                                            <div className="flex items-center gap-2">
                                                <Badge variant="outline" className="border-green-300 text-green-600 text-xs">
                                                    {data.LOW} low
                                                </Badge>
                                                <Badge variant="outline" className="border-amber-300 text-amber-600 text-xs">
                                                    {data.MEDIUM} med
                                                </Badge>
                                                <Badge variant="outline" className="border-red-300 text-red-600 text-xs">
                                                    {data.HIGH} high
                                                </Badge>
                                            </div>
                                        </div>
                                        <div className="flex gap-0.5 h-2 bg-slate-100 dark:bg-slate-800 rounded overflow-hidden">
                                            <div
                                                className="bg-green-500"
                                                style={{ width: `${(data.LOW / data.total) * 100}%` }}
                                            />
                                            <div
                                                className="bg-amber-500"
                                                style={{ width: `${(data.MEDIUM / data.total) * 100}%` }}
                                            />
                                            <div
                                                className="bg-red-500"
                                                style={{ width: `${(data.HIGH / data.total) * 100}%` }}
                                            />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center py-8 text-center">
                                <ShieldCheck className="h-10 w-10 text-muted-foreground/50 mb-3" />
                                <p className="text-muted-foreground">
                                    No branch data available
                                </p>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Risk Over Time */}
            <Card className="shadow-sm">
                <CardHeader>
                    <CardTitle>Risk Over Time</CardTitle>
                    <CardDescription>
                        Build risk levels trends over the last 30 days
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {sortedDates.length > 0 ? (
                        <ResponsiveContainer width="100%" height={300}>
                            <AreaChart
                                data={sortedDates.map((date) => ({
                                    date: new Date(date).toLocaleDateString("vi-VN", { month: "2-digit", day: "2-digit" }),
                                    LOW: buildsByDate[date].LOW,
                                    MEDIUM: buildsByDate[date].MEDIUM,
                                    HIGH: buildsByDate[date].HIGH,
                                }))}
                                margin={{ top: 10, right: 30, left: 20, bottom: 20 }}
                            >
                                <defs>
                                    <linearGradient id="colorLow" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#22c55e" stopOpacity={0.8} />
                                        <stop offset="95%" stopColor="#22c55e" stopOpacity={0.1} />
                                    </linearGradient>
                                    <linearGradient id="colorMed" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.8} />
                                        <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.1} />
                                    </linearGradient>
                                    <linearGradient id="colorHigh" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#ef4444" stopOpacity={0.8} />
                                        <stop offset="95%" stopColor="#ef4444" stopOpacity={0.1} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" vertical={true} horizontal={true} stroke="#e5e7eb" />
                                <XAxis
                                    dataKey="date"
                                    tick={{ fontSize: 11 }}
                                    className="text-muted-foreground"
                                    axisLine={false}
                                    tickLine={false}
                                    dy={10}
                                    label={{ value: 'Date', position: 'insideBottom', offset: -5, className: 'text-xs fill-muted-foreground' }}
                                />
                                <YAxis
                                    tick={{ fontSize: 11 }}
                                    className="text-muted-foreground"
                                    allowDecimals={false}
                                    axisLine={false}
                                    tickLine={false}
                                    label={{ value: 'Build Count', angle: -90, position: 'insideLeft', className: 'text-xs fill-muted-foreground' }}
                                />
                                <Tooltip
                                    contentStyle={{
                                        backgroundColor: "hsl(var(--popover))",
                                        border: "none",
                                        borderRadius: "8px",
                                        fontSize: "12px",
                                        boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                                    }}
                                />
                                <Legend iconType="circle" />
                                <Area
                                    type="monotone"
                                    dataKey="LOW"
                                    stackId="1"
                                    stroke="#22c55e"
                                    fill="url(#colorLow)"
                                    name="Low Risk"
                                />
                                <Area
                                    type="monotone"
                                    dataKey="MEDIUM"
                                    stackId="1"
                                    stroke="#f59e0b"
                                    fill="url(#colorMed)"
                                    name="Medium Risk"
                                />
                                <Area
                                    type="monotone"
                                    dataKey="HIGH"
                                    stackId="1"
                                    stroke="#ef4444"
                                    fill="url(#colorHigh)"
                                    name="High Risk"
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="flex flex-col items-center justify-center py-12 text-center">
                            <ShieldCheck className="h-10 w-10 text-muted-foreground/50 mb-3" />
                            <p className="text-muted-foreground">
                                No time-series data available
                            </p>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Recent Build Analysis Table */}
            <Card className="shadow-sm overflow-hidden">
                <CardHeader>
                    <CardTitle>Recent Build Analysis</CardTitle>
                    <CardDescription>
                        Detailed risk evaluation for recent builds
                    </CardDescription>
                </CardHeader>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-slate-50 dark:bg-slate-900 border-b">
                            <tr>
                                <th className="px-6 py-3 font-medium text-muted-foreground">Build #</th>
                                <th className="px-6 py-3 font-medium text-muted-foreground">Commit</th>
                                <th className="px-6 py-3 font-medium text-muted-foreground">Branch</th>
                                <th className="px-6 py-3 font-medium text-muted-foreground">Risk Level</th>
                                <th className="px-6 py-3 font-medium text-muted-foreground">Confidence</th>
                                <th className="px-6 py-3 font-medium text-muted-foreground">Uncertainty</th>
                                <th className="px-6 py-3 font-medium text-muted-foreground">Created At</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y">
                            {buildsWithPredictions.slice(0, 10).map((build) => (
                                <tr
                                    key={build.model_import_build_id}
                                    className={`group hover:bg-slate-50 dark:hover:bg-slate-900/50 transition-colors ${build.predicted_label === 'HIGH' ? 'border-l-4 border-l-red-500 bg-red-50/10' : 'border-l-4 border-l-transparent'
                                        }`}
                                >
                                    <td className="px-6 py-4 font-medium">{build.build_number || "-"}</td>
                                    <td className="px-6 py-4">
                                        <a
                                            href={build.web_url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="font-mono text-blue-600 hover:underline dark:text-blue-400"
                                        >
                                            {build.commit_sha?.substring(0, 7) || "unknown"}
                                        </a>
                                    </td>
                                    <td className="px-6 py-4">
                                        <Badge variant="outline" className="font-normal text-xs">
                                            {build.branch || "main"}
                                        </Badge>
                                    </td>
                                    <td className="px-6 py-4">
                                        <Badge className={`font-normal ${build.predicted_label === 'LOW' ? 'bg-green-100 text-green-700 hover:bg-green-100 dark:bg-green-900/30 dark:text-green-400' :
                                            build.predicted_label === 'MEDIUM' ? 'bg-amber-100 text-amber-700 hover:bg-amber-100 dark:bg-amber-900/30 dark:text-amber-400' :
                                                'bg-red-100 text-red-700 hover:bg-red-100 dark:bg-red-900/30 dark:text-red-400'
                                            }`}>
                                            {build.predicted_label || "UNKNOWN"}
                                        </Badge>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-2">
                                            <span className="w-8 text-right font-mono">
                                                {Math.round((build.prediction_confidence || 0) * 100)}%
                                            </span>
                                            <div className="w-16 h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                                                <div
                                                    className={`h-full rounded-full ${(build.prediction_confidence || 0) > 0.8 ? 'bg-green-500' :
                                                        (build.prediction_confidence || 0) > 0.5 ? 'bg-amber-500' : 'bg-red-500'
                                                        }`}
                                                    style={{ width: `${(build.prediction_confidence || 0) * 100}%` }}
                                                />
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 text-muted-foreground">
                                        {Math.round((build.prediction_uncertainty || 0) * 100)}%
                                    </td>
                                    <td className="px-6 py-4 text-muted-foreground text-sm">
                                        {build.created_at ? new Date(build.created_at).toLocaleDateString() : "-"}
                                    </td>
                                </tr>
                            ))}
                            {buildsWithPredictions.length === 0 && (
                                <tr>
                                    <td colSpan={7} className="px-6 py-12 text-center text-muted-foreground">
                                        No analysed builds found
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </Card>


        </div>
    );
}
