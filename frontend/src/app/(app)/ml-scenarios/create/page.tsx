"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
    ArrowLeft,
    FileCode,
    Loader2,
    Upload,
    CheckCircle,
    XCircle,
    BookOpen,
    ChevronDown,
    AlertCircle,
} from "lucide-react";

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
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/use-toast";
import { mlScenariosApi } from "@/lib/api";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface SampleTemplate {
    filename: string;
    name: string;
    description: string;
    strategy: string;
    group_by: string;
}

interface ValidationError {
    field: string;
    message: string;
    expected?: string;
    got?: string;
}

export default function CreateScenarioPage() {
    const router = useRouter();
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [yamlConfig, setYamlConfig] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);

    // Validation state
    const [isValidating, setIsValidating] = useState(false);
    const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
    const [isValid, setIsValid] = useState<boolean | null>(null);

    // Sample templates
    const [templates, setTemplates] = useState<SampleTemplate[]>([]);
    const [isLoadingTemplates, setIsLoadingTemplates] = useState(false);

    // Load sample templates on mount
    useEffect(() => {
        const loadTemplates = async () => {
            setIsLoadingTemplates(true);
            try {
                const data = await mlScenariosApi.getSampleTemplates();
                setTemplates(data.templates);
            } catch (err) {
                console.error("Failed to load templates:", err);
            } finally {
                setIsLoadingTemplates(false);
            }
        };
        loadTemplates();
    }, []);

    // Debounced validation
    const validateYaml = useCallback(async (yaml: string) => {
        if (!yaml.trim()) {
            setIsValid(null);
            setValidationErrors([]);
            return;
        }

        setIsValidating(true);
        try {
            const result = await mlScenariosApi.validateYaml(yaml);
            setIsValid(result.valid);
            setValidationErrors(result.errors);
        } catch {
            setIsValid(null);
            setValidationErrors([]);
        } finally {
            setIsValidating(false);
        }
    }, []);

    // Validate on YAML change (debounced)
    useEffect(() => {
        const timer = setTimeout(() => {
            if (yamlConfig.trim()) {
                validateYaml(yamlConfig);
            }
        }, 500);
        return () => clearTimeout(timer);
    }, [yamlConfig, validateYaml]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!name.trim()) {
            toast({
                title: "Validation Error",
                description: "Scenario name is required",
                variant: "destructive",
            });
            return;
        }

        if (!yamlConfig.trim()) {
            toast({
                title: "Validation Error",
                description: "YAML configuration is required",
                variant: "destructive",
            });
            return;
        }

        // Check validation before submit
        if (isValid === false) {
            toast({
                title: "Validation Error",
                description: "Please fix the YAML errors before submitting",
                variant: "destructive",
            });
            return;
        }

        setIsSubmitting(true);
        try {
            const scenario = await mlScenariosApi.create({
                name: name.trim(),
                yaml_config: yamlConfig,
                description: description.trim() || undefined,
            });

            toast({
                title: "Success",
                description: `Scenario "${scenario.name}" created successfully`,
            });

            router.push(`/ml-scenarios/${scenario.id}`);
        } catch (err: unknown) {
            console.error(err);
            const errorMessage = err instanceof Error ? err.message : "Failed to create scenario";
            toast({
                title: "Error",
                description: errorMessage,
                variant: "destructive",
            });
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        const text = await file.text();
        setYamlConfig(text);

        // Extract name from filename if not set
        if (!name) {
            const baseName = file.name.replace(/\.(yaml|yml)$/i, "");
            setName(baseName);
        }

        toast({
            title: "File Loaded",
            description: `Loaded ${file.name}`,
        });
    };

    const handleTemplateSelect = async (filename: string) => {
        try {
            const data = await mlScenariosApi.getSampleTemplate(filename);
            setYamlConfig(data.content);
            toast({
                title: "Template Loaded",
                description: `Loaded template: ${filename}`,
            });
        } catch (err) {
            console.error(err);
            toast({
                title: "Error",
                description: "Failed to load template",
                variant: "destructive",
            });
        }
    };

    return (
        <div className="space-y-6">
            {/* Back Button */}
            <div className="flex items-center justify-between">
                <Button
                    variant="ghost"
                    onClick={() => router.push("/ml-scenarios")}
                    className="gap-2"
                >
                    <ArrowLeft className="h-4 w-4" />
                    Back to Scenarios
                </Button>

                {/* Docs Link */}
                <Button
                    variant="outline"
                    onClick={() => window.open("/docs/yaml-guide", "_blank")}
                    className="gap-2"
                >
                    <BookOpen className="h-4 w-4" />
                    YAML Guide
                </Button>
            </div>

            {/* Header */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <FileCode className="h-5 w-5" />
                        Create ML Scenario
                    </CardTitle>
                    <CardDescription>
                        Define a scenario using YAML configuration to create train/validation/test splits.
                    </CardDescription>
                </CardHeader>
            </Card>

            {/* Form */}
            <form onSubmit={handleSubmit}>
                <Card>
                    <CardContent className="pt-6 space-y-6">
                        {/* Name */}
                        <div className="space-y-2">
                            <Label htmlFor="name">Scenario Name *</Label>
                            <Input
                                id="name"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                placeholder="e.g., temporal_split_2024"
                                disabled={isSubmitting}
                            />
                        </div>

                        {/* Description */}
                        <div className="space-y-2">
                            <Label htmlFor="description">Description</Label>
                            <Input
                                id="description"
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                placeholder="Optional description"
                                disabled={isSubmitting}
                            />
                        </div>

                        {/* File Upload & Template Selector */}
                        <div className="space-y-2">
                            <Label>Load Configuration</Label>
                            <div className="flex items-center gap-2 flex-wrap">
                                <Input
                                    type="file"
                                    accept=".yaml,.yml"
                                    onChange={handleFileUpload}
                                    disabled={isSubmitting}
                                    className="max-w-xs"
                                />

                                <DropdownMenu>
                                    <DropdownMenuTrigger asChild>
                                        <Button
                                            variant="outline"
                                            disabled={isLoadingTemplates || isSubmitting}
                                            className="gap-2"
                                        >
                                            <FileCode className="h-4 w-4" />
                                            Sample Templates
                                            <ChevronDown className="h-4 w-4" />
                                        </Button>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="start" className="w-80">
                                        {templates.length === 0 ? (
                                            <div className="px-2 py-1.5 text-sm text-muted-foreground">
                                                No templates available
                                            </div>
                                        ) : (
                                            templates.map((template) => (
                                                <DropdownMenuItem
                                                    key={template.filename}
                                                    onClick={() => handleTemplateSelect(template.filename)}
                                                    className="flex flex-col items-start py-2"
                                                >
                                                    <div className="flex items-center gap-2">
                                                        <span className="font-medium">{template.name}</span>
                                                        <Badge variant="secondary" className="text-xs">
                                                            {template.strategy}
                                                        </Badge>
                                                    </div>
                                                    <span className="text-xs text-muted-foreground">
                                                        {template.description}
                                                    </span>
                                                </DropdownMenuItem>
                                            ))
                                        )}
                                    </DropdownMenuContent>
                                </DropdownMenu>
                            </div>
                        </div>

                        {/* YAML Editor with Validation */}
                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <Label htmlFor="yaml_config">YAML Configuration *</Label>
                                <div className="flex items-center gap-2">
                                    {isValidating && (
                                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                                            <Loader2 className="h-3 w-3 animate-spin" />
                                            Validating...
                                        </span>
                                    )}
                                    {!isValidating && isValid === true && (
                                        <span className="text-xs text-green-600 flex items-center gap-1">
                                            <CheckCircle className="h-3 w-3" />
                                            Valid YAML
                                        </span>
                                    )}
                                    {!isValidating && isValid === false && (
                                        <span className="text-xs text-red-600 flex items-center gap-1">
                                            <XCircle className="h-3 w-3" />
                                            {validationErrors.length} error(s)
                                        </span>
                                    )}
                                </div>
                            </div>
                            <Textarea
                                id="yaml_config"
                                value={yamlConfig}
                                onChange={(e) => setYamlConfig(e.target.value)}
                                placeholder="Enter YAML configuration or select a template..."
                                className={cn(
                                    "font-mono text-sm min-h-[400px]",
                                    isValid === false && "border-red-300 focus-visible:ring-red-500"
                                )}
                                disabled={isSubmitting}
                            />

                            {/* Validation Errors */}
                            {validationErrors.length > 0 && (
                                <div className="bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900 rounded-md p-3 space-y-2">
                                    <div className="flex items-center gap-2 text-red-800 dark:text-red-200 font-medium text-sm">
                                        <AlertCircle className="h-4 w-4" />
                                        Validation Errors
                                    </div>
                                    <ul className="space-y-1">
                                        {validationErrors.map((error, idx) => (
                                            <li key={idx} className="text-xs text-red-700 dark:text-red-300">
                                                <span className="font-mono bg-red-100 dark:bg-red-900/30 px-1 rounded">
                                                    {error.field}
                                                </span>
                                                {": "}
                                                {error.message}
                                                {error.expected && (
                                                    <span className="text-red-500">
                                                        {" "}(expected: {error.expected})
                                                    </span>
                                                )}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            <p className="text-xs text-muted-foreground">
                                Configure data source filters, splitting strategy, and output format.
                                <a
                                    href="/docs/yaml-guide"
                                    target="_blank"
                                    className="ml-1 text-primary hover:underline"
                                >
                                    View YAML Guide →
                                </a>
                            </p>
                        </div>

                        {/* Submit */}
                        <div className="flex justify-end gap-2 pt-4">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => router.push("/ml-scenarios")}
                                disabled={isSubmitting}
                            >
                                Cancel
                            </Button>
                            <Button type="submit" disabled={isSubmitting || isValid === false}>
                                {isSubmitting ? (
                                    <>
                                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                        Creating...
                                    </>
                                ) : (
                                    <>
                                        <Upload className="h-4 w-4 mr-2" />
                                        Create Scenario
                                    </>
                                )}
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </form>
        </div>
    );
}
