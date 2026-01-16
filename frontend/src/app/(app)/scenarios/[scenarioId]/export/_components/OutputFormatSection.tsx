"use client";


import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { ExportConfig } from "./types";

interface OutputFormatSectionProps {
    config: ExportConfig;
    updateConfig: (updates: Partial<ExportConfig>) => void;
}

export function OutputFormatSection({ config, updateConfig }: OutputFormatSectionProps) {
    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-lg">3. Output Format</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-4">
                    <div className="space-y-2">
                        <Label>File Format</Label>
                        <Select
                            value={config.format}
                            onValueChange={(v: "parquet" | "csv") => updateConfig({ format: v })}
                        >
                            <SelectTrigger>
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="parquet">Parquet (recommended)</SelectItem>
                                <SelectItem value="csv">CSV</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
