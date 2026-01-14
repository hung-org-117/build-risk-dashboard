"use client";

import { Checkbox } from "@/components/ui/checkbox";
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
                <div className="grid gap-6 md:grid-cols-2">
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
                    <div className="flex items-center gap-3 pt-6">
                        <Checkbox
                            id="include-metadata"
                            checked={config.include_metadata}
                            onCheckedChange={(v) => updateConfig({ include_metadata: !!v })}
                        />
                        <Label htmlFor="include-metadata" className="cursor-pointer">
                            Include Metadata (repo, commit, build_id)
                        </Label>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
