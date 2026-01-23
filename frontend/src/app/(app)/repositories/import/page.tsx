"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
    ArrowLeft,
    ArrowRight,
    Building2,
    Globe,
    Loader2,
    Search,
    X,
    Folder,
} from "lucide-react";

import { FeatureConfigForm, type FeatureConfigsData } from "@/components/features/config/FeatureConfigForm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { useDebounce } from "@/hooks/use-debounce";
import { reposApi, templatesApi } from "@/lib/api";
import {
    CIProvider,
    FeatureDefinitionSummary,
    RepoImportPayload,
    RepoSuggestion
} from "@/types";

import { useToast } from "@/components/ui/use-toast";
import { featuresApi } from "@/lib/api/features";

import { useRepoLanguages } from "@/hooks/use-repo-languages";

import { useFeatureSelector } from "@/components/features";

export default function ImportRepositoriesPage() {
    const router = useRouter();
    const [step, setStep] = useState<1 | 2>(1);
    const [searchTerm, setSearchTerm] = useState("");
    const [isSearching, setIsSearching] = useState(false);
    const debouncedSearchTerm = useDebounce(searchTerm, 500);
    const lastSearchedTerm = useRef<string | null>(null);

    // Search results
    const [privateMatches, setPrivateMatches] = useState<RepoSuggestion[]>([]);
    const [publicMatches, setPublicMatches] = useState<RepoSuggestion[]>([]);
    const [searchError, setSearchError] = useState<string | null>(null);

    // Selection & Config
    const [selectedRepos, setSelectedRepos] = useState<Record<string, RepoSuggestion>>({});
    const [featureConfigs, setFeatureConfigs] = useState<FeatureConfigsData>({
        global: {},
        repos: {},
    });
    const [baseConfigs, setBaseConfigs] = useState<
        Record<string, {
            ci_provider: string;
            max_builds?: number | null;
            since_days?: number | null;
        }>
    >({});
    const [importing, setImporting] = useState(false);
    const [activeRepo, setActiveRepo] = useState<string | null>(null);

    // Supported Languages Validation
    const [supportedLanguages, setSupportedLanguages] = useState<string[]>([]);
    const { toast } = useToast();

    useEffect(() => {
        featuresApi.getConfig().then(data => {
            setSupportedLanguages(data.languages.map(l => l.toLowerCase()));
        }).catch(err => console.error("Failed to fetch supported languages", err));
    }, []);


    // Feature Selector Hook
    const featureSelector = useFeatureSelector();

    // Track if template has been applied (to avoid double API call)
    const [templateApplied, setTemplateApplied] = useState(false);

    // Initialize default template if empty
    useEffect(() => {
        const loadDefaultTemplate = async () => {
            if (featureSelector.loading) return;

            // Load Risk Prediction template if on step 2 (Configure)
            // Even if defaults are loaded, we want to ensure Risk Prediction is used.
            // Check if we already applied a template or if selection is just defaults
            if (step === 2 && !templateApplied) {
                try {
                    const template = await templatesApi.getByName("Risk Prediction");
                    if (template.feature_names) {
                        featureSelector.applyTemplate(template.feature_names);
                    }
                } catch (err) {
                    console.error("Failed to load Risk Prediction template", err);
                } finally {
                    setTemplateApplied(true);
                }
            }
        };

        if (step === 2) {
            loadDefaultTemplate();
        }
    }, [step, featureSelector.loading, templateApplied]);

    const performSearch = useCallback(async (query: string, force = false) => {
        if (!force && query === lastSearchedTerm.current) return;
        lastSearchedTerm.current = query;

        setIsSearching(true);
        setSearchError(null);
        try {
            const data = await reposApi.search(query.trim() || undefined);
            setPrivateMatches(data.private_matches.map(r => ({ ...r })));
            setPublicMatches(data.public_matches.map(r => ({ ...r })));
        } catch (err) {
            console.error(err);
            setSearchError("Failed to search repositories.");
        } finally {
            setIsSearching(false);
        }
    }, []);

    useEffect(() => {
        if (debouncedSearchTerm === searchTerm) {
            performSearch(debouncedSearchTerm);
        }
    }, [debouncedSearchTerm, searchTerm, performSearch]);

    useEffect(() => {
        performSearch("", true);
    }, [performSearch]);

    const toggleSelection = (repo: RepoSuggestion) => {
        const repoId = String(repo.github_repo_id);
        setSelectedRepos((prev) => {
            const next = { ...prev };
            if (next[repoId]) {
                delete next[repoId];
                setBaseConfigs((current) => {
                    const updated = { ...current };
                    delete updated[repoId];
                    return updated;
                });
            } else {
                next[repoId] = repo;
                setBaseConfigs((current) => ({
                    ...current,
                    [repoId]: {
                        ci_provider: CIProvider.GITHUB_ACTIONS,
                        max_builds: null,
                        since_days: null,
                    },
                }));
            }
            return next;
        });
    };

    const selectedList = useMemo(() => Object.values(selectedRepos), [selectedRepos]);

    useEffect(() => {
        if (selectedList.length === 0) {
            setActiveRepo(null);
            return;
        }
        if (!activeRepo || !selectedRepos[activeRepo]) {
            // Using ID as key
            setActiveRepo(String(selectedList[0].github_repo_id));
        }
    }, [selectedList, activeRepo, selectedRepos]);

    const handleImport = async () => {
        if (!selectedList.length) return;
        setImporting(true);

        try {
            // Filter out unsupported repositories
            const validRepos = selectedList.filter(repo => {
                if (!repo.language) return false; // Strict: requires language
                const lang = repo.language.toLowerCase();
                return supportedLanguages.includes(lang);
            });

            if (validRepos.length === 0) {
                toast({
                    title: "No valid repositories",
                    description: "None of the selected repositories use a supported language.",
                    variant: "destructive",
                });
                setImporting(false);
                return;
            }

            if (validRepos.length < selectedList.length) {
                toast({
                    title: "Some repositories skipped",
                    description: `${selectedList.length - validRepos.length} repositories were skipped because their language is not supported.`,
                    variant: "default", // or warning if available, default is neutral 
                });
            }

            // Prepare global configs including all selected features
            const finalGlobalConfig: Record<string, any> = { ...featureConfigs.global };

            // Get selected features for backend
            const featureIds = Array.from(featureSelector.selectedFeatures);

            const payloads: RepoImportPayload[] = validRepos.map((repo) => {
                const repoId = String(repo.github_repo_id);
                const baseConfig = baseConfigs[repoId];
                const dynamicRepoConfig = featureConfigs.repos[repoId] || {};

                return {
                    full_name: repo.full_name,
                    provider: "github",
                    ci_provider: baseConfig.ci_provider,
                    max_builds: baseConfig.max_builds ?? null,
                    since_days: baseConfig.since_days ?? null,
                    feature_configs: {
                        global: finalGlobalConfig,
                        repos: {
                            [repoId]: dynamicRepoConfig,
                        },
                    },
                    feature_ids: featureIds,
                };
            });

            await reposApi.importBulk(payloads);
            router.push("/repositories?imported=true");
        } catch (err: unknown) {
            console.error(err);
            toast({
                title: "Import failed",
                description: "An error occurred while importing repositories.",
                variant: "destructive",
            });
        } finally {
            setImporting(false);
        }
    };

    const featureFormFeatures = useMemo(() => featureSelector.selectedFeatures, [featureSelector.selectedFeatures]);

    const featureFormRepos = useMemo(() => selectedList.map(r => ({
        id: String(r.github_repo_id),
        full_name: r.full_name,
        validation_status: "unknown",
        primary_language: r.language
    })), [selectedList]);

    // Detect languages for selected repos
    const { repoLanguages } = useRepoLanguages(featureFormRepos);

    return (
        <div className="flex flex-col h-full min-h-0">
            {/* Header */}
            <div className="flex items-center justify-between border-b bg-background px-6 py-4">
                <div className="flex items-center gap-4">
                    <Button variant="ghost" size="sm" onClick={() => router.push("/repositories")}>
                        <ArrowLeft className="h-4 w-4 mr-2" />
                        Back to Repositories
                    </Button>
                    <div className="h-4 w-px bg-border" />
                    <div>
                        <h1 className="text-lg font-semibold">Import Repositories</h1>
                        <p className="text-sm text-muted-foreground">
                            Step {step} of 2: {step === 1 ? "Select Repositories" : "Configure & Import"}
                        </p>
                    </div>
                </div>

                {/* Step Indicator */}
                <div className="hidden md:flex items-center gap-2">
                    <StepIndicator step={1} currentStep={step} label="Repos" />
                    <div className="w-8 h-px bg-border" />
                    <StepIndicator step={2} currentStep={step} label="Configure" />
                </div>

                {/* Action Buttons */}
                <div className="flex items-center gap-2">
                    {step > 1 && (
                        <Button variant="outline" onClick={() => setStep(1)}>
                            <ArrowLeft className="h-4 w-4 mr-1" />
                            Back
                        </Button>
                    )}
                    {step < 2 ? (
                        <Button onClick={() => setStep(2)} disabled={selectedList.length === 0}>
                            Next
                            <ArrowRight className="h-4 w-4 ml-1" />
                        </Button>
                    ) : (
                        <Button onClick={handleImport} disabled={importing || selectedList.length === 0}>
                            {importing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Import {selectedList.length} Repositories
                        </Button>
                    )}
                </div>
            </div>

            {/* Main Content - Split View */}
            <div className={`flex-1 grid grid-cols-1 ${step === 1 ? "lg:grid-cols-[1fr_400px]" : ""} min-h-0 overflow-hidden`}>
                {/* Left Panel */}
                <div className="overflow-y-auto p-6">
                    {step === 1 ? (
                        <Step1Content
                            searchTerm={searchTerm}
                            setSearchTerm={setSearchTerm}
                            isSearching={isSearching}
                            searchError={searchError}
                            privateMatches={privateMatches}
                            publicMatches={publicMatches}
                            selectedRepos={selectedRepos}
                            toggleSelection={toggleSelection}
                            supportedLanguages={supportedLanguages}
                        />
                    ) : (
                        <ConfigurationStep
                            supportedLanguages={supportedLanguages}
                            selectedList={selectedList}
                            activeRepo={activeRepo}
                            setActiveRepo={setActiveRepo}
                            baseConfigs={baseConfigs}
                            setBaseConfigs={setBaseConfigs}
                            featureFormFeatures={featureFormFeatures}
                            featureFormRepos={featureFormRepos}
                            setFeatureConfigs={setFeatureConfigs}
                            repoLanguages={repoLanguages}
                            templateApplied={templateApplied}
                        />
                    )}
                </div>

                {/* Right Panel - Preview (Only for Step 1) */}
                {step === 1 && (
                    <div className="hidden lg:flex flex-col border-l bg-slate-50 dark:bg-slate-900/30 overflow-y-auto">
                        <div className="p-4 border-b bg-background">
                            <h3 className="font-semibold text-sm">
                                Selected Repositories
                            </h3>
                        </div>
                        <div className="flex-1 p-4 space-y-4 overflow-y-auto">
                            <SelectedReposPreview
                                selectedList={selectedList}
                                onRemove={(repo) => toggleSelection(repo)}
                            />
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

// Step Indicator Component
function StepIndicator({ step, currentStep, label }: { step: number; currentStep: number; label: string }) {
    const isActive = step === currentStep;
    const isComplete = step < currentStep;

    return (
        <div className="flex items-center gap-2">
            <div
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium ${isActive
                    ? "bg-primary text-primary-foreground"
                    : isComplete
                        ? "bg-green-500 text-white"
                        : "bg-muted text-muted-foreground"
                    }`}
            >
                {isComplete ? "✓" : step}
            </div>
            <span className={`text-sm ${isActive ? "font-medium" : "text-muted-foreground"}`}>
                {label}
            </span>
        </div>
    );
}

// Step 1 Content
interface Step1Props {
    searchTerm: string;
    setSearchTerm: (val: string) => void;
    isSearching: boolean;
    searchError: string | null;
    privateMatches: RepoSuggestion[];
    publicMatches: RepoSuggestion[];
    selectedRepos: Record<string, RepoSuggestion>;
    toggleSelection: (repo: RepoSuggestion) => void;
    supportedLanguages: string[];
}

function Step1Content({
    searchTerm,
    setSearchTerm,
    isSearching,
    searchError,
    privateMatches,
    publicMatches,
    selectedRepos,
    toggleSelection,
    supportedLanguages,
}: Step1Props) {
    const isLanguageSupported = (lang?: string) => {
        if (!lang) return false;
        return supportedLanguages.includes(lang.toLowerCase());
    };

    return (
        <div className="space-y-6 max-w-3xl">
            {/* Search */}
            <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                    type="text"
                    className="w-full rounded-lg border bg-background pl-10 pr-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    placeholder="Search repositories (e.g. owner/repo)..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                />
            </div>

            {/* Supported Languages Info */}
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 dark:border-blue-800 dark:bg-blue-900/20">
                <p className="text-sm text-blue-700 dark:text-blue-300">
                    <span className="font-semibold">Supported Languages:</span>{" "}
                    {supportedLanguages.length > 0 ? (
                        supportedLanguages.map((lang, i) => (
                            <span key={lang}>
                                <code className="rounded bg-blue-100 px-1.5 py-0.5 text-xs font-medium dark:bg-blue-800">
                                    {lang}
                                </code>
                                {i < supportedLanguages.length - 1 && <span className="mx-1">,</span>}
                            </span>
                        ))
                    ) : (
                        <span className="text-muted-foreground">Loading...</span>
                    )}
                </p>
            </div>

            {searchError && (
                <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
                    {searchError}
                </div>
            )}

            {/* Organization Repos */}
            <div>
                <h3 className="mb-3 text-sm font-semibold text-muted-foreground flex items-center gap-2">
                    <Building2 className="h-4 w-4" />
                    Organization Repositories
                </h3>
                <div className="space-y-2">
                    {privateMatches.length === 0 && !isSearching ? (
                        <div className="text-sm text-muted-foreground italic py-3 px-4 rounded-lg bg-muted/30">
                            No matching organization repositories found.
                        </div>
                    ) : (
                        privateMatches.map((repo) => (
                            <RepoItem
                                key={repo.github_repo_id}
                                repo={repo}
                                isSelected={!!selectedRepos[String(repo.github_repo_id)]}
                                onToggle={() => toggleSelection(repo)}
                                isSupported={isLanguageSupported(repo.language)}
                            />
                        ))
                    )}
                </div>
            </div>

            {/* Public Repos */}
            <div>
                <h3 className="mb-3 text-sm font-semibold text-muted-foreground flex items-center gap-2">
                    <Globe className="h-4 w-4" />
                    Public GitHub Repositories
                </h3>
                <div className="space-y-2">
                    {publicMatches.length === 0 && !isSearching ? (
                        <div className="text-sm text-muted-foreground italic py-3 px-4 rounded-lg bg-muted/30">
                            {searchTerm.length >= 3
                                ? "No matching public repositories found."
                                : "Type at least 3 characters to search."}
                        </div>
                    ) : (
                        publicMatches.map((repo) => (
                            <RepoItem
                                key={repo.github_repo_id}
                                repo={repo}
                                isSelected={!!selectedRepos[String(repo.github_repo_id)]}
                                onToggle={() => toggleSelection(repo)}
                                isSupported={isLanguageSupported(repo.language)}
                            />
                        ))
                    )}
                </div>
            </div>

            {isSearching && (
                <div className="flex justify-center py-6">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
            )}
        </div>
    );
}

// Step 2 Content
interface Step2Props {
    selectedList: RepoSuggestion[];
    activeRepo: string | null;
    setActiveRepo: (repo: string) => void;
    baseConfigs: Record<string, { ci_provider: string; max_builds?: number | null; since_days?: number | null }>;
    setBaseConfigs: React.Dispatch<React.SetStateAction<Record<string, { ci_provider: string; max_builds?: number | null; since_days?: number | null }>>>;
    featureFormFeatures: Set<string>;
    featureFormRepos: { id: string; full_name: string; validation_status: string }[];
    setFeatureConfigs: React.Dispatch<React.SetStateAction<FeatureConfigsData>>;
    repoLanguages: Record<string, string[]>;
    templateApplied: boolean;
}

// Step 3 Content (was Step 2)
interface ConfigurationStepProps extends Step2Props {
    supportedLanguages: string[];
}

function ConfigurationStep({
    selectedList,
    activeRepo,
    setActiveRepo,
    baseConfigs,
    setBaseConfigs,
    featureFormFeatures,
    featureFormRepos,
    setFeatureConfigs,
    repoLanguages,
    templateApplied,
    supportedLanguages,
}: ConfigurationStepProps) {
    // Validate active repo
    const currentRepo = selectedList.find(r => String(r.github_repo_id) === activeRepo);
    const currentLang = currentRepo?.language?.toLowerCase();
    const isSupported = currentLang ? supportedLanguages.includes(currentLang) : false;

    return (
        <div className="space-y-6 max-w-5xl mx-auto">
            <div className="flex items-center gap-2 text-sm text-muted-foreground pb-2">
                <Folder className="h-4 w-4" />
                Configure general settings and feature parameters.
            </div>
            {/* Repo Tabs */}
            <div className="flex gap-2 overflow-x-auto pb-2">
                {selectedList.map((repo) => {
                    const langCalls = repo.language?.toLowerCase();
                    const supported = langCalls ? supportedLanguages.includes(langCalls) : false;

                    return (
                        <button
                            key={repo.github_repo_id}
                            className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors flex items-center gap-2 ${activeRepo === String(repo.github_repo_id)
                                ? "bg-primary text-primary-foreground"
                                : "bg-muted hover:bg-muted/80"
                                } ${!supported ? "opacity-70" : ""}`}
                            onClick={() => setActiveRepo(String(repo.github_repo_id))}
                        >
                            {repo.full_name.split("/")[1]}
                            {!supported && (
                                <span className="flex h-4 w-4 items-center justify-center rounded-full bg-destructive/10 text-destructive text-[10px] font-bold">!</span>
                            )}
                        </button>
                    );
                })}
            </div>

            {activeRepo && currentRepo && (
                <div className="space-y-6">
                    {!isSupported && (
                        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive font-medium">
                            Language &apos;{currentRepo.language || "unknown"}&apos; is not supported. This repository will be skipped during import.
                        </div>
                    )}

                    {/* Base Config - Disable if not supported */}
                    <Card className={!isSupported ? "opacity-50 pointer-events-none" : ""}>
                        <CardHeader className="pb-4">
                            <CardTitle className="text-base">Import Settings</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="grid gap-4 sm:grid-cols-3">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium">CI Provider</label>
                                    <Select
                                        disabled={!isSupported}
                                        value={baseConfigs[activeRepo]?.ci_provider || CIProvider.GITHUB_ACTIONS}
                                        onValueChange={(val) => setBaseConfigs(prev => ({
                                            ...prev,
                                            [activeRepo]: { ...prev[activeRepo], ci_provider: val }
                                        }))}
                                    >
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value={CIProvider.GITHUB_ACTIONS}>GitHub Actions</SelectItem>
                                            <SelectItem value={CIProvider.TRAVIS_CI}>Travis CI</SelectItem>
                                            <SelectItem value={CIProvider.CIRCLECI}>CircleCI</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-sm font-medium">Max Builds</label>
                                    <Input
                                        disabled={!isSupported}
                                        type="number"
                                        placeholder="Unlimited"
                                        min={1}
                                        value={baseConfigs[activeRepo]?.max_builds || ""}
                                        onChange={(e) => setBaseConfigs(prev => ({
                                            ...prev,
                                            [activeRepo]: { ...prev[activeRepo], max_builds: e.target.value ? parseInt(e.target.value) : null }
                                        }))}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-sm font-medium">Since Days</label>
                                    <Input
                                        disabled={!isSupported}
                                        type="number"
                                        placeholder="Unlimited"
                                        min={1}
                                        value={baseConfigs[activeRepo]?.since_days || ""}
                                        onChange={(e) => setBaseConfigs(prev => ({
                                            ...prev,
                                            [activeRepo]: { ...prev[activeRepo], since_days: e.target.value ? parseInt(e.target.value) : null }
                                        }))}
                                    />
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Feature Config - only render after template is applied */}
                    {templateApplied && isSupported && (
                        <FeatureConfigForm
                            selectedFeatures={featureFormFeatures}
                            repos={featureFormRepos}
                            repoLanguages={repoLanguages}
                            onChange={setFeatureConfigs}
                            showValidationStatusColumn={false}
                        />
                    )}
                </div>
            )}
        </div>
    );
}

// Repo Item Component
function RepoItem({
    repo,
    isSelected,
    onToggle,
    isSupported,
}: {
    repo: RepoSuggestion;
    isSelected: boolean;
    onToggle: () => void;
    isSupported: boolean;
}) {
    const language = repo.language || "Unknown";

    return (
        <label
            className={`flex items-start gap-3 rounded-lg border p-4 transition-colors ${!isSupported
                ? "opacity-50 cursor-not-allowed bg-muted/20"
                : isSelected
                    ? "bg-primary/5 border-primary/30 dark:bg-primary/10 cursor-pointer"
                    : "hover:bg-muted/50 cursor-pointer"
                }`}
        >
            <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary disabled:opacity-50"
                checked={isSelected}
                onChange={onToggle}
                disabled={!isSupported}
            />
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                    <span className={`font-medium text-sm ${!isSupported ? "text-muted-foreground" : ""}`}>
                        {repo.full_name}
                    </span>
                    {repo.private && (
                        <Badge variant="secondary" className="text-[10px] h-5">Private</Badge>
                    )}
                    <Badge
                        variant={isSupported ? "outline" : "destructive"}
                        className={`text-[10px] h-5 ${isSupported ? "" : "bg-destructive/10"}`}
                    >
                        {language}
                    </Badge>
                    {!isSupported && (
                        <span className="text-[10px] text-destructive font-medium">Not supported</span>
                    )}
                </div>
                <p className="text-xs text-muted-foreground line-clamp-1 mt-1">
                    {repo.description || "No description provided"}
                </p>
            </div>
        </label>
    );
}

// Selected Repos Preview
function SelectedReposPreview({
    selectedList,
    onRemove,
}: {
    selectedList: RepoSuggestion[];
    onRemove: (repo: RepoSuggestion) => void;
}) {
    if (selectedList.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mb-3">
                    <Search className="h-5 w-5 text-muted-foreground" />
                </div>
                <p className="text-sm text-muted-foreground">
                    Select repositories from the list
                </p>
            </div>
        );
    }

    return (
        <div className="space-y-2">
            {selectedList.map((repo) => (
                <div
                    key={repo.github_repo_id}
                    className="flex items-center justify-between gap-2 rounded-lg border bg-background p-3"
                >
                    <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">{repo.full_name}</p>
                        <p className="text-xs text-muted-foreground truncate">
                            {repo.description || "No description"}
                        </p>
                    </div>
                    <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                        onClick={() => onRemove(repo)}
                    >
                        <X className="h-4 w-4" />
                    </Button>
                </div>
            ))}
        </div>
    );
}
