"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Loader2, RefreshCw, AlertTriangle } from "lucide-react";
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import {
    ExportConfig,
    GroupPreview,
    STRATEGY,
    GROUP_BY,
    STRATEGY_OPTIONS,
    GROUP_BY_OPTIONS,
    LABEL_OPTIONS,
    getStrategyOption,
    isGroupBasedCV,
    isCVStrategy,
    requiresGroupBy as checkRequiresGroupBy,
    showNumBins as checkShowNumBins,
    showTimeSlots as checkShowTimeSlots,
} from "./types";
import { RatioSlider } from "@/components/ui/ratio-slider";

interface SplittingStrategySectionProps {
    config: ExportConfig;
    updateConfig: (updates: Partial<ExportConfig>) => void;
    updateRatios: (key: "train" | "val" | "test", value: number) => void;
    groupsPreview: GroupPreview | null;
    loadingGroups: boolean;
    fetchGroupsPreview: () => void;
    validationError: string | null;
}

export function SplittingStrategySection({
    config,
    updateConfig,
    updateRatios,
    groupsPreview,
    loadingGroups,
    fetchGroupsPreview,
    validationError,
}: SplittingStrategySectionProps) {
    const currentStrategyOption = getStrategyOption(config.strategy);
    const requiresGroupBy = checkRequiresGroupBy(config.strategy);
    const isGroupBased = isGroupBasedCV(config.strategy);
    const isCV = isCVStrategy(config.strategy);
    const showNumBins = checkShowNumBins(config.strategy, config.group_by);
    const showTimeSlots = checkShowTimeSlots(config.strategy, config.group_by);
    const requiresGroupSelection = config.strategy === STRATEGY.STRATIFIED_WITHIN_GROUP;

    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-lg">2. Splitting Strategy</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
                {/* Strategy and Group By Selection */}
                <div className="grid gap-6 md:grid-cols-2">
                    <div className="space-y-2">
                        <Label>Strategy</Label>
                        <Select
                            value={config.strategy}
                            onValueChange={(v: string) => updateConfig({ strategy: v })}
                        >
                            <SelectTrigger>
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {STRATEGY_OPTIONS.map((opt) => (
                                    <SelectItem key={opt.value} value={opt.value}>
                                        <div className="flex flex-col">
                                            <span>{opt.label}</span>
                                        </div>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        {currentStrategyOption?.description && (
                            <p className="text-xs text-muted-foreground">
                                {currentStrategyOption.description}
                            </p>
                        )}
                    </div>

                    {requiresGroupBy ? (
                        <div className="space-y-2">
                            <Label>Group By</Label>
                            <Select
                                value={config.group_by}
                                onValueChange={(v: string) => updateConfig({ group_by: v })}
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
                            <p className="text-xs text-muted-foreground">
                                {GROUP_BY_OPTIONS.find((g) => g.value === config.group_by)?.description}
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            <Label className="text-muted-foreground">Group By</Label>
                            <div className="p-2 border rounded-md bg-muted/50 text-sm text-muted-foreground">
                                Not applicable for this strategy
                            </div>
                        </div>
                    )}
                </div>

                {/* Dynamic Binning Options */}
                {(showNumBins || showTimeSlots) && (
                    <div className="space-y-4 pt-4 border-t">
                        <Label>Grouping Configuration</Label>
                        <div className="grid gap-6 md:grid-cols-2">
                            {showNumBins && (
                                <div className="space-y-2">
                                    <div className="flex justify-between">
                                        <span className="text-sm text-muted-foreground">Number of Bins</span>
                                        <span className="text-sm font-medium">{config.num_bins}</span>
                                    </div>
                                    <Slider
                                        value={[config.num_bins]}
                                        onValueChange={([v]: number[]) => updateConfig({ num_bins: v })}
                                        min={2}
                                        max={10}
                                        step={1}
                                    />
                                </div>
                            )}
                            {showTimeSlots && (
                                <div className="space-y-2">
                                    <div className="flex justify-between">
                                        <span className="text-sm text-muted-foreground">Time Slots</span>
                                        <span className="text-sm font-medium">{config.time_slots}</span>
                                    </div>
                                    <Slider
                                        value={[config.time_slots]}
                                        onValueChange={([v]: number[]) => updateConfig({ time_slots: v })}
                                        min={2}
                                        max={12}
                                        step={1}
                                    />
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Group Preview Table */}
                {requiresGroupBy && (isGroupBased || requiresGroupSelection) && groupsPreview && (
                    <div className="space-y-4 pt-4 border-t">
                        <div className="flex items-center justify-between">
                            <Label>
                                Available Groups ({groupsPreview.groups.length})
                                {isGroupBased && (
                                    <span className="ml-2 text-xs text-muted-foreground">
                                        (CV will iterate all groups)
                                    </span>
                                )}
                            </Label>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={fetchGroupsPreview}
                                disabled={loadingGroups}
                            >
                                {loadingGroups ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <RefreshCw className="h-4 w-4" />
                                )}
                            </Button>
                        </div>
                        <div className="border rounded-lg overflow-hidden max-h-48 overflow-y-auto">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Group</TableHead>
                                        <TableHead className="text-right">Count</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {groupsPreview.groups.map((g) => (
                                        <TableRow key={g.value}>
                                            <TableCell className="font-medium">{g.label || g.value}</TableCell>
                                            <TableCell className="text-right">
                                                {g.count.toLocaleString()}
                                                {g.warning && (
                                                    <Badge variant="outline" className="ml-2 text-xs text-amber-600">
                                                        Small sample
                                                    </Badge>
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    </div>
                )}

                {/* CV Configuration: Validation Ratio - for group-based CV only */}
                {isGroupBased && (
                    <div className="space-y-4 pt-4 border-t">
                        <Label>Cross-Validation Settings</Label>
                        <div className="space-y-4">
                            <div className="space-y-2">
                                <div className="flex justify-between">
                                    <span className="text-sm text-muted-foreground">
                                        Internal Validation Ratio
                                    </span>
                                    <span className="text-sm font-medium">
                                        {(config.internal_val_ratio * 100).toFixed(0)}%
                                    </span>
                                </div>
                                <Slider
                                    value={[config.internal_val_ratio * 100]}
                                    onValueChange={([v]: number[]) =>
                                        updateConfig({ internal_val_ratio: v / 100 })
                                    }
                                    min={5}
                                    max={50}
                                    step={5}
                                />
                                <p className="text-xs text-muted-foreground">
                                    Percentage of non-test data used for validation in each fold.
                                </p>
                            </div>
                        </div>
                    </div>
                )}

                {/* Extreme Novelty CV Configuration */}
                {config.strategy === STRATEGY.EXTREME_NOVELTY_CV && (
                    <div className="space-y-4 pt-4 border-t">
                        <Label>Extreme Novelty Target Label</Label>
                        <Select
                            value={String(config.novelty_target_label)}
                            onValueChange={(v: string) =>
                                updateConfig({ novelty_target_label: parseInt(v) })
                            }
                        >
                            <SelectTrigger>
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {LABEL_OPTIONS.map((opt) => (
                                    <SelectItem key={opt.value} value={String(opt.value)}>
                                        {opt.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <p className="text-xs text-muted-foreground">
                            Label to isolate for zero-shot detection. CV will iterate through all groups.
                        </p>
                    </div>
                )}

                {/* Imbalanced K-Fold CV Configuration */}
                {config.strategy === STRATEGY.IMBALANCED_KFOLD_CV && (
                    <div className="space-y-4 pt-4 border-t">
                        <Label>Imbalanced K-Fold Configuration</Label>
                        <div className="grid gap-4 md:grid-cols-2">
                            <div className="space-y-2">
                                <div className="flex justify-between">
                                    <span className="text-sm text-muted-foreground">Number of Folds</span>
                                    <span className="text-sm font-medium">{config.n_folds}</span>
                                </div>
                                <Slider
                                    value={[config.n_folds]}
                                    onValueChange={([v]: number[]) => updateConfig({ n_folds: v })}
                                    min={2}
                                    max={20}
                                    step={1}
                                />
                            </div>
                            <div className="space-y-2">
                                <div className="flex justify-between">
                                    <span className="text-sm text-muted-foreground">Label Drop Rate</span>
                                    <span className="text-sm font-medium">
                                        {(config.imbalance_drop_rate * 100).toFixed(0)}%
                                    </span>
                                </div>
                                <Slider
                                    value={[config.imbalance_drop_rate * 100]}
                                    onValueChange={([v]: number[]) =>
                                        updateConfig({ imbalance_drop_rate: v / 100 })
                                    }
                                    min={0}
                                    max={90}
                                    step={10}
                                />
                            </div>
                        </div>
                        <p className="text-xs text-muted-foreground">
                            Percentage of failure samples (Label {config.imbalance_drop_label}) to remove
                            from training set in each fold.
                        </p>
                    </div>
                )}

                {/* Ratios - show for non-CV strategies */}
                {!isCV && (
                    <div className="space-y-4 pt-4 border-t">
                        <Label>Train / Validation / Test Ratios</Label>
                        <RatioSlider
                            ratios={config.ratios}
                            onChange={(newRatios) => updateConfig({ ratios: newRatios })}
                        />
                    </div>
                )}

                {/* Validation Error */}
                {validationError && (
                    <div className="p-3 border border-amber-500 bg-amber-50 dark:bg-amber-950/20 rounded-lg flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4 text-amber-500" />
                        <span className="text-sm text-amber-700 dark:text-amber-400">
                            {validationError}
                        </span>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
