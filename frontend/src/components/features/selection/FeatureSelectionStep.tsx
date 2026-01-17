"use client";

import { useCallback, useState } from "react";
import {
    Loader2,
    AlertTriangle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";

import {
    GraphView,
    ListView,
    SelectedFeaturesPanel,
    TemplateSelector,
    ViewToggle,
} from "@/components/features/selection";

import { ScanSelectionPanel, type EnabledTools } from "@/components/sonar/scan-selection-panel";
import { UseFeatureSelectorReturn } from "@/components/features";

const DEFAULT_ENABLED_TOOLS: EnabledTools = {
    sonarqube: true,
    trivy: true,
};

export interface ScanMetrics {
    sonarqube: string[];
    trivy: string[];
}

interface FeatureSelectionStepProps {
    featureSelector: UseFeatureSelectorReturn;
    scanMetrics: ScanMetrics;
    onScanMetricsChange: (metrics: ScanMetrics) => void;
}

export function FeatureSelectionStep({
    featureSelector,
    scanMetrics,
    onScanMetricsChange,
}: FeatureSelectionStepProps) {
    // Local state for UI
    const [viewMode, setViewMode] = useState<"graph" | "list">("list");
    const [enabledTools, setEnabledTools] = useState<EnabledTools>(DEFAULT_ENABLED_TOOLS);

    const {
        extractorNodes,
        dagData,
        allFeatures,
        defaultFeatures,
        loading,
        selectedFeatures,
        expandedNodes,
        searchQuery,
        toggleFeature,
        toggleNode,
        toggleNodeExpand,
        clearSelection,
        selectAllAvailable,
        setSearchQuery,
        filteredNodes,
        applyTemplate,
    } = featureSelector;

    // Handle features change from graph view
    const handleGraphFeaturesChange = useCallback(
        (featuresList: string[]) => {
            const currentSet = selectedFeatures;
            const newSet = new Set(featuresList);
            // Don't deselect defaults
            defaultFeatures.forEach(f => newSet.add(f));

            newSet.forEach((f) => {
                if (!currentSet.has(f)) toggleFeature(f);
            });
            currentSet.forEach((f) => {
                if (!newSet.has(f) && !defaultFeatures.includes(f)) toggleFeature(f);
            });
        },
        [selectedFeatures, toggleFeature, defaultFeatures]
    );

    const handleClearScanMetrics = () => {
        onScanMetricsChange({ sonarqube: [], trivy: [] });
    };

    return (
        <div className="h-full flex flex-col overflow-hidden">
            {/* Content Area */}
            <div className="flex-1 border rounded-lg overflow-hidden bg-background shadow-sm">
                <ResizablePanelGroup direction="horizontal" className="h-full w-full">
                    {/* LEFT: Graph/List View - 60% */}
                    <ResizablePanel defaultSize={60} minSize={40}>
                        <div className="flex flex-col h-full relative bg-slate-50/50 dark:bg-slate-950/50">
                            {/* Toolbar */}
                            <div className="absolute top-4 left-4 right-4 z-10 flex flex-col gap-2 pointer-events-none">
                                <div className="flex items-center justify-between">
                                    <div className="pointer-events-auto">
                                        <TemplateSelector onApplyTemplate={applyTemplate} />
                                    </div>
                                    <div className="pointer-events-auto flex items-center gap-2 bg-background/80 backdrop-blur-sm p-1 rounded-lg shadow-sm">
                                        <ViewToggle value={viewMode} onChange={setViewMode} />
                                    </div>
                                </div>

                            </div>

                            {/* Visualization Content */}
                            <div className="flex-1 overflow-hidden pt-16">
                                {loading ? (
                                    <div className="flex h-full items-center justify-center">
                                        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                                    </div>
                                ) : viewMode === "graph" ? (
                                    <GraphView
                                        dagData={dagData}
                                        selectedFeatures={selectedFeatures}
                                        onFeaturesChange={handleGraphFeaturesChange}
                                        isLoading={loading}
                                    />
                                ) : (
                                    <div className="h-full flex flex-col p-4">
                                        <div className="flex-1 bg-background rounded-lg border shadow-sm overflow-hidden flex flex-col min-h-0">
                                            <ListView
                                                nodes={filteredNodes}
                                                selectedFeatures={selectedFeatures}
                                                expandedNodes={expandedNodes}
                                                onToggleFeature={toggleFeature}
                                                onToggleNode={toggleNode}
                                                onToggleNodeExpand={toggleNodeExpand}
                                                searchQuery={searchQuery}
                                                onSearchChange={setSearchQuery}
                                            />
                                        </div>
                                    </div>
                                )}
                            </div>

                        </div>
                    </ResizablePanel>

                    <ResizableHandle withHandle />

                    {/* RIGHT: Selected Features + Scans - 40% */}
                    <ResizablePanel defaultSize={40} minSize={25}>
                        <ResizablePanelGroup direction="vertical" className="h-full">
                            {/* Features Panel - 60% */}
                            <ResizablePanel defaultSize={60} minSize={20}>
                                <div className="h-full flex flex-col bg-background">
                                    <div className="px-4 py-2 border-b bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-between flex-shrink-0">
                                        <div className="flex items-center gap-2 font-medium text-sm">
                                            Features
                                            <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-[10px]">
                                                {selectedFeatures.size}
                                            </Badge>
                                        </div>
                                        <div className="flex items-center gap-1">
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={selectAllAvailable}
                                                className="h-7 text-xs text-muted-foreground hover:text-foreground px-2"
                                            >
                                                Select All
                                            </Button>
                                            <div className="w-px h-3 bg-border mx-1" />
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={clearSelection}
                                                className="h-7 text-xs text-muted-foreground hover:text-destructive px-2"
                                            >
                                                Clear All
                                            </Button>
                                        </div>
                                    </div>
                                    <div className="flex-1 overflow-y-auto min-h-0">
                                        {defaultFeatures.length > 0 && (
                                            <div className="mx-4 mt-3 mb-1 bg-blue-50/50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800 p-2.5 rounded-md text-xs text-blue-700 dark:text-blue-300 flex items-start gap-2">
                                                <AlertTriangle className="h-3.5 w-3.5 mt-0.5 flex-shrink-0 opacity-80" />
                                                <span className="leading-tight">
                                                    {defaultFeatures.length} core features are automatically included
                                                </span>
                                            </div>
                                        )}
                                        <SelectedFeaturesPanel
                                            selectedFeatures={selectedFeatures}
                                            allFeatures={allFeatures}
                                            nodes={extractorNodes}
                                            onRemoveFeature={toggleFeature}
                                            onClearAll={clearSelection}
                                            rowCount={0}
                                            className="border-none shadow-none h-full rounded-none"
                                            hideHeader={true}
                                            defaultFeatures={defaultFeatures}
                                        />
                                    </div>
                                </div>
                            </ResizablePanel>

                            <ResizableHandle withHandle />

                            {/* Scans Panel - 40% */}
                            <ResizablePanel defaultSize={40} minSize={20}>
                                <div className="h-full flex flex-col bg-background">
                                    <div className="px-4 py-2 border-b bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-between flex-shrink-0">
                                        <div className="flex items-center gap-2 font-medium text-sm">
                                            Scans
                                            {(scanMetrics.sonarqube.length > 0 || scanMetrics.trivy.length > 0) && (
                                                <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-[10px]">
                                                    {scanMetrics.sonarqube.length + scanMetrics.trivy.length}
                                                </Badge>
                                            )}
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={handleClearScanMetrics}
                                            className="h-7 text-xs text-muted-foreground hover:text-destructive px-2"
                                        >
                                            Clear All
                                        </Button>
                                    </div>
                                    <div className="flex-1 overflow-y-auto p-4 min-h-0">
                                        <ScanSelectionPanel
                                            selectedSonarMetrics={scanMetrics.sonarqube}
                                            selectedTrivyMetrics={scanMetrics.trivy}
                                            onSonarMetricsChange={(metrics) =>
                                                onScanMetricsChange({ ...scanMetrics, sonarqube: metrics })
                                            }
                                            onTrivyMetricsChange={(metrics) =>
                                                onScanMetricsChange({ ...scanMetrics, trivy: metrics })
                                            }
                                            enabledTools={enabledTools}
                                            onEnabledToolsChange={setEnabledTools}
                                        />
                                    </div>
                                </div>
                            </ResizablePanel>
                        </ResizablePanelGroup>
                    </ResizablePanel>
                </ResizablePanelGroup>
            </div>
        </div>
    );
}
