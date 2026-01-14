"use client";

import { memo, useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
    AlertCircle,
    Check,
    ChevronDown,
    ChevronRight,
    FileText,
    GitBranch,
    Search,
    Settings,
    Shield,
    Github,
    Database,
    Box,
} from "lucide-react";
import type { NodeInfo } from "../types";

interface ListViewProps {
    nodes: NodeInfo[];
    selectedFeatures: Set<string>;
    expandedNodes: Set<string>;
    onToggleFeature: (featureName: string) => void;
    onToggleNode: (nodeName: string, features: string[]) => void;
    onToggleNodeExpand: (nodeName: string) => void;
    searchQuery: string;
    onSearchChange: (query: string) => void;
    isLoading?: boolean;
}

const groupIcons: Record<string, typeof GitBranch> = {
    git: GitBranch,
    github: Github,
    build_log: FileText,
    sonar: Settings,
    security: Shield,
    repo: Database,
};

export const ListView = memo(function ListView({
    nodes,
    selectedFeatures,
    expandedNodes,
    onToggleFeature,
    onToggleNode,
    onToggleNodeExpand,
    searchQuery,
    onSearchChange,
    isLoading = false,
}: ListViewProps) {
    if (isLoading) {
        return (
            <div className="flex h-full items-center justify-center">
                <div className="text-muted-foreground">Loading features...</div>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col">
            {/* Search */}
            <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                    placeholder="Search features..."
                    value={searchQuery}
                    onChange={(e) => onSearchChange(e.target.value)}
                    className="pl-10 flex-shrink-0"
                />
            </div>

            {/* Nodes */}
            <div className="flex-1 space-y-3 overflow-y-auto pr-2">
                {nodes.map((node) => (
                    <NodeCard
                        key={node.name}
                        node={node}
                        selectedFeatures={selectedFeatures}
                        isExpanded={expandedNodes.has(node.name)}
                        onToggleNode={() =>
                            onToggleNode(
                                node.name,
                                node.features.map((f) => f.name)
                            )
                        }
                        onToggleExpand={() => onToggleNodeExpand(node.name)}
                        onToggleFeature={onToggleFeature}
                    />
                ))}
            </div>

            {nodes.length === 0 && (
                <div className="flex-1 flex items-center justify-center text-muted-foreground">
                    No features match your search
                </div>
            )}
        </div>
    );
});

interface NodeCardProps {
    node: NodeInfo;
    selectedFeatures: Set<string>;
    isExpanded: boolean;
    onToggleNode: () => void;
    onToggleExpand: () => void;
    onToggleFeature: (featureName: string) => void;
}

function NodeCard({
    node,
    selectedFeatures,
    isExpanded,
    onToggleNode,
    onToggleExpand,
    onToggleFeature,
}: NodeCardProps) {
    const Icon = groupIcons[node.group] || Box;

    const selectedCount = node.features.filter((f) =>
        selectedFeatures.has(f.name)
    ).length;
    const allSelected = selectedCount === node.features.length && node.features.length > 0;
    const someSelected = selectedCount > 0 && selectedCount < node.features.length;

    // Manual expand/collapse - avoid Collapsible component event bubbling issues
    return (
        <div
            className={`rounded-lg border ${node.is_configured
                ? "border-slate-200 dark:border-slate-700"
                : "border-dashed border-slate-300 opacity-75 dark:border-slate-600"
                }`}
        >
            {/* Node Header */}
            <div
                className={`flex items-center justify-between p-3 ${node.is_configured ? "hover:bg-slate-50 dark:hover:bg-slate-800/50" : ""
                    }`}
            >
                <div className="flex items-center gap-3">
                    {/* Custom Checkbox for reliable rendering of states */}
                    <button
                        type="button"
                        onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            onToggleNode();
                        }}
                        className="flex items-center justify-center focus:outline-none"
                    >
                        <div
                            className={`h-4 w-4 shrink-0 rounded-sm border flex items-center justify-center transition-colors ${allSelected
                                    ? "bg-primary border-primary text-primary-foreground"
                                    : someSelected
                                        ? "bg-yellow-500 border-yellow-500 text-white"
                                        : "border-slate-500 bg-transparent"
                                }`}
                        >
                            {allSelected && <Check className="h-3 w-3" />}
                            {someSelected && <div className="h-0.5 w-2 bg-current" />}
                        </div>
                    </button>
                    {/* Clickable area for expand */}
                    <button
                        type="button"
                        className="flex-1 cursor-pointer text-left"
                        onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            onToggleExpand();
                        }}
                    >
                        <div className="flex items-center gap-2">
                            <span className="font-medium">{node.display_name}</span>
                        </div>
                        <p className="text-xs text-muted-foreground">{node.description}</p>
                    </button>
                </div>

                {/* Badge and chevron - also triggers expand */}
                <button
                    type="button"
                    className="flex items-center gap-2 cursor-pointer"
                    onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        onToggleExpand();
                    }}
                >
                    <Badge
                        variant={allSelected ? "default" : someSelected ? "secondary" : "outline"}
                        className="text-xs"
                    >
                        {selectedCount}/{node.feature_count}
                    </Badge>
                    {isExpanded ? (
                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    ) : (
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    )}
                </button>
            </div>

            {/* Features - manually controlled visibility */}
            {isExpanded && node.is_configured && (
                <div className="border-t p-3 pt-2">
                    <div className="space-y-1">
                        {node.features.map((feature) => (
                            <label
                                key={feature.name}
                                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 hover:bg-slate-100 dark:hover:bg-slate-700"
                            >
                                <Checkbox
                                    checked={selectedFeatures.has(feature.name)}
                                    onCheckedChange={() => onToggleFeature(feature.name)}
                                />
                                <div className="flex-1 min-w-0">
                                    <span className="text-sm font-mono">{feature.name}</span>
                                    <p className="truncate text-xs text-muted-foreground">
                                        {feature.description}
                                    </p>
                                </div>
                            </label>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
