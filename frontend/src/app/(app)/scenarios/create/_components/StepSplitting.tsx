"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Layers, HelpCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
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

import { useWizard } from "./WizardContext";

const SPLITTING_STRATEGIES = [
    {
        value: "random_split",
        label: "Random Split",
        description: "Randomly assigns builds to sets based on ratios.",
    },
    {
        value: "time_series_split",
        label: "Time Series Split",
        description: "Splits based on time (Train < Val < Test). Recommended for build data.",
    },
    {
        value: "stratified_split",
        label: "Stratified Split",
        description: "Maintains distribution of a target variable (e.g., outcome) across sets.",
    },
    {
        value: "stratified_within_group",
        label: "Stratified Within Group",
        description: "Splits time-series wise within each group (e.g. per repo).",
    },
];

const GROUP_BY_OPTIONS = [
    { value: "repo_name", label: "Repository Name" },
    { value: "language", label: "Language" },
    { value: "ci_provider", label: "CI Provider" },
];

const STRATIFY_BY_OPTIONS = [
    { value: "outcome", label: "Build Outcome" },
    { value: "conclusion", label: "Conclusion (Detailed)" },
];

export function StepSplitting() {
    const { state, updateSplitting, setStep } = useWizard();
    const { splitting } = state;

    // Local state for sliders to debounce or just direct update
    // We update context directly for simplicity as there is no heavy calc
    const [trainRatio, setTrainRatio] = useState(splitting.ratios.train * 100);
    const [valRatio, setValRatio] = useState(splitting.ratios.val * 100);
    const [testRatio, setTestRatio] = useState(splitting.ratios.test * 100);

    // Sync from context on mount
    useEffect(() => {
        setTrainRatio(splitting.ratios.train * 100);
        setValRatio(splitting.ratios.val * 100);
        setTestRatio(splitting.ratios.test * 100);
    }, [splitting.ratios]);

    // Handle slider changes - we need to balance them to sum to 100
    // Simplified: User sets Train and Val, Test is remainder
    const handleTrainChange = (value: number[]) => {
        const newTrain = value[0];
        let newVal = valRatio;
        if (newTrain + newVal > 100) {
            newVal = 100 - newTrain;
        }
        const newTest = 100 - newTrain - newVal;

        setTrainRatio(newTrain);
        setValRatio(newVal);
        setTestRatio(newTest);

        updateSplitting({
            ratios: {
                train: newTrain / 100,
                val: newVal / 100,
                test: newTest / 100,
            },
        });
    };

    const handleValChange = (value: number[]) => {
        const newVal = value[0];
        let newTrain = trainRatio;
        if (newTrain + newVal > 100) {
            newTrain = 100 - newVal;
        }
        const newTest = 100 - newTrain - newVal;

        setTrainRatio(newTrain);
        setValRatio(newVal);
        setTestRatio(newTest);

        updateSplitting({
            ratios: {
                train: newTrain / 100,
                val: newVal / 100,
                test: newTest / 100,
            },
        });
    };

    const isGroupedStrategy =
        splitting.strategy === "stratified_within_group" ||
        splitting.strategy === "group_k_fold"; // if supported

    const isStratifiedStrategy =
        splitting.strategy === "stratified_split" ||
        splitting.strategy === "stratified_within_group";

    return (
        <div className="space-y-6 max-w-4xl mx-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">Splitting Strategy</h2>
                    <p className="text-muted-foreground">
                        Configure how your dataset will be split into training, validation, and test sets.
                    </p>
                </div>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle className="items-center gap-2 flex">
                        <Layers className="h-5 w-5" />
                        Strategy Configuration
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-8">
                    {/* Strategy Selection */}
                    <div className="space-y-3">
                        <Label>Splitting Strategy</Label>
                        <Select
                            value={splitting.strategy}
                            onValueChange={(value) => updateSplitting({ strategy: value })}
                        >
                            <SelectTrigger className="w-full md:w-[400px]">
                                <SelectValue placeholder="Select strategy" />
                            </SelectTrigger>
                            <SelectContent>
                                {SPLITTING_STRATEGIES.map((s) => (
                                    <SelectItem key={s.value} value={s.value}>
                                        <div className="flex flex-col items-start py-1">
                                            <span className="font-medium">{s.label}</span>
                                            <span className="text-xs text-muted-foreground">{s.description}</span>
                                        </div>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Parameters Grid */}
                    <div className="grid gap-6 md:grid-cols-2">
                        {/* Group By - Only if valid for strategy */}
                        {isGroupedStrategy && (
                            <div className="space-y-3">
                                <div className="flex items-center gap-2">
                                    <Label>Group By</Label>
                                    <TooltipProvider>
                                        <Tooltip>
                                            <TooltipTrigger>
                                                <HelpCircle className="h-4 w-4 text-muted-foreground" />
                                            </TooltipTrigger>
                                            <TooltipContent>
                                                <p>Dimension to group data by before splitting (e.g. per repository)</p>
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
                        )}

                        {/* Stratify By - Only if valid for strategy */}
                        {isStratifiedStrategy && (
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
                        )}
                    </div>

                    {/* Ratios */}
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
                                max={100 - trainRatio} // Can't exceed remaining
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
                </CardContent>
            </Card>

            {/* Navigation */}
            <div className="flex justify-between">
                <Button variant="outline" onClick={() => setStep(2)}>
                    <ArrowLeft className="h-4 w-4 mr-2" />
                    Back
                </Button>
                <Button onClick={() => setStep(4)}>
                    Next: Preprocessing
                    <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
            </div>
        </div>
    );
}
