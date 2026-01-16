"use client";

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
import {
    ExportConfig,
    MISSING_VALUES_OPTIONS,
    NORMALIZATION_OPTIONS,
} from "./types";

interface PreprocessingSectionProps {
    config: ExportConfig;
    updateConfig: (updates: Partial<ExportConfig>) => void;
}

export function PreprocessingSection({ config, updateConfig }: PreprocessingSectionProps) {
    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-lg">1. Preprocessing</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-4">
                    <div className="space-y-2">
                        <Label>Missing Values Strategy</Label>
                        <Select
                            value={config.missing_values_strategy}
                            onValueChange={(v: ExportConfig["missing_values_strategy"]) =>
                                updateConfig({ missing_values_strategy: v })
                            }
                        >
                            <SelectTrigger>
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {MISSING_VALUES_OPTIONS.map(opt => (
                                    <SelectItem key={opt.value} value={opt.value}>
                                        {opt.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    <div className="space-y-2">
                        <Label>Normalization</Label>
                        <Select
                            value={config.normalization}
                            onValueChange={(v: ExportConfig["normalization"]) =>
                                updateConfig({ normalization: v })
                            }
                        >
                            <SelectTrigger>
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {NORMALIZATION_OPTIONS.map(opt => (
                                    <SelectItem key={opt.value} value={opt.value}>
                                        {opt.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
