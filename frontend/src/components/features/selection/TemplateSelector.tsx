"use client";

import { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Loader2, Search, BookTemplate, Check, ChevronsUpDown } from "lucide-react";
import { datasetsApi } from "@/lib/api";
import type { DatasetTemplateRecord } from "@/types";
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover";
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from "@/components/ui/command";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface TemplateSelectorProps {
    onApplyTemplate: (featureNames: string[]) => void;
    disabled?: boolean;
}

export function TemplateSelector({ onApplyTemplate, disabled }: TemplateSelectorProps) {
    const [templates, setTemplates] = useState<DatasetTemplateRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [open, setOpen] = useState(false);
    const [appliedTemplate, setAppliedTemplate] = useState<string | null>(null);

    // Load templates on mount
    useEffect(() => {
        async function loadTemplates() {
            try {
                setLoading(true);
                const response = await datasetsApi.listTemplates();
                setTemplates(response.items);
            } catch (err) {
                console.error("Failed to load templates:", err);
            } finally {
                setLoading(false);
            }
        }
        loadTemplates();
    }, []);

    const handleSelect = (template: DatasetTemplateRecord) => {
        onApplyTemplate(template.feature_names);
        setAppliedTemplate(template.name);
        setOpen(false);
    };

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={open}
                    disabled={disabled}
                    className={cn(
                        "w-72 justify-between bg-background/95 backdrop-blur-sm shadow-sm hover:bg-accent/50",
                        !appliedTemplate && "text-muted-foreground"
                    )}
                >
                    <div className="flex items-center gap-2 truncate">
                        {appliedTemplate ? (
                            <>
                                <BookTemplate className="h-4 w-4 text-purple-600" />
                                <span className="font-semibold text-foreground truncate">{appliedTemplate}</span>
                            </>
                        ) : (
                            <>
                                <BookTemplate className="h-4 w-4 opacity-50" />
                                <span>Select a template...</span>
                            </>
                        )}
                    </div>
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-[400px] p-0" align="start" sideOffset={8}>
                <Command className="border-none shadow-none">
                    <CommandInput placeholder="Search templates..." />
                    {loading ? (
                        <div className="flex justify-center py-6">
                            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                        </div>
                    ) : (
                        <CommandList>
                            <CommandEmpty className="py-6 text-center text-xs text-muted-foreground">No templates found.</CommandEmpty>
                            <CommandGroup heading="Available Templates">
                                {templates.map((template) => (
                                    <CommandItem
                                        key={template.id}
                                        value={template.name}
                                        onSelect={() => handleSelect(template)}
                                        className={cn(
                                            "flex flex-col items-start gap-1 py-3 cursor-pointer border-l-2 transition-all duration-200",
                                            "aria-selected:bg-slate-100 dark:aria-selected:bg-slate-800 aria-selected:border-purple-500", // Hover effect
                                            appliedTemplate === template.name
                                                ? "bg-purple-50/60 dark:bg-purple-900/20 border-purple-600 pl-3"
                                                : "border-transparent pl-3"
                                        )}
                                    >
                                        <div className="flex items-center justify-between w-full">
                                            <div className="flex items-center gap-2">
                                                <BookTemplate className={cn(
                                                    "h-3.5 w-3.5 transition-colors",
                                                    appliedTemplate === template.name ? "text-purple-600" : "text-slate-400 group-aria-selected:text-purple-500"
                                                )} />
                                                <span className={cn(
                                                    "font-medium text-sm transition-colors",
                                                    appliedTemplate === template.name ? "text-purple-700 dark:text-purple-300" : "text-foreground group-aria-selected:text-purple-700"
                                                )}>{template.name}</span>
                                            </div>
                                            <Badge variant="secondary" className={cn(
                                                "text-[10px] h-4 px-1.5 transition-colors",
                                                appliedTemplate === template.name ? "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300" : "bg-slate-100 dark:bg-slate-800"
                                            )}>
                                                {template.feature_names.length}
                                            </Badge>
                                        </div>
                                        <span className={cn(
                                            "text-xs line-clamp-2 pl-5.5 text-left transition-colors",
                                            appliedTemplate === template.name ? "text-purple-600/80 dark:text-purple-400/80" : "text-muted-foreground group-aria-selected:text-foreground"
                                        )}>
                                            {template.description}
                                        </span>
                                        {appliedTemplate === template.name && (
                                            <Check className="h-3 w-3 text-purple-600 absolute right-2 top-3" />
                                        )}
                                    </CommandItem>
                                ))}
                            </CommandGroup>
                        </CommandList>
                    )}
                </Command>
            </PopoverContent>
        </Popover>
    );
}
