"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Editor from "@monaco-editor/react";
import yaml from "js-yaml";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
    AlertTriangle,
    ArrowLeft,
    BookOpen,
    Check,
    FileText,
    Upload,
    PanelRightClose,
    PanelRightOpen,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

interface Template {
    name: string;
    filename: string;
    content: string;
}

interface YamlImportFormProps {
    guideContent: string;
    templates: Template[];
}

export function YamlImportForm({ guideContent, templates }: YamlImportFormProps) {
    // Default to the first template if available
    const initialContent = templates.length > 0 ? templates[0].content : "";

    const [content, setContent] = useState(initialContent);
    const [error, setError] = useState<string | null>(null);
    // Expand guide by default on large screens
    const [showGuide, setShowGuide] = useState(true);

    const router = useRouter();
    const { toast } = useToast();

    // If templates change (unlikely), reset content? Maybe not. 
    // But helpful to ensure we have something on load if initialContent was empty.
    useEffect(() => {
        if (!content && templates.length > 0) {
            setContent(templates[0].content);
        }
    }, [templates, content]);

    const handleImport = () => {
        setError(null);
        try {
            const data = yaml.load(content) as any;

            // Basic Validation
            if (!data || typeof data !== "object") {
                throw new Error("Invalid YAML format: Root must be an object");
            }
            if (!data.scenario?.name) {
                throw new Error("Missing required field: scenario.name");
            }
            if (!data.splitting) {
                throw new Error("Missing required section: splitting");
            }

            // Save to localStorage for the create page to pick up
            localStorage.setItem("scenario_import_draft", JSON.stringify(data));

            toast({
                title: "Configuration Loaded",
                description: "Redirecting to scenario creation wizard...",
            });

            router.push("/scenarios/create");
        } catch (e: any) {
            console.error(e);
            setError(e.message || "Failed to parse YAML");
            toast({
                title: "Import Failed",
                description: e.message || "Invalid YAML configuration",
                variant: "destructive",
            });
        }
    };

    return (
        // Adjusted height calculation and padding to fit better within standard app layout without global scroll
        // h-[calc(100vh-8rem)] accounts for header (~4rem) + some padding/margins
        <div className="flex flex-col gap-4 p-4 lg:flex-row lg:gap-6 w-full h-[calc(100vh-6rem)] overflow-hidden">
            {/* Left Column: Editor */}
            <div className={cn("flex flex-col gap-4 min-w-0 h-full", showGuide ? "flex-1" : "w-full")}>
                <div className="flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-2">
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => router.push("/scenarios/create")}
                            className="gap-2"
                        >
                            <ArrowLeft className="h-4 w-4" />
                            Back
                        </Button>
                        <h1 className="text-xl font-bold hidden md:block">Import Configuration</h1>
                    </div>
                    <div className="flex items-center gap-2">
                        <Select
                            onValueChange={(filename) => {
                                const template = templates.find(t => t.filename === filename);
                                if (template) {
                                    setContent(template.content);
                                }
                            }}
                        >
                            <SelectTrigger className="w-[180px] h-9 text-xs">
                                <SelectValue placeholder="Load Template" />
                            </SelectTrigger>
                            <SelectContent>
                                {templates.map(t => (
                                    <SelectItem key={t.filename} value={t.filename}>
                                        {t.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>

                        <Button
                            variant="outline"
                            size="icon"
                            className="h-9 w-9"
                            onClick={() => setShowGuide(!showGuide)}
                            title={showGuide ? "Hide Guide" : "Show Guide"}
                        >
                            {showGuide ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
                        </Button>

                        <Button onClick={handleImport} size="sm" className="gap-2 bg-green-600 hover:bg-green-700 h-9">
                            <Upload className="h-4 w-4" />
                            <span className="hidden sm:inline">Import & Create</span>
                            <span className="sm:hidden">Import</span>
                        </Button>
                    </div>
                </div>

                <Card className="flex-1 overflow-hidden border-slate-200 dark:border-slate-800 shadow-md">
                    <Editor
                        height="100%"
                        defaultLanguage="yaml"
                        theme="vs-dark"
                        value={content}
                        onChange={(value) => setContent(value || "")}
                        options={{
                            minimap: { enabled: false },
                            fontSize: 14,
                            scrollBeyondLastLine: false,
                            wordWrap: "on",
                            padding: { top: 16, bottom: 16 }
                        }}
                    />
                </Card>

                {error && (
                    <div className="flex items-center gap-2 rounded-md bg-red-50 p-3 text-red-900 dark:bg-red-900/20 dark:text-red-200 shrink-0">
                        <AlertTriangle className="h-4 w-4" />
                        <span className="text-sm font-medium">{error}</span>
                    </div>
                )}
            </div>

            {/* Right Column: Documentation */}
            {showGuide && (
                <div className="w-full lg:w-[500px] flex flex-col gap-4 h-full">
                    <div className="flex items-center gap-2 px-2 h-9 shrink-0">
                        <BookOpen className="h-5 w-5 text-muted-foreground" />
                        <h2 className="font-semibold text-sm">Format Guide</h2>
                    </div>
                    <Card className="flex-1 overflow-hidden border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50">
                        <div className="h-full overflow-y-auto p-6 text-sm 
                            prose dark:prose-invert max-w-none 
                            prose-pre:bg-slate-900 prose-pre:border prose-pre:border-slate-800
                            prose-table:border-collapse prose-table:w-full prose-table:border prose-table:border-slate-200 dark:prose-table:border-slate-700
                            prose-th:border prose-th:border-slate-200 dark:prose-th:border-slate-700 prose-th:p-2 prose-th:bg-slate-100 dark:prose-th:bg-slate-800
                            prose-td:border prose-td:border-slate-200 dark:prose-td:border-slate-700 prose-td:p-2">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {guideContent}
                            </ReactMarkdown>
                        </div>
                    </Card>
                </div>
            )}
        </div>
    );
}
