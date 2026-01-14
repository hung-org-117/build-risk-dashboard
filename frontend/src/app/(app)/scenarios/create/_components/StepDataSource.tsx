"use client";

import { useCallback, useEffect, useState } from "react";
import {
    Calendar,
    Check,
    Filter,
    Loader2,
    Search,
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
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from "@/components/ui/command";
import { useDebounce } from "@/hooks/use-debounce";
import { buildSourcesApi } from "@/lib/api/build-sources";
import { trainingScenariosApi } from "@/lib/api/training-scenarios";
import type { PreviewBuild } from "@/lib/api/training-scenarios";
import { formatDateTime, cn } from "@/lib/utils";
import {
    useWizard,
    BUILD_CONCLUSIONS,
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

const CI_PROVIDER_LABELS: Record<string, string> = {
    github_actions: "GitHub Actions",
    circleci: "CircleCI",
    travis_ci: "Travis CI",
};

function getCIProviderLabel(provider: string): string {
    return CI_PROVIDER_LABELS[provider] || provider.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

export function StepDataSource() {
    const { state, updateDataSource, setPreviewStats, setPreviewRepos, setIsPreviewLoading, setStep } = useWizard();
    const { dataSource, previewStats, isPreviewLoading } = state;

    const [previewBuilds, setPreviewBuilds] = useState<PreviewBuild[]>([]);
    const [page, setPage] = useState(1);
    const [hasApplied, setHasApplied] = useState(false);
    const [isFilterOpen, setIsFilterOpen] = useState(false);

    // Dynamic Options State
    const [ciProviders, setCiProviders] = useState<{ value: string; label: string }[]>([]);
    const [supportedLanguages, setSupportedLanguages] = useState<{ value: string; label: string }[]>([]);
    const [buildSources, setBuildSources] = useState<{ id: string; name: string; builds_found: number }[]>([]);
    const [isLoadingOptions, setIsLoadingOptions] = useState(false);

    // Server-side Search State
    const [searchQuery, setSearchQuery] = useState("");
    const debouncedSearch = useDebounce(searchQuery, 300);

    const PAGE_SIZE = 20;

    // Fetch Static Filter Options on Mount
    useEffect(() => {
        const fetchStaticOptions = async () => {
            try {
                const options = await trainingScenariosApi.getFilterOptions();
                setCiProviders([{ value: "all", label: "All CI Providers" }, ...options.providers]);
                setSupportedLanguages(options.languages);
            } catch (err) {
                console.error("Failed to load filter options:", err);
            }
        };
        fetchStaticOptions();
    }, []);

    // Fetch Build Sources (Server-side Search)
    useEffect(() => {
        const fetchBuildSources = async () => {
            // Only show loading if we are searching or initial load (buildSources empty)
            if (debouncedSearch || buildSources.length === 0) {
                setIsLoadingOptions(true);
            }

            try {
                const sourcesResponse = await buildSourcesApi.list({
                    limit: 5,
                    q: debouncedSearch
                });

                setBuildSources(sourcesResponse.items
                    .filter(s => s.validation_status === 'completed')
                    .map(s => ({ id: s.id, name: s.name, builds_found: s.validation_stats.builds_found }))
                );
            } catch (err) {
                console.error("Failed to load build sources:", err);
            } finally {
                setIsLoadingOptions(false);
            }
        };
        fetchBuildSources();
    }, [debouncedSearch]);

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
            if (dataSource.ci_providers.length > 0) {
                params.ci_providers = dataSource.ci_providers.join(",");
            }
            if (dataSource.build_source_ids.length > 0) {
                params.build_source_ids = dataSource.build_source_ids.join(",");
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

    const handleProviderToggle = (provider: string) => {
        const current = dataSource.ci_providers;
        if (current.includes(provider)) {
            updateDataSource({ ci_providers: current.filter((p) => p !== provider) });
        } else {
            updateDataSource({ ci_providers: [...current, provider] });
        }
    };

    const handleBuildSourceToggle = (sourceId: string) => {
        const current = dataSource.build_source_ids;
        if (current.includes(sourceId)) {
            updateDataSource({ build_source_ids: current.filter((id) => id !== sourceId) });
        } else {
            updateDataSource({ build_source_ids: [...current, sourceId] });
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
                            {dataSource.build_source_ids.length > 0 && (
                                <Badge variant="secondary" className="ml-1 h-5 px-1.5 min-w-[1.25rem] text-[10px]">
                                    {dataSource.build_source_ids.length}
                                </Badge>
                            )}
                        </Button>
                    </DialogTrigger>
                    <DialogContent className="max-w-3xl">
                        <DialogHeader>
                            <DialogTitle>Filter Builds</DialogTitle>
                            <DialogDescription>
                                Refine the build selection for your training set
                            </DialogDescription>
                        </DialogHeader>

                        <div className="grid gap-6 py-4">
                            {/* Top Row: Dates and Provider */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                {/* Date Start */}
                                <div className="space-y-2">
                                    <Label>From Date</Label>
                                    <Input
                                        type="date"
                                        value={dataSource.date_start}
                                        onChange={(e) => updateDataSource({ date_start: e.target.value })}
                                        className="bg-background"
                                    />
                                </div>
                                {/* Date End */}
                                <div className="space-y-2">
                                    <Label>To Date</Label>
                                    <Input
                                        type="date"
                                        value={dataSource.date_end}
                                        onChange={(e) => updateDataSource({ date_end: e.target.value })}
                                        className="bg-background"
                                    />
                                </div>
                                {/* Provider */}
                                <div className="space-y-2">
                                    <Label>CI Provider</Label>
                                    <div className="border rounded-md p-2 h-[100px] overflow-y-auto bg-background">
                                        <div className="flex items-center space-x-2 mb-2 pb-2 border-b">
                                            <Checkbox
                                                id="provider-all"
                                                checked={dataSource.ci_providers.length === 0}
                                                onCheckedChange={(checked) => {
                                                    if (checked) updateDataSource({ ci_providers: [] });
                                                }}
                                            />
                                            <label
                                                htmlFor="provider-all"
                                                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                                            >
                                                All
                                            </label>
                                        </div>
                                        <div className="space-y-2">
                                            {ciProviders.filter(p => p.value !== 'all').map((provider) => (
                                                <div key={provider.value} className="flex items-center space-x-2">
                                                    <Checkbox
                                                        id={`provider-${provider.value}`}
                                                        checked={dataSource.ci_providers.includes(provider.value)}
                                                        onCheckedChange={() => handleProviderToggle(provider.value)}
                                                    />
                                                    <label
                                                        htmlFor={`provider-${provider.value}`}
                                                        className="text-sm leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                                                    >
                                                        {provider.label}
                                                    </label>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Middle Row: Languages and Status */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="space-y-2">
                                    <Label>Languages</Label>
                                    <div className="p-3 border rounded-md bg-slate-50/50 dark:bg-slate-900/20 max-h-[160px] overflow-y-auto space-y-2">
                                        {isLoadingOptions ? (
                                            <div className="flex justify-center p-2"><Loader2 className="animate-spin h-4 w-4" /></div>
                                        ) : supportedLanguages.length > 0 ? (
                                            <>
                                                <div className="flex items-center space-x-2 mb-2 pb-2 border-b border-secondary">
                                                    <Checkbox
                                                        id="lang-all"
                                                        checked={dataSource.languages.length === 0}
                                                        onCheckedChange={(checked) => {
                                                            if (checked) updateDataSource({ languages: [] });
                                                        }}
                                                    />
                                                    <label htmlFor="lang-all" className="text-sm font-medium leading-none cursor-pointer select-none">
                                                        All
                                                    </label>
                                                </div>
                                                {supportedLanguages.map((lang) => (
                                                    <div key={lang.value} className="flex items-center space-x-2">
                                                        <Checkbox
                                                            id={`lang-${lang.value}`}
                                                            checked={dataSource.languages.includes(lang.value)}
                                                            onCheckedChange={() => handleLanguageToggle(lang.value)}
                                                        />
                                                        <label
                                                            htmlFor={`lang-${lang.value}`}
                                                            className="text-sm font-medium leading-none cursor-pointer select-none"
                                                        >
                                                            {lang.label}
                                                        </label>
                                                    </div>
                                                ))}
                                            </>
                                        ) : (
                                            <div className="text-sm text-muted-foreground p-2">No languages available</div>
                                        )}
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <Label>Build Status</Label>
                                    <div className="p-3 border rounded-md bg-slate-50/50 dark:bg-slate-900/20 max-h-[160px] overflow-y-auto space-y-2">
                                        <div className="flex items-center space-x-2 mb-2 pb-2 border-b border-secondary">
                                            <Checkbox
                                                id="conclusion-all"
                                                checked={dataSource.conclusions.length === 0}
                                                onCheckedChange={(checked) => {
                                                    if (checked) updateDataSource({ conclusions: [] });
                                                }}
                                            />
                                            <label htmlFor="conclusion-all" className="text-sm font-medium leading-none cursor-pointer select-none">
                                                All
                                            </label>
                                        </div>
                                        {BUILD_CONCLUSIONS.map((c) => (
                                            <div key={c.value} className="flex items-center space-x-2">
                                                <Checkbox
                                                    id={`conclusion-${c.value}`}
                                                    checked={dataSource.conclusions.includes(c.value)}
                                                    onCheckedChange={() => handleConclusionToggle(c.value)}
                                                />
                                                <label
                                                    htmlFor={`conclusion-${c.value}`}
                                                    className="text-sm font-medium leading-none cursor-pointer select-none"
                                                >
                                                    {c.label}
                                                </label>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>

                            {/* Bottom Row: Data Source (Multi-Select Combobox) */}
                            {buildSources.length > 0 && (
                                <div className="space-y-2">
                                    <div className="space-y-2">
                                        <div className="flex items-center justify-between">
                                            <Label>Data Source</Label>
                                        </div>

                                        <div className="border rounded-md shadow-sm bg-background">
                                            <Command shouldFilter={false} className="h-auto bg-transparent">
                                                <CommandInput
                                                    placeholder="Search sources..."
                                                    className="h-9"
                                                    value={searchQuery}
                                                    onValueChange={setSearchQuery}
                                                />
                                                <CommandList className="max-h-[200px] overflow-y-auto p-1">
                                                    {isLoadingOptions ? (
                                                        <div className="py-6 text-center text-sm text-muted-foreground">
                                                            <Loader2 className="h-4 w-4 animate-spin mx-auto mb-2" />
                                                            Loading sources...
                                                        </div>
                                                    ) : (
                                                        <>
                                                            <CommandEmpty className="py-2 text-center text-sm text-muted-foreground">No source found.</CommandEmpty>
                                                            <CommandGroup>
                                                                {buildSources.map((source) => (
                                                                    <CommandItem
                                                                        key={source.id}
                                                                        value={source.name}
                                                                        onSelect={() => handleBuildSourceToggle(source.id)}
                                                                        className="flex items-center gap-2 px-2 py-1.5 cursor-pointer"
                                                                    >
                                                                        <div className={cn(
                                                                            "flex h-4 w-4 items-center justify-center rounded-sm border border-primary",
                                                                            dataSource.build_source_ids.includes(source.id)
                                                                                ? "bg-primary text-primary-foreground"
                                                                                : "opacity-50 [&_svg]:invisible"
                                                                        )}>
                                                                            <Check className={cn("h-3 w-3")} />
                                                                        </div>

                                                                        <div className="flex flex-col flex-1 min-w-0">
                                                                            <span className="truncate font-medium">{source.name}</span>
                                                                            <span className="text-xs text-muted-foreground">
                                                                                {source.builds_found} builds
                                                                            </span>
                                                                        </div>
                                                                    </CommandItem>
                                                                ))}
                                                            </CommandGroup>
                                                        </>
                                                    )}
                                                </CommandList>
                                            </Command>
                                        </div>


                                        <div className="flex justify-between items-center text-xs text-muted-foreground px-1 h-6">
                                            <span>
                                                {dataSource.build_source_ids.length > 0
                                                    ? `${dataSource.build_source_ids.length} selected`
                                                    : "All sources included"}
                                            </span>
                                            {dataSource.build_source_ids.length > 0 && (
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    className="h-auto p-0 text-muted-foreground hover:text-foreground font-normal"
                                                    onClick={() => updateDataSource({ build_source_ids: [] })}
                                                >
                                                    Clear selection
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            )}

                        </div>
                        <DialogFooter className="gap-2 sm:gap-0">
                            <Button variant="ghost" onClick={() => setIsFilterOpen(false)}>
                                Cancel
                            </Button>
                            <Button onClick={() => applyFilters(1)} disabled={isPreviewLoading}>
                                {isPreviewLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                Apply Filters
                            </Button>
                        </DialogFooter>
                    </DialogContent >
                </Dialog >
            </div >

            {/* Main Table Area */}
            < Card className="flex-1 overflow-hidden flex flex-col shadow-md" >
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
                    </div>
                </CardHeader>
                <CardContent className="p-0 flex-1 overflow-hidden">
                    <div className="h-full overflow-y-auto">
                        <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                            <thead className="bg-slate-50 dark:bg-slate-900 sticky top-0 z-10 shadow-sm border-b">
                                <tr>
                                    <th className="px-4 py-3 text-left font-semibold text-slate-500 bg-slate-50 dark:bg-slate-900">Repository</th>
                                    <th className="px-4 py-3 text-left font-semibold text-slate-500 bg-slate-50 dark:bg-slate-900">Language</th>
                                    <th className="px-4 py-3 text-left font-semibold text-slate-500 bg-slate-50 dark:bg-slate-900">CI Provider</th>
                                    <th className="px-4 py-3 text-left font-semibold text-slate-500 bg-slate-50 dark:bg-slate-900">Commit</th>
                                    <th className="px-4 py-3 text-left font-semibold text-slate-500 bg-slate-50 dark:bg-slate-900">Conclusion</th>
                                    <th className="px-4 py-3 text-left font-semibold text-slate-500 bg-slate-50 dark:bg-slate-900">Build Created</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-200 dark:divide-slate-800 bg-white dark:bg-slate-950">
                                {isPreviewLoading ? (
                                    <tr>
                                        <td colSpan={6} className="px-4 py-20 text-center">
                                            <div className="flex flex-col items-center gap-2">
                                                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                                                <p className="text-sm text-muted-foreground">Loading builds...</p>
                                            </div>
                                        </td>
                                    </tr>
                                ) : previewBuilds.length === 0 ? (
                                    <tr>
                                        <td colSpan={6} className="px-4 py-20 text-center text-muted-foreground">
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
                                            <td className="px-4 py-3 text-muted-foreground">{build.language || "Unknown"}</td>
                                            <td className="px-4 py-3 text-muted-foreground">{getCIProviderLabel(build.ci_provider || "unknown")}</td>
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
            </Card >
        </div >
    );
}
