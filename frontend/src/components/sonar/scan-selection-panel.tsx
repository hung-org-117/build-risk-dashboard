"use client";

import { useState, useEffect } from "react";
import { BarChart3, Shield, Info } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScanMetricsSelector, type AvailableMetrics } from "./scan-metrics-selector";
import { cn } from "@/lib/utils";
import { settingsApi } from "@/lib/api";

export interface EnabledTools {
    sonarqube: boolean;
    trivy: boolean;
}

interface ScanSelectionPanelProps {
    selectedSonarMetrics: string[];
    selectedTrivyMetrics: string[];
    onSonarMetricsChange: (metrics: string[]) => void;
    onTrivyMetricsChange: (metrics: string[]) => void;
    enabledTools: EnabledTools;
    onEnabledToolsChange: (tools: EnabledTools) => void;
    disabled?: boolean;
}

export function ScanSelectionPanel({
    selectedSonarMetrics,
    selectedTrivyMetrics,
    onSonarMetricsChange,
    onTrivyMetricsChange,
    enabledTools,
    onEnabledToolsChange,
    disabled = false,
}: ScanSelectionPanelProps) {
    const [availableMetrics, setAvailableMetrics] = useState<AvailableMetrics | null>(null);
    const [loading, setLoading] = useState(true);

    // Fetch available metrics on mount
    useEffect(() => {
        const fetchMetrics = async () => {
            try {
                setLoading(true);
                const data = await settingsApi.getAvailableMetrics();
                setAvailableMetrics(data);
            } catch (err) {
                console.error("Failed to fetch available metrics:", err);
            } finally {
                setLoading(false);
            }
        };
        fetchMetrics();
    }, []);

    // Toggle tool
    const toggleTool = (tool: keyof EnabledTools) => {
        const newTools = { ...enabledTools, [tool]: !enabledTools[tool] };
        onEnabledToolsChange(newTools);

        // Clear metrics when disabling tool
        if (enabledTools[tool]) {
            if (tool === "sonarqube") onSonarMetricsChange([]);
            if (tool === "trivy") onTrivyMetricsChange([]);
        }
    };

    return (
        <Card className="h-full border-none shadow-none bg-transparent">
            <CardContent className="p-0 h-full flex flex-col">
                <Tabs defaultValue="sonarqube" className="flex-1 flex flex-col min-h-0">
                    <TabsList className="grid w-full grid-cols-2 mb-4 bg-muted/50">
                        <TabsTrigger value="sonarqube" className="flex items-center gap-2 data-[state=active]:bg-background data-[state=active]:shadow-sm">
                            <BarChart3 className="h-4 w-4" />
                            SonarQube
                        </TabsTrigger>
                        <TabsTrigger value="trivy" className="flex items-center gap-2 data-[state=active]:bg-background data-[state=active]:shadow-sm">
                            <Shield className="h-4 w-4" />
                            Trivy
                        </TabsTrigger>
                    </TabsList>

                    {/* SonarQube Content */}
                    <TabsContent value="sonarqube" className="mt-0 flex-1 overflow-y-auto min-h-0 space-y-4 pr-1">
                        <div className="space-y-3 pt-2">
                            <div className="flex items-center justify-between mb-2">
                                <h4 className="text-sm font-medium">Metric Selection</h4>
                                <Badge variant="outline" className="text-xs font-normal">
                                    {selectedSonarMetrics.length} selected
                                </Badge>
                            </div>
                            <ScanMetricsSelector
                                selectedSonarMetrics={selectedSonarMetrics}
                                selectedTrivyMetrics={[]}
                                onSonarChange={onSonarMetricsChange}
                                onTrivyChange={() => { }}
                                showOnlyTool="sonarqube"
                                availableMetrics={availableMetrics}
                                isLoading={loading}
                            />
                        </div>
                    </TabsContent>

                    {/* Trivy Content */}
                    <TabsContent value="trivy" className="mt-0 flex-1 overflow-y-auto min-h-0 space-y-4 pr-1">
                        <div className="space-y-3 pt-2">
                            <div className="flex items-center justify-between mb-2">
                                <h4 className="text-sm font-medium">Metric Selection</h4>
                                <Badge variant="outline" className="text-xs font-normal">
                                    {selectedTrivyMetrics.length} selected
                                </Badge>
                            </div>
                            <ScanMetricsSelector
                                selectedSonarMetrics={[]}
                                selectedTrivyMetrics={selectedTrivyMetrics}
                                onSonarChange={() => { }}
                                onTrivyChange={onTrivyMetricsChange}
                                showOnlyTool="trivy"
                                availableMetrics={availableMetrics}
                                isLoading={loading}
                            />
                        </div>
                    </TabsContent>
                </Tabs>
            </CardContent>
        </Card>
    );
}
