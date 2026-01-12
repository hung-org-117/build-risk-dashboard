"use client";

import { useEffect, useState } from "react";
import { Layers } from "lucide-react";

import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

import { useWizard } from "./WizardContext";
import {
    SPLITTING_STRATEGIES,
    getStrategyMetadata,
    GroupByConfig,
    StratifyByConfig,
    RatioConfig,
} from "./splitting/strategy-configs";

export function StepSplitting() {
    const { state, updateSplitting } = useWizard();
    const { splitting } = state;

    // Local state for ratio sliders
    const [trainRatio, setTrainRatio] = useState(splitting.ratios.train * 100);
    const [valRatio, setValRatio] = useState(splitting.ratios.val * 100);
    const [testRatio, setTestRatio] = useState(splitting.ratios.test * 100);

    // Sync from context on mount
    useEffect(() => {
        setTrainRatio(splitting.ratios.train * 100);
        setValRatio(splitting.ratios.val * 100);
        setTestRatio(splitting.ratios.test * 100);
    }, [splitting.ratios]);

    // Handle slider changes - balance to sum to 100
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

    // Get current strategy metadata
    const strategyMeta = getStrategyMetadata(splitting.strategy);

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

                    {/* Parameters Grid - Group By & Stratify By */}
                    <div className="grid gap-6 md:grid-cols-2">
                        {strategyMeta?.showGroupBy && (
                            <GroupByConfig splitting={splitting} updateSplitting={updateSplitting} />
                        )}
                        {strategyMeta?.showStratifyBy && (
                            <StratifyByConfig splitting={splitting} updateSplitting={updateSplitting} />
                        )}
                    </div>

                    {/* Strategy-specific config component */}
                    {strategyMeta?.ConfigComponent && (
                        <strategyMeta.ConfigComponent splitting={splitting} updateSplitting={updateSplitting} />
                    )}

                    {/* Ratios - only for ratio-based strategies */}
                    {strategyMeta?.showRatios && (
                        <RatioConfig
                            splitting={splitting}
                            updateSplitting={updateSplitting}
                            trainRatio={trainRatio}
                            valRatio={valRatio}
                            testRatio={testRatio}
                            handleTrainChange={handleTrainChange}
                            handleValChange={handleValChange}
                        />
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
