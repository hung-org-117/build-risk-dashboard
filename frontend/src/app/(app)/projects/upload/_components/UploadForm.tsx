"use client";

import {
    AlertCircle,
    CheckCircle2,
    Loader2,
    Upload,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

import { ColumnSelector } from "./ColumnSelector";
import type { StepUploadProps, MappingKey } from "./types";

interface UploadFormProps extends Omit<StepUploadProps, "preview" | "isDatasetCreated" | "onClearFile"> {
    previewExists: boolean;
    columns: string[];
}

export function UploadForm({
    previewExists,
    uploading,
    name,
    description,
    ciProvider,
    ciProviderMode,
    ciProviderColumn,
    ciProviders,
    buildFilters,
    mappings,
    isMappingValid,
    fileInputRef,
    onFileSelect,
    onNameChange,
    onDescriptionChange,
    onCiProviderChange,
    onCiProviderModeChange,
    onCiProviderColumnChange,
    onBuildFiltersChange,
    onMappingChange,
    columns,
}: UploadFormProps) {

    if (!previewExists) {
        return (
            <div className="flex flex-col items-center justify-center px-8 py-12 border-2 border-dashed border-slate-300 rounded-xl bg-slate-50/50 dark:border-slate-700 dark:bg-slate-900/50 transition-colors hover:border-blue-500 hover:bg-slate-50">
                <input
                    ref={fileInputRef as React.RefObject<HTMLInputElement>}
                    type="file"
                    accept=".csv"
                    className="hidden"
                    onChange={onFileSelect}
                />
                <div
                    className="flex flex-col items-center justify-center gap-4 text-center cursor-pointer w-full"
                    onClick={() => fileInputRef.current?.click()}
                >
                    {uploading ? (
                        <>
                            <Loader2 className="h-12 w-12 animate-spin text-blue-500" />
                            <p className="text-muted-foreground font-medium">Parsing CSV...</p>
                        </>
                    ) : (
                        <>
                            <div className="rounded-full bg-blue-100 p-4 dark:bg-blue-900/30 text-blue-600">
                                <Upload className="h-8 w-8" />
                            </div>
                            <div>
                                <h3 className="text-lg font-semibold">Upload Dataset CSV</h3>
                                <p className="text-sm text-muted-foreground mt-1 max-w-[240px] mx-auto">
                                    Drag & drop or click to browse.
                                </p>
                            </div>
                            <Badge variant="outline" className="mt-2 text-[10px] px-2 py-0.5 h-auto">
                                Supports .csv
                            </Badge>
                        </>
                    )}
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-8 pr-4">
            {/* Dataset Info */}
            <div className="space-y-4">
                <h3 className="text-sm font-semibold uppercase text-muted-foreground tracking-wider flex items-center gap-2">
                    <span className="flex items-center justify-center w-5 h-5 rounded-full bg-slate-200 text-slate-700 text-[10px] dark:bg-slate-800 dark:text-slate-300">1</span>
                    Basic Info
                </h3>
                <div className="grid gap-4">
                    <div className="space-y-2">
                        <Label>Dataset Name</Label>
                        <Input value={name} onChange={(e) => onNameChange(e.target.value)} placeholder="My Dataset" />
                    </div>
                    <div className="space-y-2">
                        <Label>Description <span className="text-muted-foreground font-normal">(optional)</span></Label>
                        <Input value={description} onChange={(e) => onDescriptionChange(e.target.value)} placeholder="Description..." />
                    </div>
                </div>
            </div>

            <div className="h-px bg-border" />

            {/* Column Mapping */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold uppercase text-muted-foreground tracking-wider flex items-center gap-2">
                        <span className="flex items-center justify-center w-5 h-5 rounded-full bg-slate-200 text-slate-700 text-[10px] dark:bg-slate-800 dark:text-slate-300">2</span>
                        Column Mapping
                    </h3>
                    {isMappingValid ? (
                        <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-emerald-600 bg-emerald-50 px-2 py-1 rounded-full dark:bg-emerald-900/20">
                            <CheckCircle2 className="h-3 w-3" /> Valid
                        </span>
                    ) : (
                        <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-amber-600 bg-amber-50 px-2 py-1 rounded-full dark:bg-amber-900/20">
                            Required
                        </span>
                    )}
                </div>
                <div className="grid gap-4">
                    <div className="space-y-1.5">
                        <Label className="text-xs uppercase text-muted-foreground">
                            Build ID <span className="text-red-500">*</span>
                        </Label>
                        <ColumnSelector
                            value={mappings.build_id}
                            columns={columns}
                            onChange={(v) => onMappingChange("build_id" as MappingKey, v)}
                        />
                    </div>
                    <div className="space-y-1.5">
                        <Label className="text-xs uppercase text-muted-foreground">
                            Repo Name <span className="text-red-500">*</span>
                        </Label>
                        <ColumnSelector
                            value={mappings.repo_name}
                            columns={columns}
                            onChange={(v) => onMappingChange("repo_name" as MappingKey, v)}
                        />
                    </div>
                </div>
            </div>

            <div className="h-px bg-border" />

            {/* CI Provider */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold uppercase text-muted-foreground tracking-wider flex items-center gap-2">
                        <span className="flex items-center justify-center w-5 h-5 rounded-full bg-slate-200 text-slate-700 text-[10px] dark:bg-slate-800 dark:text-slate-300">3</span>
                        CI Provider
                    </h3>
                    <div className="flex gap-1 p-0.5 bg-muted rounded-md">
                        <button
                            type="button"
                            onClick={() => onCiProviderModeChange("single")}
                            className={`px-2 py-1 text-[10px] font-medium rounded-sm transition-all ${ciProviderMode === "single"
                                ? "bg-background shadow-sm text-foreground"
                                : "text-muted-foreground hover:text-foreground"
                                }`}
                        >
                            Single
                        </button>
                        <button
                            type="button"
                            onClick={() => onCiProviderModeChange("column")}
                            className={`px-2 py-1 text-[10px] font-medium rounded-sm transition-all ${ciProviderMode === "column"
                                ? "bg-background shadow-sm text-foreground"
                                : "text-muted-foreground hover:text-foreground"
                                }`}
                        >
                            Mapped
                        </button>
                    </div>
                </div>

                {ciProviderMode === "single" ? (
                    <div className="space-y-2">
                        <Select value={ciProvider} onValueChange={onCiProviderChange}>
                            <SelectTrigger>
                                <SelectValue placeholder="Select CI Provider" />
                            </SelectTrigger>
                            <SelectContent>
                                {ciProviders.map((provider) => (
                                    <SelectItem key={provider.value} value={provider.value}>
                                        {provider.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                ) : (
                    <div className="space-y-2">
                        <ColumnSelector
                            value={ciProviderColumn}
                            columns={columns}
                            onChange={onCiProviderColumnChange}
                            placeholder="Select column..."
                        />
                    </div>
                )}
            </div>

            <div className="h-px bg-border" />

            {/* Filters */}
            <div className="space-y-4">
                <h3 className="text-sm font-semibold uppercase text-muted-foreground tracking-wider flex items-center gap-2">
                    <span className="flex items-center justify-center w-5 h-5 rounded-full bg-slate-200 text-slate-700 text-[10px] dark:bg-slate-800 dark:text-slate-300">4</span>
                    Filters
                </h3>

                <div className="space-y-4 p-4 rounded-lg bg-muted/40 border">
                    <div className="flex flex-col gap-3">
                        <label className="flex items-center gap-3 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={buildFilters.only_completed}
                                onChange={(e) =>
                                    onBuildFiltersChange({
                                        ...buildFilters,
                                        only_completed: e.target.checked,
                                    })
                                }
                                className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                            />
                            <span className="text-sm font-medium">Only completed builds</span>
                        </label>
                        <label className="flex items-center gap-3 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={buildFilters.exclude_bots}
                                onChange={(e) =>
                                    onBuildFiltersChange({
                                        ...buildFilters,
                                        exclude_bots: e.target.checked,
                                    })
                                }
                                className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                            />
                            <span className="text-sm font-medium">Exclude bot commits</span>
                        </label>
                    </div>

                    <div className="space-y-3 pt-2 border-t">
                        <Label className="text-xs uppercase text-muted-foreground">Conclusions</Label>
                        <div className="flex flex-wrap gap-2">
                            {[
                                { value: "success", label: "Success", color: "bg-emerald-100 text-emerald-700 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-400 dark:border-emerald-800" },
                                { value: "failure", label: "Failure", color: "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800" },
                                { value: "cancelled", label: "Cancelled", color: "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700" },
                                { value: "skipped", label: "Skipped", color: "bg-gray-100 text-gray-700 border-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-700" },
                                { value: "timed_out", label: "Timed Out", color: "bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-900/30 dark:text-orange-400 dark:border-orange-800" },
                                { value: "neutral", label: "Neutral", color: "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-800" },
                                { value: "action_required", label: "Action Required", color: "bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900/30 dark:text-yellow-400 dark:border-yellow-800" },
                            ].map((option) => {
                                const isSelected = buildFilters.allowed_conclusions.includes(option.value);
                                return (
                                    <button
                                        key={option.value}
                                        type="button"
                                        onClick={() => {
                                            const newConclusions = isSelected
                                                ? buildFilters.allowed_conclusions.filter((c) => c !== option.value)
                                                : [...buildFilters.allowed_conclusions, option.value];
                                            onBuildFiltersChange({
                                                ...buildFilters,
                                                allowed_conclusions: newConclusions,
                                            });
                                        }}
                                        className={`px-2.5 py-1 text-xs font-medium rounded-full border transition-all ${isSelected
                                            ? option.color
                                            : "bg-background text-muted-foreground border-transparent hover:bg-muted"
                                            }`}
                                    >
                                        {option.label}
                                    </button>
                                );
                            })}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
