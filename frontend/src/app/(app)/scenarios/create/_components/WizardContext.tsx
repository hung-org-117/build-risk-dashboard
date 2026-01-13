"use client";

import { createContext, useContext, useState, useCallback, useMemo, ReactNode } from "react";

// =============================================================================
// Constants (moved from deleted splitting/constants.ts)
// =============================================================================

export const CI_PROVIDERS = [
    { value: "all", label: "All CI Providers" },
    { value: "github_actions", label: "GitHub Actions" },
    { value: "circleci", label: "CircleCI" },
    { value: "travis_ci", label: "Travis CI" },
] as const;

export const BUILD_CONCLUSIONS = [
    { value: "success", label: "Success" },
    { value: "failure", label: "Failure" },
] as const;

export const SUPPORTED_LANGUAGES = [
    { value: "python", label: "Python" },
    { value: "javascript", label: "JavaScript" },
    { value: "typescript", label: "TypeScript" },
    { value: "java", label: "Java" },
    { value: "go", label: "Go" },
    { value: "ruby", label: "Ruby" },
    { value: "rust", label: "Rust" },
    { value: "c", label: "C" },
    { value: "cpp", label: "C++" },
    { value: "csharp", label: "C#" },
    { value: "php", label: "PHP" },
    { value: "swift", label: "Swift" },
    { value: "kotlin", label: "Kotlin" },
    { value: "scala", label: "Scala" },
] as const;

export type CIProviderKey = (typeof CI_PROVIDERS)[number]["value"];
export type BuildConclusionKey = (typeof BUILD_CONCLUSIONS)[number]["value"];
export type LanguageKey = (typeof SUPPORTED_LANGUAGES)[number]["value"];

// =============================================================================
// Types
// =============================================================================

export interface DataSourceConfig {
    filter_by: "all" | "by_language" | "by_name";
    languages: string[];
    repo_names: string[];
    date_start: string;
    date_end: string;
    conclusions: string[];
    ci_provider: CIProviderKey | "all";
}

export interface FeatureConfig {
    dag_features: string[];
    scan_metrics: {
        sonarqube: string[];
        trivy: string[];
    };
    exclude: string[];
}

export interface PreviewStats {
    total_builds: number;
    total_repos: number;
    outcome_distribution: {
        success: number;
        failure: number;
    };
    repos?: { id: string; full_name: string }[];
}

export interface WizardState {
    // Current step (1-3: Data Source → Features → Review)
    step: number;

    // Scenario metadata
    name: string;
    description: string;

    // Step 1: Data Source
    dataSource: DataSourceConfig;
    previewStats: PreviewStats | null;
    previewRepos: { id: string; full_name: string }[];

    // Step 2: Features
    features: FeatureConfig;
    featureConfigs: Record<string, any>; // Detailed feature params
    scanConfigs: Record<string, any>; // Detailed scan params

    // Loading states
    isPreviewLoading: boolean;
    isSubmitting: boolean;
}

interface WizardContextValue {
    state: WizardState;
    setStep: (step: number) => void;
    setName: (name: string) => void;
    setDescription: (description: string) => void;
    updateDataSource: (updates: Partial<DataSourceConfig>) => void;
    setPreviewStats: (stats: PreviewStats | null) => void;
    setPreviewRepos: (repos: { id: string; full_name: string }[]) => void;
    updateFeatures: (updates: Partial<FeatureConfig>) => void;
    setFeatureConfigs: (configs: Record<string, any>) => void;
    setScanConfigs: (configs: Record<string, any>) => void;
    setIsPreviewLoading: (loading: boolean) => void;
    setIsSubmitting: (submitting: boolean) => void;
    resetState: () => void;
}

// =============================================================================
// Initial State
// =============================================================================

const initialDataSource: DataSourceConfig = {
    filter_by: "all",
    languages: [],
    repo_names: [],
    date_start: "",
    date_end: "",
    conclusions: ["success", "failure"],
    ci_provider: "all",
};

const initialFeatures: FeatureConfig = {
    dag_features: ["build_*", "git_*", "log_*", "repo_*", "history_*", "author_*"],
    scan_metrics: {
        sonarqube: [],
        trivy: [],
    },
    exclude: [],
};

const initialState: WizardState = {
    step: 1,
    name: "",
    description: "",
    dataSource: initialDataSource,
    previewStats: null,
    previewRepos: [],
    features: initialFeatures,
    featureConfigs: {},
    scanConfigs: {},
    isPreviewLoading: false,
    isSubmitting: false,
};

// =============================================================================
// Context
// =============================================================================

const WizardContext = createContext<WizardContextValue | null>(null);

export function WizardProvider({ children }: { children: ReactNode }) {
    const [state, setState] = useState<WizardState>(initialState);

    const setStep = useCallback((step: number) => setState((s) => ({ ...s, step })), []);
    const setName = useCallback((name: string) => setState((s) => ({ ...s, name })), []);
    const setDescription = useCallback((description: string) => setState((s) => ({ ...s, description })), []);

    const updateDataSource = useCallback((updates: Partial<DataSourceConfig>) =>
        setState((s) => ({ ...s, dataSource: { ...s.dataSource, ...updates } })), []);

    const setPreviewStats = useCallback((stats: PreviewStats | null) =>
        setState((s) => ({ ...s, previewStats: stats })), []);

    const setPreviewRepos = useCallback((repos: { id: string; full_name: string }[]) =>
        setState((s) => ({ ...s, previewRepos: repos })), []);

    const updateFeatures = useCallback((updates: Partial<FeatureConfig>) =>
        setState((s) => ({ ...s, features: { ...s.features, ...updates } })), []);

    const setFeatureConfigs = useCallback((configs: Record<string, any>) =>
        setState((s) => ({ ...s, featureConfigs: configs })), []);

    const setScanConfigs = useCallback((configs: Record<string, any>) =>
        setState((s) => ({ ...s, scanConfigs: configs })), []);

    const setIsPreviewLoading = useCallback((loading: boolean) =>
        setState((s) => ({ ...s, isPreviewLoading: loading })), []);

    const setIsSubmitting = useCallback((submitting: boolean) =>
        setState((s) => ({ ...s, isSubmitting: submitting })), []);

    const resetState = useCallback(() => setState(initialState), []);

    const value = useMemo(
        () => ({
            state,
            setStep,
            setName,
            setDescription,
            updateDataSource,
            setPreviewStats,
            setPreviewRepos,
            updateFeatures,
            setFeatureConfigs,
            setScanConfigs,
            setIsPreviewLoading,
            setIsSubmitting,
            resetState,
        }),
        [
            state,
            setStep,
            setName,
            setDescription,
            updateDataSource,
            setPreviewStats,
            setPreviewRepos,
            updateFeatures,
            setFeatureConfigs,
            setScanConfigs,
            setIsPreviewLoading,
            setIsSubmitting,
            resetState,
        ]
    );

    return (
        <WizardContext.Provider value={value}>
            {children}
        </WizardContext.Provider>
    );
}

export function useWizard() {
    const context = useContext(WizardContext);
    if (!context) {
        throw new Error("useWizard must be used within a WizardProvider");
    }
    return context;
}
