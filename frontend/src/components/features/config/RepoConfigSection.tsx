"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
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
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import {
    ChevronLeft,
    ChevronRight,
    Folder,
    Search,
    Settings,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { DynamicConfigField } from "./DynamicConfigField";
import { RepoScanConfig, ScanConfigOverrideModal } from "./ScanConfigOverrideModal";

interface RepoInfo {
    id: string;
    full_name: string;
    validation_status?: string;
}

// Dynamic config: field name -> array of selected values
type RepoConfig = Record<string, string[]>;

import { ConfigFieldSpec } from "@/types";

interface RepoConfigSectionProps {
    repos: RepoInfo[];
    repoFields: ConfigFieldSpec[];
    repoConfigs: Record<string, RepoConfig>;
    onChange: (configs: Record<string, RepoConfig>) => void;
    disabled?: boolean;
    isLoading?: boolean;
    showValidationStatusColumn?: boolean;
    // Scan config props
    repoScanConfigs?: Record<string, RepoScanConfig>;
    onScanConfigChange?: (repoId: string, config: RepoScanConfig) => void;
    showScanConfig?: boolean;
    // Language detection
    repoLanguages?: Record<string, string[]>;
    languageLoading?: Record<string, boolean>;
}

const PAGE_SIZE = 10;

/** Format field name for display (snake_case -> Title Case) */
const formatFieldName = (name: string) =>
    name.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());

export function RepoConfigSection({
    repos,
    repoFields,
    repoConfigs,
    onChange,
    disabled = false,
    isLoading = false,
    showValidationStatusColumn = true,
    onScanConfigChange,
    showScanConfig = false,
    repoLanguages,
    languageLoading,
    repoScanConfigs = {},
}: RepoConfigSectionProps) {
    const [page, setPage] = useState(0);
    const [searchQuery, setSearchQuery] = useState("");
    const [filterMode, setFilterMode] = useState<"all" | "overrides" | "default">("all");

    // Scan config modal state
    const [scanConfigRepo, setScanConfigRepo] = useState<{ id: string; name: string } | null>(null);
    const [savingScanConfig, setSavingScanConfig] = useState(false);

    // Apply to all state - dynamic based on repoFields
    const [applyAllValues, setApplyAllValues] = useState<RepoConfig>({});

    // Edit dialog state
    const [editingRepo, setEditingRepo] = useState<string | null>(null);
    const [editValues, setEditValues] = useState<RepoConfig>({});

    // Language detection state (received from props or empty)
    const effectiveRepoLanguages = repoLanguages || {};
    const effectiveLanguageLoading = languageLoading || {};

    // Only fields with type "list" and valid options (array or non-empty object)
    const listFields = useMemo(() =>
        repoFields.filter(f => {
            if (f.type !== "list" || !f.options) return false;
            // Check for array with items OR object with keys
            if (Array.isArray(f.options)) return f.options.length > 0;
            if (typeof f.options === "object") return Object.keys(f.options).length > 0;
            return false;
        }),
        [repoFields]
    );

    // Check if repo has override
    const hasOverride = useCallback((repoId: string) => {
        const config = repoConfigs[repoId];
        if (!config) return false;
        return Object.values(config).some(arr => arr.length > 0);
    }, [repoConfigs]);

    // Filter and Sort repos
    const filteredRepos = useMemo(() => {
        let result = repos;
        if (searchQuery.trim()) {
            const q = searchQuery.toLowerCase();
            result = result.filter(r => r.full_name.toLowerCase().includes(q));
        }
        if (filterMode === "overrides") {
            result = result.filter(r => hasOverride(r.id));
        } else if (filterMode === "default") {
            result = result.filter(r => !hasOverride(r.id));
        }
        // Sort alphabetically by full_name
        return [...result].sort((a, b) => a.full_name.localeCompare(b.full_name));
    }, [repos, searchQuery, filterMode, hasOverride]);

    // Paginated repos
    const paginatedRepos = useMemo(() => {
        const start = page * PAGE_SIZE;
        return filteredRepos.slice(start, start + PAGE_SIZE);
    }, [filteredRepos, page]);

    const totalPages = Math.ceil(filteredRepos.length / PAGE_SIZE);
    const tableColumnCount =
        1 +
        listFields.length +
        (showValidationStatusColumn ? 1 : 0) +
        (showScanConfig ? 1 : 0);

    // Open edit dialog
    const openEditDialog = (repoId: string) => {
        const existingConfig = repoConfigs[repoId] || {};
        // Initialize with empty arrays for all fields
        const config: RepoConfig = {};
        repoFields.forEach(f => {
            config[f.name] = existingConfig[f.name] || [];
        });
        setEditValues(config);
        setEditingRepo(repoId);
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
    const toggleEditOption = (fieldName: string, option: string) => {
        setEditValues(prev => {
            const current = prev[fieldName] || [];
            const newValues = current.includes(option)
                ? current.filter(v => v !== option)
                : [...current, option];
            return { ...prev, [fieldName]: newValues };
        });
    };

    // Get display value for a repo's config field
    const getDisplayValue = (repoId: string, fieldName: string) => {
        const config = repoConfigs[repoId];
        if (!config || !config[fieldName] || config[fieldName].length === 0) return "—";
        return config[fieldName].join(", ");
    };

    // Filter source_languages options based on detected languages
    const filterSourceLanguages = useCallback((options: string[], languages: string[]): string[] => {
        if (languages.length === 0) return options; // Show all if no languages detected
        const langSet = new Set(languages.map(l => l.toLowerCase()));
        return options.filter(opt => langSet.has(opt.toLowerCase()));
    }, []);

    // Filter test_frameworks options based on detected languages
    const filterTestFrameworks = useCallback((
        options: Record<string, string[]>,
        languages: string[]
    ): Record<string, string[]> => {
        if (languages.length === 0) return options; // Show all if no languages detected
        const langSet = new Set(languages.map(l => l.toLowerCase()));
        const filtered: Record<string, string[]> = {};
        for (const [lang, frameworks] of Object.entries(options)) {
            if (langSet.has(lang.toLowerCase())) {
                filtered[lang] = frameworks;
            }
        }
        return filtered;
    }, []);

    // Get filtered options for a field based on languages
    const getFilteredOptions = useCallback((field: ConfigFieldSpec, languages: string[]) => {
        if (field.name === "source_languages" && Array.isArray(field.options)) {
            return filterSourceLanguages(field.options as string[], languages);
        }
        if (field.name === "test_frameworks" && typeof field.options === "object" && !Array.isArray(field.options)) {
            return filterTestFrameworks(field.options as Record<string, string[]>, languages);
        }
        return field.options;
    }, [filterSourceLanguages, filterTestFrameworks]);

    // If no list fields with options, don't render
    if (listFields.length === 0) {
        return null;
    }

    // Show empty state when no repos but fields exist
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
                            Please validate the dataset first to see repositories.
                        </p>
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
                <Select value={filterMode} onValueChange={(v) => { setFilterMode(v as typeof filterMode); setPage(0); }}>
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
                                {showValidationStatusColumn && (
                                    <TableHead className="w-[10%]">Status</TableHead>
                                )}
                                {listFields.map(field => (
                                    <TableHead key={field.name}>
                                        <div className="flex flex-col gap-0.5">
                                            <span>{formatFieldName(field.name)}</span>
                                            {/* Show feature badges in header */}
                                            {field.required_by && field.required_by.length > 0 && (
                                                <div className="flex flex-wrap gap-0.5">
                                                    <TooltipProvider delayDuration={100}>
                                                        {field.required_by.slice(0, 2).map((featureName) => (
                                                            <Tooltip key={featureName}>
                                                                <TooltipTrigger asChild>
                                                                    <Badge
                                                                        variant="outline"
                                                                        className="text-[9px] px-1 py-0 cursor-help font-normal"
                                                                    >
                                                                        {featureName}
                                                                    </Badge>
                                                                </TooltipTrigger>
                                                                <TooltipContent side="top" className="max-w-xs">
                                                                    <p className="font-medium">{featureName}</p>
                                                                    <p className="text-xs text-muted-foreground">Feature requires this configuration</p>
                                                                </TooltipContent>
                                                            </Tooltip>
                                                        ))}
                                                        {field.required_by.length > 2 && (
                                                            <Tooltip>
                                                                <TooltipTrigger asChild>
                                                                    <Badge variant="outline" className="text-[9px] px-1 py-0 cursor-help font-normal">
                                                                        +{field.required_by.length - 2}
                                                                    </Badge>
                                                                </TooltipTrigger>
                                                                <TooltipContent side="top" className="max-w-xs">
                                                                    <div className="space-y-1">
                                                                        {field.required_by.slice(2).map(f => (
                                                                            <p key={f} className="text-xs">{f}</p>
                                                                        ))}
                                                                    </div>
                                                                </TooltipContent>
                                                            </Tooltip>
                                                        )}
                                                    </TooltipProvider>
                                                </div>
                                            )}
                                        </div>
                                    </TableHead>
                                ))}
                                {showScanConfig && (
                                    <TableHead className="w-[80px]">Scan Config</TableHead>
                                )}
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {paginatedRepos.map(repo => (
                                <TableRow
                                    key={repo.id}
                                    className={`cursor-pointer hover:bg-muted/50 ${disabled ? "cursor-not-allowed opacity-70" : ""}`}
                                    onClick={() => !disabled && openEditDialog(repo.id)}
                                >
                                    <TableCell className="font-medium">
                                        <div className="flex items-center gap-2">
                                            <span>{repo.full_name}</span>
                                            {hasOverride(repo.id) && (
                                                <span className="text-primary" title="Has custom settings">●</span>
                                            )}
                                        </div>
                                    </TableCell>
                                    {showValidationStatusColumn && (
                                        <TableCell>
                                            <Badge
                                                variant={repo.validation_status === 'valid' ? 'default' : 'secondary'}
                                                className="text-[10px] h-5 px-1.5 uppercase"
                                            >
                                                {repo.validation_status || 'unknown'}
                                            </Badge>
                                        </TableCell>
                                    )}
                                    {listFields.map(field => (
                                        <TableCell key={field.name} className="text-sm text-muted-foreground">
                                            {getDisplayValue(repo.id, field.name)}
                                        </TableCell>
                                    ))}
                                    {/* Scan Config Button */}
                                    {showScanConfig && (
                                        <TableCell>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    setScanConfigRepo({ id: repo.id, name: repo.full_name });
                                                }}
                                                className="gap-1"
                                                title="Configure scan settings"
                                            >
                                                <Settings className="h-3.5 w-3.5" />
                                                {repoScanConfigs[repo.id] && (
                                                    <span className="w-1.5 h-1.5 bg-blue-500 rounded-full" />
                                                )}
                                            </Button>
                                        </TableCell>
                                    )}
                                </TableRow>
                            ))}
                            {paginatedRepos.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={tableColumnCount} className="text-center text-muted-foreground py-8">
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
                        <DialogTitle>Configure {repos.find(r => r.id === editingRepo)?.full_name || "Repository"}</DialogTitle>
                        <DialogDescription>
                            Set configuration values for this repository
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-6 py-4">
                        {listFields.map(field => {
                            // Get filtered options for this specific repo
                            const repoLangs = editingRepo ? (effectiveRepoLanguages[editingRepo] || []) : [];
                            const filteredOptions = getFilteredOptions(field, repoLangs);

                            // Create a field spec with filtered options
                            const fieldWithFilteredOptions: ConfigFieldSpec = {
                                ...field,
                                options: filteredOptions,
                            };

                            return (
                                <DynamicConfigField
                                    key={field.name}
                                    field={fieldWithFilteredOptions}
                                    value={editValues[field.name]}
                                    onChange={(newValue) => {
                                        setEditValues(prev => ({
                                            ...prev,
                                            [field.name]: newValue as string[]
                                        }));
                                    }}
                                />
                            );
                        })}
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

            {/* Scan Config Modal */}
            {scanConfigRepo && (
                <ScanConfigOverrideModal
                    isOpen={!!scanConfigRepo}
                    onClose={() => setScanConfigRepo(null)}
                    repoName={scanConfigRepo.name}
                    scanConfig={repoScanConfigs[scanConfigRepo.id] || null}
                    onSave={(config) => {
                        if (onScanConfigChange) {
                            onScanConfigChange(scanConfigRepo.id, config);
                        }
                        setScanConfigRepo(null);
                    }}
                    isSaving={savingScanConfig}
                />
            )}
        </div>
    );
}
