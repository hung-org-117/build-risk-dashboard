import { useState } from "react";
import { format } from "date-fns";
import {
    ChevronDown,
    ChevronUp,
    Download,
    Trash2,
    RefreshCw,
    FileText,
    CheckCircle2,
    AlertCircle,
    Clock,
    XCircle,
    Database,
    Settings,
    BarChart3,
    Code
} from "lucide-react";

import { getStrategyOption, MISSING_VALUES_OPTIONS, GROUP_BY_OPTIONS } from "./types";

import { Button } from "@/components/ui/button";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { TrainingExportRecord } from "@/lib/api/training-scenarios";
import { cn, formatDateTime, formatDurationFromSeconds } from "@/lib/utils";

interface ExportsListSectionProps {
    scenarioId: string;
    exports: TrainingExportRecord[];
    onCreateNew: () => void;
    onViewExport?: (exportId: string) => void;
    onDeleteExport: (exportId: string) => void;
    onRefresh?: () => void;
    scansRunning: boolean;
    scansProgress: number;
}

export function ExportsListSection({
    scenarioId,
    exports,
    onCreateNew,
    onViewExport,
    onDeleteExport,
    onRefresh,
    scansRunning,
    scansProgress,
}: ExportsListSectionProps) {
    const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
    const [page, setPage] = useState(1);
    const pageSize = 10;
    const [refreshing, setRefreshing] = useState(false);

    const toggleRow = (id: string) => {
        const newExpanded = new Set(expandedRows);
        if (newExpanded.has(id)) {
            newExpanded.delete(id);
        } else {
            newExpanded.add(id);
        }
        setExpandedRows(newExpanded);
    };

    const handleRefresh = async () => {
        if (onRefresh) {
            setRefreshing(true);
            await onRefresh();
            setRefreshing(false);
        }
    };

    // Pagination Logic
    const total = exports.length;
    const totalPages = Math.ceil(total / pageSize);
    const startIndex = (page - 1) * pageSize;
    const endIndex = Math.min(startIndex + pageSize, total);
    const currentExports = exports.slice(startIndex, endIndex);

    const handlePrevious = () => {
        if (page > 1) setPage(page - 1);
    };

    const handleNext = () => {
        if (page < totalPages) setPage(page + 1);
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case "completed": return "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400";
            case "failed": return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400";
            case "processing": return "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400";
            case "pending": return "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400";
            default: return "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400";
        }
    };

    const getNormalizationLabel = (val: string) => {
        switch (val) {
            case "z_score": return "Z-Score";
            case "min_max": return "Min-Max";
            case "robust": return "Robust";
            case "none": return "None";
            default: return val || "—";
        }
    };

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between">
                <div>
                    <CardTitle>Export History</CardTitle>
                </div>
                <div className="flex items-center gap-2">
                    {onRefresh && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleRefresh}
                            disabled={refreshing}
                        >
                            <RefreshCw className={cn("h-4 w-4 mr-2", refreshing && "animate-spin")} />
                            Refresh
                        </Button>
                    )}
                    <Button
                        onClick={onCreateNew}
                        disabled={scansRunning}
                        className="bg-green-600 hover:bg-green-700 text-white"
                    >
                        {scansRunning ? (
                            <>
                                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                                Scans Running ({scansProgress}%)
                            </>
                        ) : (
                            <>
                                <FileText className="mr-2 h-4 w-4" />
                                Create New Export
                            </>
                        )}
                    </Button>
                </div>
            </CardHeader>
            <CardContent>
                <div className="rounded-md border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="w-[50px]"></TableHead>
                                <TableHead>Name</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Strategy</TableHead>
                                <TableHead>Records</TableHead>
                                <TableHead>Created</TableHead>
                                <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {currentExports.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                                        No exports found. Create one to get started.
                                    </TableCell>
                                </TableRow>
                            ) : (
                                currentExports.map((exp) => {
                                    const isExpanded = expandedRows.has(exp.id);
                                    const totalRecords = (exp.train_count || 0) + (exp.val_count || 0) + (exp.test_count || 0);
                                    // Use optional chaining carefully, splitting_config is required by type but might be missing in partial data
                                    const strategy = exp.splitting_config?.strategy || "—";

                                    return (
                                        <>
                                            <TableRow
                                                key={exp.id}
                                                className={cn("cursor-pointer hover:bg-muted/50 transition-colors", isExpanded && "bg-muted/50 border-b-0")}
                                                onClick={() => toggleRow(exp.id)}
                                            >
                                                <TableCell>
                                                    <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={(e) => { e.stopPropagation(); toggleRow(exp.id); }}>
                                                        {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                                                    </Button>
                                                </TableCell>
                                                <TableCell className="font-medium">
                                                    {exp.name || <span className="text-muted-foreground italic">Untitled Export</span>}
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant="outline" className={getStatusColor(exp.status)}>
                                                        {exp.status}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant="secondary" className="font-mono text-xs">
                                                        {getStrategyOption(strategy)?.label || strategy}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>
                                                    {totalRecords > 0 ? totalRecords.toLocaleString() : "—"}
                                                </TableCell>
                                                <TableCell className="text-muted-foreground text-sm">
                                                    {formatDateTime(exp.created_at)}
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    <div className="flex justify-end gap-2" onClick={(e) => e.stopPropagation()}>
                                                        {exp.status === "completed" && (
                                                            <Button variant="outline" size="sm" asChild>
                                                                <a
                                                                    href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'}/training-scenarios/${scenarioId}/exports/${exp.id}/download`}
                                                                    download
                                                                >
                                                                    <Download className="mr-2 h-4 w-4" />
                                                                    Download
                                                                </a>
                                                            </Button>
                                                        )}
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            className="text-red-500 hover:text-red-600 hover:bg-red-50"
                                                            onClick={() => onDeleteExport(exp.id)}
                                                        >
                                                            <Trash2 className="h-4 w-4" />
                                                        </Button>
                                                    </div>
                                                </TableCell>
                                            </TableRow>

                                            {/* Detailed Expanded View */}
                                            {isExpanded && (
                                                <TableRow className="bg-muted/30 hover:bg-muted/30">
                                                    <TableCell colSpan={7} className="p-0">
                                                        <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-6 text-sm">
                                                            {/* Configuration */}
                                                            <div className="space-y-3">
                                                                <h4 className="font-medium flex items-center gap-2 text-primary">
                                                                    Configuration
                                                                </h4>
                                                                <div className="grid grid-cols-2 gap-2 text-muted-foreground">
                                                                    <span>Missing Values:</span>
                                                                    <span className="font-medium text-foreground">
                                                                        {MISSING_VALUES_OPTIONS.find(o => o.value === exp.preprocessing_config?.missing_values_strategy)?.label || exp.preprocessing_config?.missing_values_strategy || "—"}
                                                                    </span>

                                                                    <span>Normalization:</span>
                                                                    <span className="font-medium text-foreground">{getNormalizationLabel(exp.preprocessing_config?.normalization)}</span>

                                                                    <span>Format:</span>
                                                                    <span className="font-medium text-foreground uppercase">{exp.output_config?.format || "PARQUET"}</span>

                                                                    {exp.splitting_config?.group_by && (
                                                                        <>
                                                                            <span>Group By:</span>
                                                                            <span className="font-medium text-foreground">
                                                                                {GROUP_BY_OPTIONS.find(o => o.value === exp.splitting_config.group_by)?.label || exp.splitting_config.group_by}
                                                                            </span>
                                                                        </>
                                                                    )}
                                                                </div>
                                                            </div>

                                                            {/* Data Splits */}
                                                            <div className="space-y-3">
                                                                <h4 className="font-medium flex items-center gap-2 text-primary">
                                                                    Data Splits
                                                                </h4>
                                                                <div className="space-y-2">
                                                                    <div className="flex justify-between items-center text-xs">
                                                                        <span className="text-muted-foreground">Train</span>
                                                                        <span className="font-mono">{exp.train_count?.toLocaleString() || 0}</span>
                                                                    </div>
                                                                    <div className="flex justify-between items-center text-xs">
                                                                        <span className="text-muted-foreground">Validation</span>
                                                                        <span className="font-mono">{exp.val_count?.toLocaleString() || 0}</span>
                                                                    </div>
                                                                    <div className="flex justify-between items-center text-xs">
                                                                        <span className="text-muted-foreground">Test</span>
                                                                        <span className="font-mono">{exp.test_count?.toLocaleString() || 0}</span>
                                                                    </div>
                                                                </div>
                                                            </div>

                                                            {/* Features & Performance */}
                                                            <div className="space-y-3">
                                                                <h4 className="font-medium flex items-center gap-2 text-primary">
                                                                    Features & Metrics
                                                                </h4>
                                                                <div className="grid grid-cols-2 gap-2">
                                                                    <div className="bg-background border rounded p-2 text-center">
                                                                        <div className="text-xs text-muted-foreground mb-1">Total Features</div>
                                                                        <div className="font-bold text-lg">{exp.feature_count}</div>
                                                                    </div>
                                                                    <div className="bg-background border rounded p-2 text-center">
                                                                        <div className="text-xs text-muted-foreground mb-1">Duration</div>
                                                                        <div className="font-bold text-lg">{formatDurationFromSeconds(exp.generation_duration_seconds)}</div>
                                                                    </div>
                                                                </div>
                                                                <div className="text-xs text-muted-foreground pt-2 flex items-center gap-1">
                                                                    <Clock className="h-3 w-3" />
                                                                    Generated at: {formatDateTime(exp.generated_at)}
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </TableCell>
                                                </TableRow>
                                            )}
                                        </>
                                    );
                                })
                            )}
                        </TableBody>
                    </Table>
                </div>

                {/* Pagination Controls */}
                {total > 0 && (
                    <div className="flex items-center justify-between py-4">
                        <div className="text-sm text-muted-foreground">
                            Showing {Math.min(startIndex + 1, total)}-{endIndex} of {total} exports
                        </div>
                        <div className="flex items-center space-x-2">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handlePrevious}
                                disabled={page === 1}
                            >
                                Previous
                            </Button>
                            <div className="text-sm font-medium">
                                Page {page} of {totalPages}
                            </div>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handleNext}
                                disabled={page >= totalPages}
                            >
                                Next
                            </Button>
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
