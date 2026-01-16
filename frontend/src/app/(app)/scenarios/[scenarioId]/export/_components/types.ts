// =============================================================================
// Types
// =============================================================================

export interface ExportConfig {
    name: string;
    // Preprocessing
    missing_values_strategy: "drop_row" | "fill_mean" | "fill_median" | "fill_zero";
    normalization: "none" | "z_score" | "min_max" | "robust";
    // Splitting
    strategy: string;
    group_by: string;
    ratios: { train: number; val: number; test: number };
    stratify_by: string;
    // Dynamic binning
    num_bins: number;
    time_slots: number;
    // CV configuration
    n_folds: number;
    internal_val_ratio: number;
    // Imbalanced K-Fold specific
    imbalance_drop_rate: number;
    imbalance_drop_label: number;
    // Extreme Novelty specific
    novelty_target_label: number;
    // Output
    format: "parquet" | "csv";
}

export interface GroupPreview {
    groups: Array<{ value: string; label: string; count: number; warning?: string }>;
    total_builds: number;
}

export interface StrategyOption {
    value: string;
    label: string;
    description: string;
    requiresGroupBy: boolean;
    minGroups?: number;
}

export interface GroupByOption {
    value: string;
    label: string;
    description: string;
}

// =============================================================================
// Constants
// =============================================================================

export const DEFAULT_CONFIG: ExportConfig = {
    name: "",
    missing_values_strategy: "drop_row",
    normalization: "z_score",
    strategy: "stratified_within_group",
    group_by: "repo_language",
    ratios: { train: 0.7, val: 0.15, test: 0.15 },
    stratify_by: "build_status_num",
    num_bins: 4,
    time_slots: 4,
    n_folds: 5,
    internal_val_ratio: 0.2,
    imbalance_drop_rate: 0.5,
    imbalance_drop_label: 1,
    novelty_target_label: 1,
    format: "parquet",
};

// Strategy value constants - use these instead of inline strings
export const STRATEGY = {
    STRATIFIED_WITHIN_GROUP: "stratified_within_group",
    STRATIFIED_SPLIT: "stratified_split",
    RANDOM_SPLIT: "random_split",
    TIME_SERIES_SPLIT: "time_series_split",
    L1GO_CV: "l1go_cv",
    L2GO_CV: "l2go_cv",
    EXTREME_NOVELTY_CV: "extreme_novelty_cv",
    IMBALANCED_KFOLD_CV: "imbalanced_kfold_cv",
} as const;

// Group by dimension constants
export const GROUP_BY = {
    REPO_LANGUAGE: "repo_language",
    TIME_OF_DAY: "time_of_day",
    PERCENTAGE_OF_BUILDS_BEFORE: "percentage_of_builds_before",
    NUMBER_OF_BUILDS_BEFORE: "number_of_builds_before",
} as const;

export const MISSING_VALUES_OPTIONS = [
    { value: "drop_row", label: "Drop Row" },
    { value: "fill_mean", label: "Fill with Mean" },
    { value: "fill_median", label: "Fill with Median" },
    { value: "fill_zero", label: "Fill with Zero" },
] as const;

export const NORMALIZATION_OPTIONS = [
    { value: "none", label: "None" },
    { value: "z_score", label: "Z-Score (StandardScaler)" },
    { value: "min_max", label: "Min-Max (0-1)" },
    { value: "robust", label: "Robust (IQR)" },
] as const;

export const STRATEGY_OPTIONS: StrategyOption[] = [
    {
        value: "stratified_within_group",
        label: "Stratified Within Group",
        description: "Split data within each group maintaining class distribution",
        requiresGroupBy: true,
    },
    {
        value: "stratified_split",
        label: "Stratified Split",
        description: "Maintains label distribution globally (like random but preserves class balance)",
        requiresGroupBy: false,
    },
    {
        value: "random_split",
        label: "Random Split",
        description: "Simple random split without grouping consideration",
        requiresGroupBy: false,
    },
    {
        value: "time_series_split",
        label: "Time Series Split",
        description: "Chronological split respecting temporal order (Train=oldest → Test=newest)",
        requiresGroupBy: false,
    },
    {
        value: "l1go_cv",
        label: "L1GO Cross-Validation",
        description: "Leave-One-Group-Out: Each group takes turn as test set",
        requiresGroupBy: true,
        minGroups: 3,
    },
    {
        value: "l2go_cv",
        label: "L2GO Cross-Validation",
        description: "Leave-Two-Groups-Out: Each pair of groups as test set",
        requiresGroupBy: true,
        minGroups: 3,
    },
];

export const GROUP_BY_OPTIONS: GroupByOption[] = [
    { value: "repo_language", label: "Language", description: "Group by programming language" },
    { value: "time_of_day", label: "Time of Day", description: "Group by build hour slots" },
    { value: "percentage_of_builds_before", label: "% of Builds Before", description: "Group by relative build position" },
    { value: "number_of_builds_before", label: "# of Builds Before", description: "Group by absolute build count" },
];

export const LABEL_OPTIONS = [
    { value: 0, label: "Success (0)" },
    { value: 1, label: "Failure (1)" },
] as const;

// =============================================================================
// Helper functions
// =============================================================================

const GROUP_BASED_CV_STRATEGIES: string[] = [
    STRATEGY.L1GO_CV,
    STRATEGY.L2GO_CV,
    STRATEGY.EXTREME_NOVELTY_CV
];

const ALL_CV_STRATEGIES: string[] = [
    STRATEGY.L1GO_CV,
    STRATEGY.L2GO_CV,
    STRATEGY.EXTREME_NOVELTY_CV,
    STRATEGY.IMBALANCED_KFOLD_CV
];

export function isGroupBasedCV(strategy: string): boolean {
    return GROUP_BASED_CV_STRATEGIES.includes(strategy);
}

export function isCVStrategy(strategy: string): boolean {
    return ALL_CV_STRATEGIES.includes(strategy);
}

export function getStrategyOption(strategy: string): StrategyOption | undefined {
    return STRATEGY_OPTIONS.find(s => s.value === strategy);
}

export function requiresGroupBy(strategy: string): boolean {
    return getStrategyOption(strategy)?.requiresGroupBy ?? true;
}

export function showNumBins(strategy: string, groupBy: string): boolean {
    return requiresGroupBy(strategy) && (
        [GROUP_BY.PERCENTAGE_OF_BUILDS_BEFORE, GROUP_BY.NUMBER_OF_BUILDS_BEFORE] as string[]
    ).includes(groupBy);
}

export function showTimeSlots(strategy: string, groupBy: string): boolean {
    return requiresGroupBy(strategy) && groupBy === GROUP_BY.TIME_OF_DAY;
}
