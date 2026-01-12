"use client";

import { useCallback, useEffect, useState } from "react";
import {
    Calendar,
    Check,
    Filter,
    Loader2,
    Search,
    X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { trainingScenariosApi } from "@/lib/api/training-scenarios";
import type { PreviewBuild } from "@/lib/api/training-scenarios";
import { formatDateTime } from "@/lib/utils";
import {
    useWizard,
    CI_PROVIDERS,
    BUILD_CONCLUSIONS,
    SUPPORTED_LANGUAGES,
    type CIProviderKey,
} from "./WizardContext";

function formatNumber(value: number) {
    return value.toLocaleString("en-US");
}

function getConclusionBadge(conclusion: string) {
    const isSuccess = conclusion === "success";
    return (
        <Badge
            variant="outline"
            className={
                isSuccess
                    ? "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300"
                    : "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300"
            }
        >
            {conclusion}
        </Badge>
    );
}

export function StepDataSource() {
    const { state, updateDataSource, setPreviewStats, setPreviewRepos, setIsPreviewLoading, setStep } = useWizard();
    const { dataSource, previewStats, isPreviewLoading } = state;

    const [previewBuilds, setPreviewBuilds] = useState<PreviewBuild[]>([]);
    const [page, setPage] = useState(1);
    const [hasApplied, setHasApplied] = useState(false);
    const [isFilterOpen, setIsFilterOpen] = useState(false);

    const PAGE_SIZE = 20;

    const applyFilters = useCallback(async (pageNum = 1) => {
        setIsPreviewLoading(true);
        try {
            const params: Record<string, string | boolean | number> = {
                skip: (pageNum - 1) * PAGE_SIZE,
                limit: PAGE_SIZE,
            };

            if (dataSource.date_start) {
                params.date_start = dataSource.date_start;
            }
            if (dataSource.date_end) {
                params.date_end = dataSource.date_end;
            }
            if (dataSource.languages.length > 0) {
                params.languages = dataSource.languages.join(",");
            }
            if (dataSource.conclusions.length > 0) {
                params.conclusions = dataSource.conclusions.join(",");
            }
            if (dataSource.ci_provider !== "all") {
                params.ci_provider = dataSource.ci_provider;
            }

            const response = await trainingScenariosApi.previewBuilds(params);
            setPreviewBuilds(response.builds);
            setPreviewStats(response.stats);
            // Save repos from preview for per-repo configuration in Step 2
            if (response.stats.repos) {
                setPreviewRepos(response.stats.repos);
            }
            setPage(pageNum);
            setHasApplied(true);
            setIsFilterOpen(false);
        } catch (error) {
            console.error("Failed to preview builds:", error);
        } finally {
            setIsPreviewLoading(false);
        }
    }, [dataSource, setIsPreviewLoading, setPreviewStats, setPreviewRepos]);

    // Auto-load on mount only if not applied yet
    useEffect(() => {
        if (!hasApplied) {
            applyFilters(1);
        }
    }, [hasApplied, applyFilters]);

    const handleLanguageToggle = (lang: string) => {
        const current = dataSource.languages;
        if (current.includes(lang)) {
            updateDataSource({ languages: current.filter((l) => l !== lang) });
        } else {
            updateDataSource({ languages: [...current, lang] });
        }
    };

    const handleConclusionToggle = (conclusion: string) => {
        const current = dataSource.conclusions;
        if (current.includes(conclusion)) {
            updateDataSource({ conclusions: current.filter((c) => c !== conclusion) });
        } else {
            updateDataSource({ conclusions: [...current, conclusion] });
        }
    };
    return (
        <div className="flex flex-col h-full gap-4">
            {/* Stats Banner & Filter Trigger */}
            <div className="flex flex-col md:flex-row gap-4 items-start md:items-center justify-between flex-shrink-0">
                {previewStats ? (
                    <div className="flex flex-wrap gap-4 flex-1">
                        <div className="flex items-center gap-2 px-3 py-2 bg-slate-100 dark:bg-slate-800 rounded-lg">
                            <span className="text-xl font-bold">{formatNumber(previewStats.total_builds)}</span>
                            <span className="text-xs text-muted-foreground uppercase tracking-wide">Total Builds</span>
                        </div>
                        <div className="flex items-center gap-2 px-3 py-2 bg-slate-100 dark:bg-slate-800 rounded-lg">
                            <span className="text-xl font-bold">{formatNumber(previewStats.total_repos)}</span>
                            <span className="text-xs text-muted-foreground uppercase tracking-wide">Repos</span>
                        </div>
                        <div className="flex items-center gap-2 px-3 py-2 bg-green-50 dark:bg-green-900/20 rounded-lg">
                            <span className="text-xl font-bold text-green-700 dark:text-green-400">
                                {formatNumber(previewStats.outcome_distribution.success)}
                            </span>
                            <span className="text-xs text-green-700/70 dark:text-green-400/70 uppercase tracking-wide">Success</span>
                        </div>
                        <div className="flex items-center gap-2 px-3 py-2 bg-red-50 dark:bg-red-900/20 rounded-lg">
                            <span className="text-xl font-bold text-red-700 dark:text-red-400">
                                {formatNumber(previewStats.outcome_distribution.failure)}
                            </span>
                            <span className="text-xs text-red-700/70 dark:text-red-400/70 uppercase tracking-wide">Failure</span>
                        </div>
                    </div>
                ) : (
                    <div className="flex-1"></div>
                )}

                <Dialog open={isFilterOpen} onOpenChange={setIsFilterOpen}>
                    <DialogTrigger asChild>
                        <Button variant="outline" className="gap-2 shrink-0">
                            <Filter className="h-4 w-4" />
                            Filters
                            {/* Badge for active filters count?? functionality not implemented but nice to have visually if complex */}
                        </Button>
                    </DialogTrigger>
                    <DialogContent className="max-w-2xl">
                        <DialogHeader>
                            <DialogTitle>Filter Builds</DialogTitle>
                        </DialogHeader>

                        <div className="grid gap-6 py-4">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                {/* Date Range */}
                                <div className="space-y-2">
                                    <Label>Date Range</Label>
                                    <div className="grid grid-cols-2 gap-2">
                                        <div className="space-y-1">
                                            <Label className="text-[10px] uppercase text-muted-foreground">From</Label>
                                            <Input
                                                type="date"
                                                value={dataSource.date_start}
                                                onChange={(e) => updateDataSource({ date_start: e.target.value })}
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <Label className="text-[10px] uppercase text-muted-foreground">To</Label>
                                            <Input
                                                type="date"
                                                value={dataSource.date_end}
                                                onChange={(e) => updateDataSource({ date_end: e.target.value })}
                                            />
                                        </div>
                                    </div>
                                </div>

                                {/* CI Provider */}
                                <div className="space-y-2">
                                    <Label>Provider</Label>
                                    <Select
                                        value={dataSource.ci_provider}
                                        onValueChange={(value) => updateDataSource({ ci_provider: value as CIProviderKey | "all" })}
                                    >
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="all">All Providers</SelectItem>
                                            {CI_PROVIDERS.map((provider) => (
                                                <SelectItem key={provider.value} value={provider.value}>
                                                    {provider.label}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                {/* Languages */}
                                <div className="space-y-2">
                                    <Label>Languages</Label>
                                    <div className="grid grid-cols-2 gap-2 p-2 border rounded-md min-h-[100px] max-h-[150px] overflow-y-auto">
                                        {SUPPORTED_LANGUAGES.map((lang) => (
                                            <div key={lang.value} className="flex items-center space-x-2">
                                                <Checkbox
                                                    id={`lang-${lang.value}`}
                                                    checked={dataSource.languages.includes(lang.value)}
                                                    onCheckedChange={() => handleLanguageToggle(lang.value)}
                                                />
                                                <label
                                                    htmlFor={`lang-${lang.value}`}
                                                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                                                >
                                                    {lang.label}
                                                </label>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Status */}
                                <div className="space-y-2">
                                    <Label>Build Status</Label>
                                    <div className="flex flex-col gap-2 p-2 border rounded-md">
                                        {BUILD_CONCLUSIONS.map((c) => (
                                            <div key={c.value} className="flex items-center space-x-2">
                                                <Checkbox
                                                    id={`conclusion-${c.value}`}
                                                    checked={dataSource.conclusions.includes(c.value)}
                                                    onCheckedChange={() => handleConclusionToggle(c.value)}
                                                />
                                                <label
                                                    htmlFor={`conclusion-${c.value}`}
                                                    className="text-sm font-medium leading-none cursor-pointer"
                                                >
                                                    {c.label}
                                                </label>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </div>

                        <DialogFooter>
                            <Button variant="outline" onClick={() => setIsFilterOpen(false)}>
                                Cancel
                            </Button>
                            <Button onClick={() => applyFilters(1)} disabled={isPreviewLoading}>
                                {isPreviewLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                Apply Filters
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>

            {/* Main Table Area */}
            <Card className="flex-1 overflow-hidden flex flex-col">
                <CardHeader className="py-4 border-b bg-slate-50/50 dark:bg-slate-900/50 flex-shrink-0">
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="text-base">Build Preview</CardTitle>
                            <CardDescription className="text-xs mt-1">
                                {previewBuilds.length > 0
                                    ? `Showing ${formatNumber(previewBuilds.length)} of ${formatNumber(previewStats?.total_builds || 0)} matched builds`
                                    : "No builds loaded"}
                            </CardDescription>
                        </div>
                        {/* Maybe pagination here later? */}
                    </div>
                </CardHeader>
                <CardContent className="p-0 flex-1 overflow-hidden">
                    <div className="h-full overflow-y-auto">
                        <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                            <thead className="bg-slate-50 dark:bg-slate-900 sticky top-0 z-10 shadow-sm border-b">
                                <tr>
                                    <th className="px-4 py-3 text-left font-semibold text-slate-500 bg-slate-50 dark:bg-slate-900">Repository</th>
                                    <th className="px-4 py-3 text-left font-semibold text-slate-500 bg-slate-50 dark:bg-slate-900">Branch</th>
                                    <th className="px-4 py-3 text-left font-semibold text-slate-500 bg-slate-50 dark:bg-slate-900">Commit</th>
                                    <th className="px-4 py-3 text-left font-semibold text-slate-500 bg-slate-50 dark:bg-slate-900">Conclusion</th>
                                    <th className="px-4 py-3 text-left font-semibold text-slate-500 bg-slate-50 dark:bg-slate-900">Date</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-200 dark:divide-slate-800 bg-white dark:bg-slate-950">
                                {isPreviewLoading ? (
                                    <tr>
                                        <td colSpan={5} className="px-4 py-20 text-center">
                                            <div className="flex flex-col items-center gap-2">
                                                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                                                <p className="text-sm text-muted-foreground">Loading builds...</p>
                                            </div>
                                        </td>
                                    </tr>
                                ) : previewBuilds.length === 0 ? (
                                    <tr>
                                        <td colSpan={5} className="px-4 py-20 text-center text-muted-foreground">
                                            <div className="flex flex-col items-center gap-2">
                                                <Search className="h-8 w-8 opacity-20" />
                                                <p>No builds found matching your filters.</p>
                                                <Button variant="link" onClick={() => setIsFilterOpen(true)}>
                                                    Adjust Filters
                                                </Button>
                                            </div>
                                        </td>
                                    </tr>
                                ) : (
                                    previewBuilds.map((build) => (
                                        <tr key={build.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/50 transition-colors">
                                            <td className="px-4 py-3 font-medium">{build.repo_name}</td>
                                            <td className="px-4 py-3 text-muted-foreground">{build.branch}</td>
                                            <td className="px-4 py-3 font-mono text-xs opacity-70">{build.commit_sha.substring(0, 7)}</td>
                                            <td className="px-4 py-3">{getConclusionBadge(build.conclusion)}</td>
                                            <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                                                {formatDateTime(build.run_started_at)}
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
