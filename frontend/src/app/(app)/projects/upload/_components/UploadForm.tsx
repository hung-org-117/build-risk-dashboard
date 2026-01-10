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
import type { MappingKey, CIProviderMode } from "./types";
import type { CIProviderOption } from "@/types";

interface UploadFormProps {
    previewExists: boolean;
    columns: string[];
    uploading: boolean;
    name: string;
    description: string;
    ciProvider: string;
    ciProviderMode: CIProviderMode;
    ciProviderColumn: string;
    ciProviders: CIProviderOption[];
    mappings: Record<MappingKey, string>;
    isMappingValid: boolean;
    fileInputRef: React.RefObject<HTMLInputElement | null>;
    onFileSelect: (event: React.ChangeEvent<HTMLInputElement>) => void;
    onNameChange: (value: string) => void;
    onDescriptionChange: (value: string) => void;
    onCiProviderChange: (value: string) => void;
    onCiProviderModeChange: (mode: CIProviderMode) => void;
    onCiProviderColumnChange: (column: string) => void;
    onMappingChange: (field: MappingKey, value: string) => void;
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
    mappings,
    isMappingValid,
    fileInputRef,
    onFileSelect,
    onNameChange,
    onDescriptionChange,
    onCiProviderChange,
    onCiProviderModeChange,
    onCiProviderColumnChange,
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
        </div>
    );
}
