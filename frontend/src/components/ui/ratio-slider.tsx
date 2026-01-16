"use client";

import React, { useState, useEffect } from "react";
import Slider from "rc-slider";
import "rc-slider/assets/index.css";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface RatioSliderProps {
    ratios: {
        train: number;
        val: number;
        test: number;
    };
    onChange: (ratios: { train: number; val: number; test: number }) => void;
}

export function RatioSlider({ ratios, onChange }: RatioSliderProps) {
    // Internal state for handles positions (0 to 100)
    // We use 3 handles: [0, split1, split2]
    // 0 is fixed hidden handle to create the first colored segment (Train)
    // split1: Split between Train/Val
    // split2: Split between Val/Test
    // The "rail" background serves as the Test color
    const [handles, setHandles] = useState([
        0,
        ratios.train * 100,
        (ratios.train + ratios.val) * 100
    ]);

    // Internal state for inputs to allow temporary invalid values while typing
    const [inputs, setInputs] = useState({
        train: (ratios.train * 100).toFixed(0),
        val: (ratios.val * 100).toFixed(0),
        test: (ratios.test * 100).toFixed(0),
    });

    // Sync from props
    useEffect(() => {
        const h1 = ratios.train * 100;
        const h2 = (ratios.train + ratios.val) * 100;

        // Only update if significantly different to avoid fighting with user input
        if (Math.abs(handles[1] - h1) > 0.1 || Math.abs(handles[2] - h2) > 0.1) {
            setHandles([0, h1, h2]);
            setInputs({
                train: (ratios.train * 100).toFixed(0),
                val: (ratios.val * 100).toFixed(0),
                test: (ratios.test * 100).toFixed(0),
            });
        }
    }, [ratios]);

    const handleSliderChange = (value: number | number[]) => {
        if (Array.isArray(value)) {
            // Ensure first handle stays at 0
            if (value[0] !== 0) return;

            const [_, h1, h2] = value;

            const train = h1 / 100;
            const val = (h2 - h1) / 100;
            const test = (100 - h2) / 100;

            setHandles([0, h1, h2]);
            setInputs({
                train: h1.toFixed(0),
                val: (h2 - h1).toFixed(0),
                test: (100 - h2).toFixed(0),
            });

            onChange({ train, val, test });
        }
    };

    // ... handleInputChange and handleInputBlur remain largely the same logic-wise
    // but we'll keep them as they were in the full file context, 
    // assuming they are unchanged for this block.

    const handleInputChange = (key: 'train' | 'val' | 'test', value: string) => {
        const newInputs = { ...inputs, [key]: value };
        setInputs(newInputs);

        // We don't update slider/prop immediately on typing to prevent jank
        // Logic handled in Blur
    };

    const handleInputBlur = (key: 'train' | 'val' | 'test') => {
        let v = parseInt(inputs[key]);
        if (isNaN(v)) v = 0;
        v = Math.max(0, Math.min(100, v));

        let currentTrain = parseFloat(inputs.train);
        let currentVal = parseFloat(inputs.val);
        let currentTest = parseFloat(inputs.test);

        if (isNaN(currentTrain)) currentTrain = 0;
        if (isNaN(currentVal)) currentVal = 0;
        if (isNaN(currentTest)) currentTest = 0;

        if (key === 'train') {
            const remaining = 100 - v;
            if (currentVal + currentTest === 0) {
                currentVal = remaining / 2;
                currentTest = remaining / 2;
            } else {
                const newVal = (currentVal / (currentVal + currentTest)) * remaining;
                const newTest = remaining - newVal;
                currentVal = newVal;
                currentTest = newTest;
            }
            currentTrain = v;
        } else if (key === 'val') {
            const remaining = 100 - v;
            if (currentTrain + currentTest === 0) {
                currentTrain = remaining / 2;
                currentTest = remaining / 2;
            } else {
                const newTrain = (currentTrain / (currentTrain + currentTest)) * remaining;
                const newTest = remaining - newTrain;
                currentTrain = newTrain;
                currentTest = newTest;
            }
            currentVal = v;
        } else { // test
            const remaining = 100 - v;
            if (currentTrain + currentVal === 0) {
                currentTrain = remaining / 2;
                currentVal = remaining / 2;
            } else {
                const newTrain = (currentTrain / (currentTrain + currentVal)) * remaining;
                const newVal = remaining - newTrain;
                currentTrain = newTrain;
                currentVal = newVal;
            }
            currentTest = v;
        }

        onChange({
            train: currentTrain / 100,
            val: currentVal / 100,
            test: currentTest / 100
        });
    };

    return (
        <div className="space-y-6">
            <div className="px-2 pt-2">
                <Slider
                    range
                    min={0}
                    max={100}
                    step={1}
                    value={handles}
                    onChange={handleSliderChange}
                    allowCross={false}
                    pushable={5} // Min 5% per section
                    trackStyle={[
                        { backgroundColor: "#3b82f6" }, // Track 0 (0 -> h1): Train (Blue)
                        { backgroundColor: "#f97316" }, // Track 1 (h1 -> h2): Val (Orange)
                    ]}
                    handleStyle={[
                        { display: "none" }, // Handle 0: Hidden
                        { borderColor: "#3b82f6", backgroundColor: "#fff", opacity: 1 }, // Handle 1 (Train/Val)
                        { borderColor: "#f97316", backgroundColor: "#fff", opacity: 1 }, // Handle 2 (Val/Test)
                    ]}
                    railStyle={{ backgroundColor: "#22c55e" }} // Rail (h2 -> 100): Test (Green)
                />
            </div>

            <div className="grid grid-cols-3 gap-4">
                <div className="space-y-1.5">
                    <Label className="text-xs text-blue-600 font-semibold flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-blue-500" />
                        Train
                    </Label>
                    <div className="relative">
                        <Input
                            type="number"
                            value={inputs.train}
                            onChange={(e) => handleInputChange('train', e.target.value)}
                            onBlur={() => handleInputBlur('train')}
                            className="pr-6 text-right"
                        />
                        <span className="absolute right-2 top-2.5 text-xs text-muted-foreground">%</span>
                    </div>
                </div>

                <div className="space-y-1.5">
                    <Label className="text-xs text-orange-600 font-semibold flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-orange-500" />
                        Validation
                    </Label>
                    <div className="relative">
                        <Input
                            type="number"
                            value={inputs.val}
                            onChange={(e) => handleInputChange('val', e.target.value)}
                            onBlur={() => handleInputBlur('val')}
                            className="pr-6 text-right"
                        />
                        <span className="absolute right-2 top-2.5 text-xs text-muted-foreground">%</span>
                    </div>
                </div>

                <div className="space-y-1.5">
                    <Label className="text-xs text-green-600 font-semibold flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-green-500" />
                        Test
                    </Label>
                    <div className="relative">
                        <Input
                            type="number"
                            value={inputs.test}
                            onChange={(e) => handleInputChange('test', e.target.value)}
                            onBlur={() => handleInputBlur('test')}
                            className="pr-6 text-right"
                        />
                        <span className="absolute right-2 top-2.5 text-xs text-muted-foreground">%</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
