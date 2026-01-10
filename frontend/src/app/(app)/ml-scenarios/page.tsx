"use client";

import {
    Beaker,
    Loader2,
    Trash2,
    Plus,
    RefreshCw,
    Play,
    Download,
    FileCode,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/use-toast";
import { useDebounce } from "@/hooks/use-debounce";
import { mlScenariosApi, type MLScenarioRecord, type MLScenarioStatus } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";

function formatNumber(value: number) {
    return value.toLocaleString("en-US");
}

const PAGE_SIZE = 20;

// Status badge component
function ScenarioStatusBadge({ status }: { status: MLScenarioStatus }) {
    const config: Record<MLScenarioStatus, { variant: "default" | "secondary" | "destructive" | "outline"; className: string; label: string }> = {
        queued: { variant: "outline", className: "border-slate-400 text-slate-500", label: "Queued" },
        filtering: { variant: "outline", className: "border-blue-500 text-blue-600", label: "Filtering..." },
        ingesting: { variant: "outline", className: "border-blue-500 text-blue-600", label: "Ingesting..." },
        processing: { variant: "outline", className: "border-purple-500 text-purple-600", label: "Processing..." },
        splitting: { variant: "outline", className: "border-orange-500 text-orange-600", label: "Splitting..." },
        completed: { variant: "outline", className: "border-green-500 text-green-600", label: "Completed" },
        failed: { variant: "destructive", className: "", label: "Failed" },
    };

    const { variant, className, label } = config[status] || config.queued;

    return (
        <Badge variant={variant} className={className}>
            {label}
        </Badge>
    );
}

export default function MLScenariosPage() {
    const router = useRouter();
    const [scenarios, setScenarios] = useState<MLScenarioRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [tableLoading, setTableLoading] = useState(false);

    // Search and pagination
    const [searchQuery, setSearchQuery] = useState("");
    const debouncedSearchQuery = useDebounce(searchQuery, 500);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);

    const loadScenarios = useCallback(
        async (pageNumber = 1, withSpinner = false) => {
            if (withSpinner) {
                setTableLoading(true);
            }
            try {
                const data = await mlScenariosApi.list({
                    skip: (pageNumber - 1) * PAGE_SIZE,
                    limit: PAGE_SIZE,
                    q: debouncedSearchQuery || undefined,
                });
                setScenarios(data.items || []);
                setTotal(data.total);
                setPage(pageNumber);
            } catch (err) {
                console.error(err);
                toast({
                    title: "Error",
                    description: "Failed to load scenarios",
                    variant: "destructive",
                });
            } finally {
                setLoading(false);
                setTableLoading(false);
            }
        },
        [debouncedSearchQuery]
    );

    useEffect(() => {
        loadScenarios(1, true);
    }, [loadScenarios]);

    const totalPages = total > 0 ? Math.ceil(total / PAGE_SIZE) : 1;
    const pageStart = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
    const pageEnd = total === 0 ? 0 : Math.min(page * PAGE_SIZE, total);

    const handlePageChange = (direction: "prev" | "next") => {
        const targetPage =
            direction === "prev"
                ? Math.max(1, page - 1)
                : Math.min(totalPages, page + 1);
        if (targetPage !== page) {
            void loadScenarios(targetPage, true);
        }
    };

    const handleDelete = async (scenario: MLScenarioRecord) => {
        if (!confirm(`Delete scenario "${scenario.name}"? This cannot be undone.`)) {
            return;
        }
        try {
            await mlScenariosApi.delete(scenario.id);
            toast({ title: "Deleted", description: `Scenario "${scenario.name}" deleted.` });
            loadScenarios(page, true);
        } catch (err) {
            console.error(err);
            toast({
                title: "Error",
                description: "Failed to delete scenario",
                variant: "destructive",
            });
        }
    };

    const handleStartGeneration = async (scenario: MLScenarioRecord) => {
        try {
            const result = await mlScenariosApi.startGeneration(scenario.id);
            toast({
                title: "Started",
                description: result.message,
            });
            loadScenarios(page, true);
        } catch (err) {
            console.error(err);
            toast({
                title: "Error",
                description: "Failed to start generation",
                variant: "destructive",
            });
        }
    };

    if (loading) {
        return (
            <div className="flex min-h-[60vh] items-center justify-center">
                <Card className="w-full max-w-md">
                    <CardHeader>
                        <CardTitle>Loading scenarios...</CardTitle>
                        <CardDescription>Fetching your ML scenarios.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header Card */}
            <Card>
                <CardHeader className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                        <CardTitle className="flex items-center gap-2">
                            <Beaker className="h-5 w-5" />
                            ML Scenario Builder
                        </CardTitle>
                        <CardDescription>
                            Create train/validation/test splits using YAML configuration.
                        </CardDescription>
                    </div>
                    <Button onClick={() => router.push("/ml-scenarios/create")} className="gap-2">
                        <Plus className="h-4 w-4" /> Create Scenario
                    </Button>
                </CardHeader>
            </Card>

            {/* Scenarios Table */}
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle>Scenarios</CardTitle>
                            <CardDescription>
                                Manage your ML dataset scenarios
                            </CardDescription>
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="relative w-64">
                                <Input
                                    placeholder="Search scenarios..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    className="h-9"
                                />
                            </div>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => loadScenarios(page, true)}
                                disabled={tableLoading}
                            >
                                <RefreshCw className={`h-4 w-4 mr-1 ${tableLoading ? "animate-spin" : ""}`} />
                                Refresh
                            </Button>
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="p-0">
                    <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                            <thead className="bg-slate-50 dark:bg-slate-900/40">
                                <tr>
                                    <th className="px-6 py-3 text-left font-semibold text-slate-500">
                                        Scenario Name
                                    </th>
                                    <th className="px-6 py-3 text-left font-semibold text-slate-500">
                                        Status
                                    </th>
                                    <th className="px-6 py-3 text-left font-semibold text-slate-500">
                                        Builds
                                    </th>
                                    <th className="px-6 py-3 text-left font-semibold text-slate-500">
                                        Splits
                                    </th>
                                    <th className="px-6 py-3 text-left font-semibold text-slate-500">
                                        Strategy
                                    </th>
                                    <th className="px-6 py-3 text-left font-semibold text-slate-500">
                                        Created
                                    </th>
                                    <th className="px-6 py-3" />
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                                {scenarios.length === 0 ? (
                                    <tr>
                                        <td
                                            colSpan={7}
                                            className="px-6 py-12 text-center text-muted-foreground"
                                        >
                                            <div className="flex flex-col items-center gap-3">
                                                <Beaker className="h-12 w-12 text-slate-300" />
                                                <p>No scenarios created yet.</p>
                                                <Button
                                                    variant="outline"
                                                    onClick={() => router.push("/ml-scenarios/create")}
                                                >
                                                    <Plus className="mr-2 h-4 w-4" /> Create Scenario
                                                </Button>
                                            </div>
                                        </td>
                                    </tr>
                                ) : (
                                    scenarios.map((scenario) => (
                                        <tr
                                            key={scenario.id}
                                            className="cursor-pointer transition hover:bg-slate-50 dark:hover:bg-slate-900/40"
                                            onClick={() => router.push(`/ml-scenarios/${scenario.id}`)}
                                        >
                                            <td className="px-6 py-4">
                                                <div>
                                                    <p className="font-medium text-foreground">{scenario.name}</p>
                                                    {scenario.description && (
                                                        <p className="text-xs text-muted-foreground truncate max-w-[200px]">
                                                            {scenario.description}
                                                        </p>
                                                    )}
                                                </div>
                                            </td>
                                            <td className="px-6 py-4">
                                                <ScenarioStatusBadge status={scenario.status} />
                                            </td>
                                            <td className="px-6 py-4 text-muted-foreground">
                                                {formatNumber(scenario.builds_total)}
                                            </td>
                                            <td className="px-6 py-4 text-muted-foreground">
                                                {scenario.status === "completed" ? (
                                                    <span className="text-green-600">
                                                        {formatNumber(scenario.train_count)} / {formatNumber(scenario.val_count)} / {formatNumber(scenario.test_count)}
                                                    </span>
                                                ) : (
                                                    <span className="text-slate-400">—</span>
                                                )}
                                            </td>
                                            <td className="px-6 py-4">
                                                {scenario.splitting_strategy && (
                                                    <Badge variant="secondary" className="text-xs">
                                                        {scenario.splitting_strategy.replace(/_/g, " ")}
                                                    </Badge>
                                                )}
                                            </td>
                                            <td className="px-6 py-4 text-muted-foreground">
                                                {formatDateTime(scenario.created_at)}
                                            </td>
                                            <td className="px-6 py-4">
                                                <div className="flex items-center gap-1">
                                                    {scenario.status === "queued" && (
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            className="h-8 w-8 p-0 text-green-600 hover:bg-green-50 hover:text-green-700"
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                handleStartGeneration(scenario);
                                                            }}
                                                            title="Start Generation"
                                                        >
                                                            <Play className="h-4 w-4" />
                                                        </Button>
                                                    )}
                                                    {scenario.status === "completed" && (
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            className="h-8 w-8 p-0 text-blue-600 hover:bg-blue-50 hover:text-blue-700"
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                router.push(`/ml-scenarios/${scenario.id}`);
                                                            }}
                                                            title="View Splits"
                                                        >
                                                            <Download className="h-4 w-4" />
                                                        </Button>
                                                    )}
                                                    <Button
                                                        size="sm"
                                                        variant="ghost"
                                                        className="h-8 w-8 p-0 text-red-600 hover:bg-red-50 hover:text-red-700"
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            handleDelete(scenario);
                                                        }}
                                                        title="Delete"
                                                    >
                                                        <Trash2 className="h-4 w-4" />
                                                    </Button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </CardContent>
                <div className="flex items-center justify-between border-t border-slate-200 px-6 py-4 text-sm text-muted-foreground dark:border-slate-800">
                    <div>
                        {total > 0
                            ? `Showing ${pageStart}-${pageEnd} of ${total} scenarios`
                            : "No scenarios to display"}
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                        {tableLoading && (
                            <div className="flex items-center gap-2">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                <span className="text-xs">Refreshing...</span>
                            </div>
                        )}
                        <div className="flex items-center gap-2">
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handlePageChange("prev")}
                                disabled={page === 1 || tableLoading}
                            >
                                Previous
                            </Button>
                            <span className="text-xs text-muted-foreground">
                                Page {page} of {totalPages}
                            </span>
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handlePageChange("next")}
                                disabled={page >= totalPages || tableLoading}
                            >
                                Next
                            </Button>
                        </div>
                    </div>
                </div>
            </Card>
        </div>
    );
}
