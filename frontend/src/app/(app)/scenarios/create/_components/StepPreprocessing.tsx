"use client";

import { ArrowLeft, ArrowRight, Settings2, FileOutput, HelpCircle } from "lucide-react";

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
import { Switch } from "@/components/ui/switch";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";

import { useWizard } from "./WizardContext";

const MISSING_VALUES_STRATEGIES = [
    {
        value: "drop_row",
        label: "Drop Row",
        description: "Remove rows with any missing values",
    },
    {
        value: "fill",
        label: "Fill with Value",
        description: "Replace missing values with a specified value",
    },
    {
        value: "skip_feature",
        label: "Skip Feature",
        description: "Exclude features that have missing values",
    },
];

const NORMALIZATION_METHODS = [
    {
        value: "z_score",
        label: "Z-Score (Standard)",
        description: "Subtract mean and divide by std dev",
    },
    {
        value: "min_max",
        label: "Min-Max",
        description: "Scale to range [0, 1]",
    },
    {
        value: "robust",
        label: "Robust Scaler",
        description: "Use median and IQR (resistant to outliers)",
    },
    {
        value: "none",
        label: "None",
        description: "No normalization applied",
    },
];

const OUTPUT_FORMATS = [
    {
        value: "parquet",
        label: "Parquet",
        description: "Columnar format, efficient for ML (recommended)",
    },
    {
        value: "csv",
        label: "CSV",
        description: "Universal, human-readable",
    },
    {
        value: "pickle",
        label: "Pickle",
        description: "Python native, preserves types",
    },
];

export function StepPreprocessing() {
    const { state, updatePreprocessing, updateOutput, setStep } = useWizard();
    const { preprocessing, output } = state;

    return (
        <div className="space-y-6 max-w-4xl mx-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">Preprocessing & Output</h2>
                    <p className="text-muted-foreground">
                        Configure how data is preprocessed and the output format for the generated dataset.
                    </p>
                </div>
            </div>

            {/* Preprocessing Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="items-center gap-2 flex">
                        <Settings2 className="h-5 w-5" />
                        Data Preprocessing
                    </CardTitle>
                    <CardDescription>
                        Settings for handling missing values and feature normalization
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Missing Values Strategy */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-2">
                            <Label>Missing Values Strategy</Label>
                            <TooltipProvider>
                                <Tooltip>
                                    <TooltipTrigger>
                                        <HelpCircle className="h-4 w-4 text-muted-foreground" />
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <p>How to handle builds with missing feature values</p>
                                    </TooltipContent>
                                </Tooltip>
                            </TooltipProvider>
                        </div>
                        <Select
                            value={preprocessing.missing_values_strategy}
                            onValueChange={(value: "drop_row" | "fill" | "skip_feature") =>
                                updatePreprocessing({ missing_values_strategy: value })
                            }
                        >
                            <SelectTrigger className="w-full md:w-[400px]">
                                <SelectValue placeholder="Select strategy" />
                            </SelectTrigger>
                            <SelectContent>
                                {MISSING_VALUES_STRATEGIES.map((s) => (
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

                    {/* Fill Value - Only if fill strategy */}
                    {preprocessing.missing_values_strategy === "fill" && (
                        <div className="space-y-3">
                            <Label>Fill Value</Label>
                            <Input
                                type="number"
                                value={preprocessing.fill_value as number}
                                onChange={(e) =>
                                    updatePreprocessing({ fill_value: parseFloat(e.target.value) || 0 })
                                }
                                className="w-[200px]"
                                placeholder="0"
                            />
                            <p className="text-xs text-muted-foreground">
                                Value to use when replacing missing data
                            </p>
                        </div>
                    )}

                    {/* Normalization Method */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-2">
                            <Label>Normalization Method</Label>
                            <TooltipProvider>
                                <Tooltip>
                                    <TooltipTrigger>
                                        <HelpCircle className="h-4 w-4 text-muted-foreground" />
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <p>How to scale numeric features for ML training</p>
                                    </TooltipContent>
                                </Tooltip>
                            </TooltipProvider>
                        </div>
                        <Select
                            value={preprocessing.normalization_method}
                            onValueChange={(value: "z_score" | "min_max" | "robust" | "none") =>
                                updatePreprocessing({ normalization_method: value })
                            }
                        >
                            <SelectTrigger className="w-full md:w-[400px]">
                                <SelectValue placeholder="Select method" />
                            </SelectTrigger>
                            <SelectContent>
                                {NORMALIZATION_METHODS.map((m) => (
                                    <SelectItem key={m.value} value={m.value}>
                                        <div className="flex flex-col items-start py-1">
                                            <span className="font-medium">{m.label}</span>
                                            <span className="text-xs text-muted-foreground">{m.description}</span>
                                        </div>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Strict Mode */}
                    <div className="flex items-center justify-between p-4 border rounded-lg">
                        <div className="space-y-0.5">
                            <Label className="text-base">Strict Mode</Label>
                            <p className="text-sm text-muted-foreground">
                                Fail the entire run if any selected feature cannot be computed
                            </p>
                        </div>
                        <Switch
                            checked={preprocessing.strict_mode}
                            onCheckedChange={(checked) => updatePreprocessing({ strict_mode: checked })}
                        />
                    </div>
                </CardContent>
            </Card>

            {/* Output Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="items-center gap-2 flex">
                        <FileOutput className="h-5 w-5" />
                        Output Configuration
                    </CardTitle>
                    <CardDescription>
                        Settings for the generated dataset files
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Output Format */}
                    <div className="space-y-3">
                        <Label>Output Format</Label>
                        <Select
                            value={output.format}
                            onValueChange={(value: "parquet" | "csv" | "pickle") =>
                                updateOutput({ format: value })
                            }
                        >
                            <SelectTrigger className="w-full md:w-[400px]">
                                <SelectValue placeholder="Select format" />
                            </SelectTrigger>
                            <SelectContent>
                                {OUTPUT_FORMATS.map((f) => (
                                    <SelectItem key={f.value} value={f.value}>
                                        <div className="flex flex-col items-start py-1">
                                            <span className="font-medium">{f.label}</span>
                                            <span className="text-xs text-muted-foreground">{f.description}</span>
                                        </div>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Include Metadata */}
                    <div className="flex items-center justify-between p-4 border rounded-lg">
                        <div className="space-y-0.5">
                            <Label className="text-base">Include Metadata</Label>
                            <p className="text-sm text-muted-foreground">
                                Add build metadata columns (repo, commit, timestamps) to output
                            </p>
                        </div>
                        <Switch
                            checked={output.include_metadata}
                            onCheckedChange={(checked) => updateOutput({ include_metadata: checked })}
                        />
                    </div>
                </CardContent>
            </Card>

            {/* Navigation */}
            <div className="flex justify-between">
                <Button variant="outline" onClick={() => setStep(3)}>
                    <ArrowLeft className="h-4 w-4 mr-2" />
                    Back
                </Button>
                <Button onClick={() => setStep(5)}>
                    Next: Review
                    <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
            </div>
        </div>
    );
}
