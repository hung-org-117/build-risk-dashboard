"use client";

import { createContext, useContext, useState, useCallback, useMemo, ReactNode } from "react";

export const BUILD_CONCLUSIONS = [
    { value: "success", label: "Success" },
    { value: "failure", label: "Failure" },
] as const;
export type CIProviderKey = string;
export type BuildConclusionKey = (typeof BUILD_CONCLUSIONS)[number]["value"];
export type LanguageKey = string;
export interface DataSourceConfig {
    languages: string[];
    build_source_ids: string[];
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
    languages: [],
    build_source_ids: [],
    date_start: "",
    date_end: "",
    conclusions: ["success", "failure"],
    ci_provider: "all",
};

const initialFeatures: FeatureConfig = {
    dag_features: [],
    scan_metrics: {
        sonarqube: [],
        trivy: [],
    },
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
