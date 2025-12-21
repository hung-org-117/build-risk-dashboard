"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
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
} from "@/components/ui/dialog";
import {
    ChevronLeft,
    ChevronRight,
    Search,
    Folder,
    Check,
    ArrowRight,
} from "lucide-react";

interface RepoInfo {
    repo_name: string;
    validation_status: string;
}

interface RepoConfig {
    source_languages: string[];
    test_frameworks: string[];
}

interface ConfigFieldSpec {
    name: string;
    type: string;
    scope: string;
    required: boolean;
    description: string;
    default: unknown;
    options: string[] | null;
}

interface RepoConfigSectionProps {
    repos: RepoInfo[];
    repoFields: ConfigFieldSpec[];
    repoConfigs: Record<string, RepoConfig>;
    onChange: (configs: Record<string, RepoConfig>) => void;
    disabled?: boolean;
    isLoading?: boolean;
}

const PAGE_SIZE = 10;

export function RepoConfigSection({
    repos,
    repoFields,
    repoConfigs,
    onChange,
    disabled = false,
    isLoading = false,
}: RepoConfigSectionProps) {
    // Pagination
    const [page, setPage] = useState(0);

    // Search & filter
    const [searchQuery, setSearchQuery] = useState("");
    const [filterMode, setFilterMode] = useState<"all" | "overrides" | "default">("all");

    // Apply to all state
    const [applyAllValues, setApplyAllValues] = useState<RepoConfig>({
        source_languages: [],
        test_frameworks: [],
    });

    // Edit dialog state
    const [editingRepo, setEditingRepo] = useState<string | null>(null);
    const [editValues, setEditValues] = useState<RepoConfig>({
        source_languages: [],
        test_frameworks: [],
    });

    // When repos is empty, sync applyAllValues as default config using special __default__ key
    useEffect(() => {
        if (repos.length === 0 && (applyAllValues.source_languages.length > 0 || applyAllValues.test_frameworks.length > 0)) {
            onChange({
                __default__: applyAllValues,
            });
        }
    }, [repos.length, applyAllValues, onChange]);

    // Get field options
    const languageOptions = useMemo(() =>
        repoFields.find(f => f.name === "source_languages")?.options || [],
        [repoFields]
    );
    const frameworkOptions = useMemo(() =>
        repoFields.find(f => f.name === "test_frameworks")?.options || [],
        [repoFields]
    );

    // Check if repo has override (different from defaults)
    const hasOverride = useCallback((repoName: string) => {
        const config = repoConfigs[repoName];
        if (!config) return false;
        return config.source_languages.length > 0 || config.test_frameworks.length > 0;
    }, [repoConfigs]);

    // Filter repos
    const filteredRepos = useMemo(() => {
        let result = repos;

        // Search
        if (searchQuery.trim()) {
            const q = searchQuery.toLowerCase();
            result = result.filter(r => r.repo_name.toLowerCase().includes(q));
        }

        // Filter mode
        if (filterMode === "overrides") {
            result = result.filter(r => hasOverride(r.repo_name));
        } else if (filterMode === "default") {
            result = result.filter(r => !hasOverride(r.repo_name));
        }

        return result;
    }, [repos, searchQuery, filterMode, hasOverride]);

    // Paginated repos
    const paginatedRepos = useMemo(() => {
        const start = page * PAGE_SIZE;
        return filteredRepos.slice(start, start + PAGE_SIZE);
    }, [filteredRepos, page]);

    const totalPages = Math.ceil(filteredRepos.length / PAGE_SIZE);

    // Reset page when filter changes
    const handleFilterChange = (value: "all" | "overrides" | "default") => {
        setFilterMode(value);
        setPage(0);
    };

    // Apply to all repos
    const handleApplyToAll = (field: "source_languages" | "test_frameworks") => {
        if (disabled) return;
        const newConfigs = { ...repoConfigs };
        repos.forEach(repo => {
            if (!newConfigs[repo.repo_name]) {
                newConfigs[repo.repo_name] = { source_languages: [], test_frameworks: [] };
            }
            newConfigs[repo.repo_name] = {
                ...newConfigs[repo.repo_name],
                [field]: [...applyAllValues[field]],
            };
        });
        onChange(newConfigs);
    };

    // Toggle option in apply-all
    const toggleApplyAllOption = (field: "source_languages" | "test_frameworks", option: string) => {
        setApplyAllValues(prev => {
            const current = prev[field];
            const newValues = current.includes(option)
                ? current.filter(v => v !== option)
                : [...current, option];
            return { ...prev, [field]: newValues };
        });
    };

    // Open edit dialog
    const openEditDialog = (repoName: string) => {
        const config = repoConfigs[repoName] || { source_languages: [], test_frameworks: [] };
        setEditValues({ ...config });
        setEditingRepo(repoName);
    };

    // Save edit
    const saveEdit = () => {
        if (!editingRepo) return;
        onChange({
            ...repoConfigs,
            [editingRepo]: editValues,
        });
        setEditingRepo(null);
    };

    // Toggle option in edit dialog
    const toggleEditOption = (field: "source_languages" | "test_frameworks", option: string) => {
        setEditValues(prev => {
            const current = prev[field];
            const newValues = current.includes(option)
                ? current.filter(v => v !== option)
                : [...current, option];
            return { ...prev, [field]: newValues };
        });
    };

    // Get display value for a repo's config
    const getDisplayValue = (repoName: string, field: "source_languages" | "test_frameworks") => {
        const config = repoConfigs[repoName];
        if (!config || config[field].length === 0) return "—";
        return config[field].join(", ");
    };

    // Show empty state message when no repos but fields exist
    if (repos.length === 0 && !isLoading) {
        return (
            <div className="space-y-4">
                <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                    <Folder className="h-4 w-4" />
                    Repository Settings
                </div>
                <div className="border rounded-lg p-4 bg-muted/30 space-y-3">
                    <div className="text-sm text-muted-foreground">
                        <p className="mb-2">
                            ⚠️ <strong>Dataset validation required</strong> to configure per-repo settings.
                        </p>
                        <p className="text-xs">
                            The selected features require repository-specific configuration (e.g., source languages, test frameworks).
                            Please validate the dataset first to see the list of repositories, or set default values below that will apply to all repos.
                        </p>
                    </div>

                    {/* Default values section */}
                    <div className="pt-3 border-t space-y-3">
                        <div className="text-sm font-medium">Set Default Values for All Repositories</div>

                        {/* Languages */}
                        {languageOptions.length > 0 && (
                            <div className="flex flex-wrap items-center gap-2">
                                <span className="text-sm text-muted-foreground w-24">Languages:</span>
                                <div className="flex flex-wrap gap-1 flex-1">
                                    {languageOptions.map(option => {
                                        const isSelected = applyAllValues.source_languages.includes(option);
                                        return (
                                            <Badge
                                                key={option}
                                                variant={isSelected ? "default" : "outline"}
                                                className={`cursor-pointer transition-colors ${disabled ? "opacity-50 cursor-not-allowed" : "hover:bg-primary/80"}`}
                                                onClick={() => !disabled && toggleApplyAllOption("source_languages", option)}
                                            >
                                                {option}
                                            </Badge>
                                        );
                                    })}
                                </div>
                            </div>
                        )}

                        {/* Frameworks */}
                        {frameworkOptions.length > 0 && (
                            <div className="flex flex-wrap items-center gap-2">
                                <span className="text-sm text-muted-foreground w-24">Frameworks:</span>
                                <div className="flex flex-wrap gap-1 flex-1">
                                    {frameworkOptions.slice(0, 10).map(option => {
                                        const isSelected = applyAllValues.test_frameworks.includes(option);
                                        return (
                                            <Badge
                                                key={option}
                                                variant={isSelected ? "default" : "outline"}
                                                className={`cursor-pointer transition-colors ${disabled ? "opacity-50 cursor-not-allowed" : "hover:bg-primary/80"}`}
                                                onClick={() => !disabled && toggleApplyAllOption("test_frameworks", option)}
                                            >
                                                {option}
                                            </Badge>
                                        );
                                    })}
                                    {frameworkOptions.length > 10 && (
                                        <Badge variant="secondary">+{frameworkOptions.length - 10} more</Badge>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                <Folder className="h-4 w-4" />
                Repository Settings ({repos.length} repos)
            </div>

            {/* Apply to All Section */}
            <div className="border rounded-lg p-4 bg-muted/30 space-y-3">
                <div className="text-sm font-medium flex items-center gap-2">
                    📋 Apply to All Repositories
                </div>

                {/* Languages */}
                <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm text-muted-foreground w-24">Languages:</span>
                    <div className="flex flex-wrap gap-1 flex-1">
                        {languageOptions.map(option => {
                            const isSelected = applyAllValues.source_languages.includes(option);
                            return (
                                <Badge
                                    key={option}
                                    variant={isSelected ? "default" : "outline"}
                                    className={`cursor-pointer transition-colors ${disabled ? "opacity-50 cursor-not-allowed" : "hover:bg-primary/80"}`}
                                    onClick={() => !disabled && toggleApplyAllOption("source_languages", option)}
                                >
                                    {option}
                                </Badge>
                            );
                        })}
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        disabled={disabled || applyAllValues.source_languages.length === 0}
                        onClick={() => handleApplyToAll("source_languages")}
                        className="gap-1"
                    >
                        Apply <ArrowRight className="h-3 w-3" />
                    </Button>
                </div>

                {/* Frameworks */}
                <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm text-muted-foreground w-24">Frameworks:</span>
                    <div className="flex flex-wrap gap-1 flex-1">
                        {frameworkOptions.slice(0, 10).map(option => {
                            const isSelected = applyAllValues.test_frameworks.includes(option);
                            return (
                                <Badge
                                    key={option}
                                    variant={isSelected ? "default" : "outline"}
                                    className={`cursor-pointer transition-colors ${disabled ? "opacity-50 cursor-not-allowed" : "hover:bg-primary/80"}`}
                                    onClick={() => !disabled && toggleApplyAllOption("test_frameworks", option)}
                                >
                                    {option}
                                </Badge>
                            );
                        })}
                        {frameworkOptions.length > 10 && (
                            <Badge variant="secondary">+{frameworkOptions.length - 10} more</Badge>
                        )}
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        disabled={disabled || applyAllValues.test_frameworks.length === 0}
                        onClick={() => handleApplyToAll("test_frameworks")}
                        className="gap-1"
                    >
                        Apply <ArrowRight className="h-3 w-3" />
                    </Button>
                </div>
            </div>

            {/* Search and Filter */}
            <div className="flex items-center gap-3">
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search repos..."
                        value={searchQuery}
                        onChange={(e) => {
                            setSearchQuery(e.target.value);
                            setPage(0);
                        }}
                        className="pl-9"
                    />
                </div>
                <Select value={filterMode} onValueChange={handleFilterChange}>
                    <SelectTrigger className="w-40">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All ({repos.length})</SelectItem>
                        <SelectItem value="overrides">With Overrides</SelectItem>
                        <SelectItem value="default">Using Default</SelectItem>
                    </SelectContent>
                </Select>
            </div>

            {/* Table */}
            {isLoading ? (
                <div className="space-y-2">
                    <Skeleton className="h-10 w-full" />
                    <Skeleton className="h-10 w-full" />
                    <Skeleton className="h-10 w-full" />
                </div>
            ) : (
                <div className="border rounded-lg overflow-hidden">
                    <Table>
                        <TableHeader>
                            <TableRow className="bg-muted/50">
                                <TableHead className="w-[40%]">Repository</TableHead>
                                <TableHead>Languages</TableHead>
                                <TableHead>Frameworks</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {paginatedRepos.map(repo => (
                                <TableRow
                                    key={repo.repo_name}
                                    className={`cursor-pointer hover:bg-muted/50 ${disabled ? "cursor-not-allowed opacity-70" : ""}`}
                                    onClick={() => !disabled && openEditDialog(repo.repo_name)}
                                >
                                    <TableCell className="font-medium">
                                        <div className="flex items-center gap-2">
                                            <span>{repo.repo_name}</span>
                                            {hasOverride(repo.repo_name) && (
                                                <span className="text-primary" title="Has custom settings">●</span>
                                            )}
                                        </div>
                                    </TableCell>
                                    <TableCell className="text-sm text-muted-foreground">
                                        {getDisplayValue(repo.repo_name, "source_languages")}
                                    </TableCell>
                                    <TableCell className="text-sm text-muted-foreground">
                                        {getDisplayValue(repo.repo_name, "test_frameworks")}
                                    </TableCell>
                                </TableRow>
                            ))}
                            {paginatedRepos.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={3} className="text-center text-muted-foreground py-8">
                                        No repositories match your search
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>
                        Showing {page * PAGE_SIZE + 1} - {Math.min((page + 1) * PAGE_SIZE, filteredRepos.length)} of {filteredRepos.length}
                    </span>
                    <div className="flex items-center gap-1">
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={page === 0}
                            onClick={() => setPage(p => p - 1)}
                        >
                            <ChevronLeft className="h-4 w-4" />
                        </Button>
                        {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                            const pageNum = page < 2 ? i : page > totalPages - 3 ? totalPages - 5 + i : page - 2 + i;
                            if (pageNum < 0 || pageNum >= totalPages) return null;
                            return (
                                <Button
                                    key={pageNum}
                                    variant={page === pageNum ? "default" : "outline"}
                                    size="sm"
                                    onClick={() => setPage(pageNum)}
                                    className="w-8"
                                >
                                    {pageNum + 1}
                                </Button>
                            );
                        })}
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={page >= totalPages - 1}
                            onClick={() => setPage(p => p + 1)}
                        >
                            <ChevronRight className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            )}

            {/* Edit Dialog */}
            <Dialog open={editingRepo !== null} onOpenChange={() => setEditingRepo(null)}>
                <DialogContent className="max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Configure {editingRepo}</DialogTitle>
                        <DialogDescription>
                            Set languages and test frameworks for this repository
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        {/* Languages */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Source Languages</label>
                            <div className="flex flex-wrap gap-1.5">
                                {languageOptions.map(option => {
                                    const isSelected = editValues.source_languages.includes(option);
                                    return (
                                        <Badge
                                            key={option}
                                            variant={isSelected ? "default" : "outline"}
                                            className="cursor-pointer transition-colors hover:bg-primary/80"
                                            onClick={() => toggleEditOption("source_languages", option)}
                                        >
                                            {isSelected && <Check className="h-3 w-3 mr-1" />}
                                            {option}
                                        </Badge>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Frameworks */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Test Frameworks</label>
                            <div className="flex flex-wrap gap-1.5 max-h-[200px] overflow-y-auto">
                                {frameworkOptions.map(option => {
                                    const isSelected = editValues.test_frameworks.includes(option);
                                    return (
                                        <Badge
                                            key={option}
                                            variant={isSelected ? "default" : "outline"}
                                            className="cursor-pointer transition-colors hover:bg-primary/80"
                                            onClick={() => toggleEditOption("test_frameworks", option)}
                                        >
                                            {isSelected && <Check className="h-3 w-3 mr-1" />}
                                            {option}
                                        </Badge>
                                    );
                                })}
                            </div>
                        </div>
                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={() => setEditingRepo(null)}>
                            Cancel
                        </Button>
                        <Button onClick={saveEdit}>
                            Save Changes
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
