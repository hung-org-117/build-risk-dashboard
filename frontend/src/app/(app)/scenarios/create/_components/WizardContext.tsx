"use client";

import { createContext, useContext, useState, useCallback, useMemo, ReactNode } from "react";

// =============================================================================
// Constants - Matching backend enums
// =============================================================================

/**
 * Supported CI providers from backend/app/ci_providers/models.py
 */
export const CI_PROVIDERS = [
    { value: "github_actions", label: "GitHub Actions" },
    { value: "circleci", label: "CircleCI" },
    { value: "travis_ci", label: "Travis CI" },
] as const;

export type CIProviderKey = typeof CI_PROVIDERS[number]["value"];

/**
 * Build conclusions that are actually stored in the database.
 * Note: SKIPPED, CANCELLED, STALE, ACTION_REQUIRED are filtered out during ingestion
 * (see dataset_validation.py and model_ingestion.py)
 */
export const BUILD_CONCLUSIONS = [
    { value: "success", label: "Success" },
    { value: "failure", label: "Failure" },
] as const;

export type BuildConclusionKey = typeof BUILD_CONCLUSIONS[number]["value"];

/**
 * Supported languages from backend/app/tasks/pipeline/feature_dag/languages/registry.py
 */
export const SUPPORTED_LANGUAGES = [
    { value: "python", label: "Python" },
    { value: "javascript", label: "JavaScript" },
    { value: "typescript", label: "TypeScript" },
    { value: "java", label: "Java" },
    { value: "go", label: "Go" },
    { value: "ruby", label: "Ruby" },
    { value: "cpp", label: "C/C++" },
] as const;

export type LanguageKey = typeof SUPPORTED_LANGUAGES[number]["value"];

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

export interface SplittingConfig {
    strategy: string;
    group_by: string;
    groups: string[];
    ratios: {
        train: number;
        val: number;
        test: number;
    };
    stratify_by: string;
    // Advanced options
    temporal_ordering: boolean;
    test_groups: string[];
    val_groups: string[];
    train_groups: string[];
    // Imbalanced train
    reduce_label?: number;
    reduce_ratio: number;
    // Novelty
    novelty_group?: string;
    novelty_label?: number;
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
    // Current step (1-5)
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

    // Step 3: Splitting
    splitting: SplittingConfig;


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
    updateSplitting: (updates: Partial<SplittingConfig>) => void;
    setIsPreviewLoading: (loading: boolean) => void;
    setIsSubmitting: (submitting: boolean) => void;
    loadFromYaml: (config: YamlConfigInput) => void;
    resetState: () => void;
}

// Input type for YAML config (matches sample YAML structure)
export interface YamlConfigInput {
    scenario?: { name?: string; description?: string };
    data_source?: {
        repositories?: { filter_by?: string; languages?: string[]; repo_names?: string[] };
        builds?: { date_range?: { start?: string; end?: string }; conclusions?: string[] };
        ci_provider?: string;
    };
    features?: { dag_features?: string[]; scan_metrics?: { sonarqube?: string[]; trivy?: string[] }; exclude?: string[] };
    splitting?: {
        strategy?: string;
        group_by?: string;
        config?: {
            ratios?: { train?: number; val?: number; test?: number };
            stratify_by?: string;
            test_groups?: string[];
            val_groups?: string[];
            reduce_label?: number;
            reduce_ratio?: number;
            novelty_group?: string;
            novelty_label?: number;
        }
    };
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

const initialSplitting: SplittingConfig = {
    strategy: "stratified_within_group",
    group_by: "language", // Default to language
    groups: [],
    ratios: { train: 0.7, val: 0.15, test: 0.15 },
    stratify_by: "outcome",
    temporal_ordering: true,
    test_groups: [],
    val_groups: [],
    train_groups: [],
    reduce_label: 1,
    reduce_ratio: 0.5,
    novelty_group: undefined,
    novelty_label: 1,
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
    splitting: initialSplitting,
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

    const updateSplitting = useCallback((updates: Partial<SplittingConfig>) =>
        setState((s) => ({ ...s, splitting: { ...s.splitting, ...updates } })), []);

    const setIsPreviewLoading = useCallback((loading: boolean) =>
        setState((s) => ({ ...s, isPreviewLoading: loading })), []);

    const setIsSubmitting = useCallback((submitting: boolean) =>
        setState((s) => ({ ...s, isSubmitting: submitting })), []);

    const loadFromYaml = useCallback((config: YamlConfigInput) => {
        setState((s) => ({
            ...s,
            name: config.scenario?.name || s.name,
            description: config.scenario?.description || s.description,
            dataSource: {
                ...s.dataSource,
                filter_by: (config.data_source?.repositories?.filter_by as any) || s.dataSource.filter_by,
                languages: config.data_source?.repositories?.languages || s.dataSource.languages,
                repo_names: config.data_source?.repositories?.repo_names || s.dataSource.repo_names,
                date_start: config.data_source?.builds?.date_range?.start || s.dataSource.date_start,
                date_end: config.data_source?.builds?.date_range?.end || s.dataSource.date_end,
                conclusions: config.data_source?.builds?.conclusions || s.dataSource.conclusions,
                ci_provider: (config.data_source?.ci_provider as any) || s.dataSource.ci_provider,
            },
            features: {
                ...s.features,
                dag_features: config.features?.dag_features || s.features.dag_features,
                scan_metrics: {
                    sonarqube: config.features?.scan_metrics?.sonarqube || s.features.scan_metrics.sonarqube,
                    trivy: config.features?.scan_metrics?.trivy || s.features.scan_metrics.trivy,
                },
                exclude: config.features?.exclude || s.features.exclude,
            },
            splitting: {
                ...s.splitting,
                strategy: config.splitting?.strategy || s.splitting.strategy,
                group_by: config.splitting?.group_by || s.splitting.group_by,
                ratios: {
                    train: config.splitting?.config?.ratios?.train ?? s.splitting.ratios.train,
                    val: config.splitting?.config?.ratios?.val ?? s.splitting.ratios.val,
                    test: config.splitting?.config?.ratios?.test ?? s.splitting.ratios.test,
                },
                stratify_by: config.splitting?.config?.stratify_by || s.splitting.stratify_by,
            },
        }));
    }, []);

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
            updateSplitting,
            setIsPreviewLoading,
            setIsSubmitting,
            loadFromYaml,
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
            updateSplitting,
            setIsPreviewLoading,
            setIsSubmitting,
            loadFromYaml,
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
