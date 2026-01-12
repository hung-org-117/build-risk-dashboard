"use client";

/**
 * Strategy Configuration Components
 * 
 * Each splitting strategy has its own config component that renders
 * the appropriate configuration fields.
 */

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { HelpCircle } from "lucide-react";

// ============================================================================
// Types
// ============================================================================

export interface SplittingState {
    strategy: string;
    group_by: string;
    stratify_by: string;
    ratios: { train: number; val: number; test: number };
    test_groups?: string[];
    val_groups?: string[];
    reduce_label?: number;
    reduce_ratio: number;
    novelty_group?: string;
    novelty_label?: number;
}

export interface StrategyConfigProps {
    splitting: SplittingState;
    updateSplitting: (updates: Partial<SplittingState>) => void;
}

export interface RatioConfigProps extends StrategyConfigProps {
    trainRatio: number;
    valRatio: number;
    testRatio: number;
    handleTrainChange: (value: number[]) => void;
    handleValChange: (value: number[]) => void;
}

// ============================================================================
// Constants
// ============================================================================

export const GROUP_BY_OPTIONS = [
    { value: "repo_full_name", label: "Repository Name" },
    { value: "repo_language", label: "Language" },
    { value: "build_ci_provider", label: "CI Provider" },
    { value: "percentage_of_builds_before", label: "Percentage of Builds Before" },
    { value: "number_of_builds_before", label: "Number of Builds Before" },
    { value: "time_of_day", label: "Time of Day" },
];

export const STRATIFY_BY_OPTIONS = [
    { value: "outcome", label: "Build Outcome" },
];

// ============================================================================
// Strategy Metadata Registry
// ============================================================================

export interface StrategyMetadata {
    value: string;
    label: string;
    description: string;
    showGroupBy: boolean;
    showStratifyBy: boolean;
    showRatios: boolean;
    ConfigComponent?: React.FC<StrategyConfigProps>;
}

// ============================================================================
// Shared Config Components
// ============================================================================

export function GroupByConfig({ splitting, updateSplitting }: StrategyConfigProps) {
    return (
        <div className="space-y-3">
            <div className="flex items-center gap-2">
                <Label>Group By</Label>
                <TooltipProvider>
                    <Tooltip>
                        <TooltipTrigger>
                            <HelpCircle className="h-4 w-4 text-muted-foreground" />
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>Dimension to group data by before splitting</p>
                        </TooltipContent>
                    </Tooltip>
                </TooltipProvider>
            </div>
            <Select
                value={splitting.group_by}
                onValueChange={(value) => updateSplitting({ group_by: value })}
            >
                <SelectTrigger>
                    <SelectValue />
                </SelectTrigger>
                <SelectContent>
                    {GROUP_BY_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    );
}

export function StratifyByConfig({ splitting, updateSplitting }: StrategyConfigProps) {
    return (
        <div className="space-y-3">
            <div className="flex items-center gap-2">
                <Label>Stratify By</Label>
                <TooltipProvider>
                    <Tooltip>
                        <TooltipTrigger>
                            <HelpCircle className="h-4 w-4 text-muted-foreground" />
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>Target variable to maintain distribution for</p>
                        </TooltipContent>
                    </Tooltip>
                </TooltipProvider>
            </div>
            <Select
                value={splitting.stratify_by}
                onValueChange={(value) => updateSplitting({ stratify_by: value })}
            >
                <SelectTrigger>
                    <SelectValue />
                </SelectTrigger>
                <SelectContent>
                    {STRATIFY_BY_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    );
}

export function RatioConfig({
    trainRatio,
    valRatio,
    testRatio,
    handleTrainChange,
    handleValChange,
}: RatioConfigProps) {
    return (
        <div className="space-y-6 pt-4 border-t">
            <Label className="text-base">Split Ratios</Label>

            {/* Train Slider */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <Label className="text-muted-foreground">Training Set</Label>
                    <span className="font-mono font-medium">{trainRatio.toFixed(0)}%</span>
                </div>
                <Slider
                    value={[trainRatio]}
                    onValueChange={handleTrainChange}
                    max={100}
                    step={1}
                    className="[&>.bg-primary]:bg-blue-600"
                />
            </div>

            {/* Validation Slider */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <Label className="text-muted-foreground">Validation Set</Label>
                    <span className="font-mono font-medium">{valRatio.toFixed(0)}%</span>
                </div>
                <Slider
                    value={[valRatio]}
                    onValueChange={handleValChange}
                    max={100 - trainRatio}
                    step={1}
                    className="[&>.bg-primary]:bg-purple-600"
                />
            </div>

            {/* Test (Read only) */}
            <div className="p-4 bg-slate-50 dark:bg-slate-900/50 rounded-lg flex items-center justify-between border">
                <div className="flex items-center gap-2">
                    <div className="h-3 w-3 rounded-full bg-green-500" />
                    <span className="font-medium text-sm">Test Set (Remainder)</span>
                </div>
                <span className="font-mono font-bold text-lg">{testRatio.toFixed(0)}%</span>
            </div>

            {/* Visual Bar */}
            <div className="h-4 w-full rounded-full overflow-hidden flex">
                <div
                    className="h-full bg-blue-500 transition-all duration-300"
                    style={{ width: `${trainRatio}%` }}
                    title="Training"
                />
                <div
                    className="h-full bg-purple-500 transition-all duration-300"
                    style={{ width: `${valRatio}%` }}
                    title="Validation"
                />
                <div
                    className="h-full bg-green-500 transition-all duration-300"
                    style={{ width: `${testRatio}%` }}
                    title="Test"
                />
            </div>
        </div>
    );
}

// ============================================================================
// Strategy-Specific Config Components
// ============================================================================

export function LeaveOneOutConfig({ splitting, updateSplitting }: StrategyConfigProps) {
    return (
        <div className="space-y-3 border-t pt-4">
            <h4 className="text-sm font-medium">Leave-One-Out Configuration</h4>
            <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-3">
                    <Label>Test Group(s) (Required)</Label>
                    <Input
                        placeholder="e.g. python"
                        value={splitting.test_groups?.join(", ") || ""}
                        onChange={(e) => updateSplitting({
                            test_groups: e.target.value.split(",").map(s => s.trim()).filter(Boolean)
                        })}
                    />
                    <p className="text-xs text-muted-foreground">Comma separated group values</p>
                </div>
            </div>
        </div>
    );
}

export function LeaveTwoOutConfig({ splitting, updateSplitting }: StrategyConfigProps) {
    return (
        <div className="space-y-3 border-t pt-4">
            <h4 className="text-sm font-medium">Leave-Two-Out Configuration</h4>
            <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-3">
                    <Label>Test Group(s) (Required)</Label>
                    <Input
                        placeholder="e.g. python"
                        value={splitting.test_groups?.join(", ") || ""}
                        onChange={(e) => updateSplitting({
                            test_groups: e.target.value.split(",").map(s => s.trim()).filter(Boolean)
                        })}
                    />
                    <p className="text-xs text-muted-foreground">Comma separated group values</p>
                </div>
                <div className="space-y-3">
                    <Label>Validation Group(s) (Required)</Label>
                    <Input
                        placeholder="e.g. javascript"
                        value={splitting.val_groups?.join(", ") || ""}
                        onChange={(e) => updateSplitting({
                            val_groups: e.target.value.split(",").map(s => s.trim()).filter(Boolean)
                        })}
                    />
                </div>
            </div>
        </div>
    );
}

export function ImbalancedTrainConfig({ splitting, updateSplitting }: StrategyConfigProps) {
    return (
        <div className="space-y-3 border-t pt-4">
            <h4 className="text-sm font-medium">Imbalance Configuration</h4>
            <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-3">
                    <Label>Reduce Label</Label>
                    <Select
                        value={splitting.reduce_label?.toString() ?? "1"}
                        onValueChange={(value) => updateSplitting({ reduce_label: parseInt(value) })}
                    >
                        <SelectTrigger>
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="1">Failure (1)</SelectItem>
                            <SelectItem value="0">Success (0)</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
                <div className="space-y-3">
                    <Label>Reduce Ratio</Label>
                    <div className="flex items-center gap-4">
                        <Slider
                            value={[splitting.reduce_ratio * 100]}
                            onValueChange={(val) => updateSplitting({ reduce_ratio: val[0] / 100 })}
                            max={100}
                            step={1}
                            className="flex-1"
                        />
                        <span className="w-12 text-sm font-mono">
                            {(splitting.reduce_ratio * 100).toFixed(0)}%
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
}

export function ExtremeNoveltyConfig({ splitting, updateSplitting }: StrategyConfigProps) {
    return (
        <div className="space-y-3 border-t pt-4">
            <h4 className="text-sm font-medium">Novelty Configuration</h4>
            <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-3">
                    <Label>Novelty Group (Required)</Label>
                    <Input
                        placeholder="e.g. python"
                        value={splitting.novelty_group || ""}
                        onChange={(e) => updateSplitting({ novelty_group: e.target.value })}
                    />
                </div>
                <div className="space-y-3">
                    <Label>Novelty Label</Label>
                    <Select
                        value={splitting.novelty_label?.toString() ?? "1"}
                        onValueChange={(value) => updateSplitting({ novelty_label: parseInt(value) })}
                    >
                        <SelectTrigger>
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="1">Failure (1)</SelectItem>
                            <SelectItem value="0">Success (0)</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </div>
        </div>
    );
}

// ============================================================================
// Strategy Registry
// ============================================================================

export const SPLITTING_STRATEGIES: StrategyMetadata[] = [
    {
        value: "random_split",
        label: "Random Split",
        description: "Randomly assigns builds to sets based on ratios.",
        showGroupBy: false,
        showStratifyBy: false,
        showRatios: true,
    },
    {
        value: "time_series_split",
        label: "Time Series Split",
        description: "Splits based on time (Train < Val < Test). Recommended for build data.",
        showGroupBy: false,
        showStratifyBy: false,
        showRatios: true,
    },
    {
        value: "stratified_split",
        label: "Stratified Split",
        description: "Maintains distribution of outcome across sets.",
        showGroupBy: false,
        showStratifyBy: true,
        showRatios: true,
    },
    {
        value: "stratified_within_group",
        label: "Stratified Within Group",
        description: "Splits time-series wise within each group (e.g. per repo).",
        showGroupBy: true,
        showStratifyBy: true,
        showRatios: true,
    },
    {
        value: "leave_one_out",
        label: "Leave-One-Out",
        description: "Selects 1 group for Test, 1 for Val, and the rest for Train.",
        showGroupBy: true,
        showStratifyBy: false,
        showRatios: false,
        ConfigComponent: LeaveOneOutConfig,
    },
    {
        value: "leave_two_out",
        label: "Leave-Two-Out",
        description: "Selects 2 groups for Test, 1 for Val, and the rest for Train.",
        showGroupBy: true,
        showStratifyBy: false,
        showRatios: false,
        ConfigComponent: LeaveTwoOutConfig,
    },
    {
        value: "imbalanced_train",
        label: "Imbalanced Train",
        description: "Reduces label 1 (failure) samples by 50% in Train set only.",
        showGroupBy: true,
        showStratifyBy: true,
        showRatios: true,
        ConfigComponent: ImbalancedTrainConfig,
    },
    {
        value: "extreme_novelty",
        label: "Extreme Novelty in Sub-Group",
        description: "Places all samples of a specific Group+Label into Test.",
        showGroupBy: true,
        showStratifyBy: false,
        showRatios: false,
        ConfigComponent: ExtremeNoveltyConfig,
    },
];

// Helper to get strategy metadata by value
export function getStrategyMetadata(strategyValue: string): StrategyMetadata | undefined {
    return SPLITTING_STRATEGIES.find(s => s.value === strategyValue);
}
