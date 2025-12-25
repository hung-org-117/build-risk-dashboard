"use client";

import { useState, useCallback, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Loader2, Sparkles, ArrowRight } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface NormalizationPreviewSectionProps {
    datasetId: string;
    versionId: string;
}

interface NormalizationMethod {
    value: string;
    label: string;
    description: string;
}

export function NormalizationPreviewSection({ datasetId, versionId }: NormalizationPreviewSectionProps) {
    const [method, setMethod] = useState("minmax");
    const [methods, setMethods] = useState<NormalizationMethod[]>([]);
    const [previewData, setPreviewData] = useState<Record<string, number | string | null>[]>([]);
    const [features, setFeatures] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);
    const [expanded, setExpanded] = useState(false);

    const fetchPreview = useCallback(async (selectedMethod: string) => {
        if (!versionId) return;
        setLoading(true);
        try {
            const res = await fetch(
                `${API_BASE}/datasets/${datasetId}/versions/${versionId}/preprocess/preview?method=${selectedMethod}&limit=5`,
                { credentials: "include" }
            );
            if (res.ok) {
                const data = await res.json();
                setPreviewData(data.sample_data || []);
                setMethods(data.methods || []);
                setFeatures(data.selected_features?.slice(0, 3) || []);
            }
        } catch (err) {
            console.error("Failed to fetch normalization preview:", err);
        } finally {
            setLoading(false);
        }
    }, [datasetId, versionId]);

    useEffect(() => {
        if (expanded) {
            fetchPreview(method);
        }
    }, [expanded, method, fetchPreview]);

    const formatValue = (value: number | string | null): string => {
        if (value === null || value === undefined) return "-";
        if (typeof value === "number") {
            if (Number.isInteger(value)) return value.toString();
            return value.toFixed(3);
        }
        return String(value);
    };

    return (
        <div className="p-4 bg-blue-50/50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
            <div
                className="flex items-center justify-between cursor-pointer"
                onClick={() => setExpanded(!expanded)}
            >
                <div className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-blue-600" />
                    <span className="font-medium">Normalization Preview</span>
                </div>
                <Button variant="ghost" size="sm">
                    {expanded ? "Collapse" : "Expand"}
                </Button>
            </div>

            {expanded && (
                <div className="mt-4 space-y-3">
                    <div className="flex items-center gap-4">
                        <span className="text-sm text-muted-foreground">Method:</span>
                        <Select value={method} onValueChange={setMethod}>
                            <SelectTrigger className="w-48">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {methods.map((m) => (
                                    <SelectItem key={m.value} value={m.value}>
                                        {m.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {loading ? (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Loading preview...
                        </div>
                    ) : previewData.length > 0 ? (
                        <div className="overflow-x-auto">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="w-12">#</TableHead>
                                        {features.map((feat) => (
                                            <TableHead key={feat} className="min-w-[140px]">
                                                <div className="flex items-center gap-1 text-xs">
                                                    <span>{feat}</span>
                                                    <ArrowRight className="h-3 w-3" />
                                                </div>
                                            </TableHead>
                                        ))}
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {previewData.slice(0, 3).map((row, idx) => (
                                        <TableRow key={idx}>
                                            <TableCell className="text-muted-foreground">{idx + 1}</TableCell>
                                            {features.map((feat) => (
                                                <TableCell key={feat} className="font-mono text-xs">
                                                    <span className="text-muted-foreground">
                                                        {formatValue(row[`${feat}_raw`])}
                                                    </span>
                                                    <ArrowRight className="inline h-3 w-3 mx-1 text-muted-foreground/50" />
                                                    <span className="text-blue-600 font-medium">
                                                        {formatValue(row[`${feat}_normalized`])}
                                                    </span>
                                                </TableCell>
                                            ))}
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    ) : (
                        <p className="text-sm text-muted-foreground">No data available</p>
                    )}
                </div>
            )}
        </div>
    );
}
