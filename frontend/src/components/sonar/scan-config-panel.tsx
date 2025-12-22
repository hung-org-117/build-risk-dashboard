"use client";

import { useState } from "react";
import { Settings, ChevronDown, ChevronUp, BarChart3, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from "@/components/ui/accordion";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScanMetricsSelector } from "./scan-metrics-selector";

// =============================================================================
// Types
// =============================================================================

export interface SonarConfig {
    projectKey?: string;
    extraProperties?: string;
}

export interface TrivyConfig {
    severity?: string;
    ignoreUnfixed?: boolean;
    scanners?: string;
    extraArgs?: string;
}

export interface ScanConfig {
    sonarqube: SonarConfig;
    trivy: TrivyConfig;
}

export interface EnabledTools {
    sonarqube: boolean;
    trivy: boolean;
}

interface ScanConfigPanelProps {
    selectedSonarMetrics: string[];
    selectedTrivyMetrics: string[];
    onSonarMetricsChange: (metrics: string[]) => void;
    onTrivyMetricsChange: (metrics: string[]) => void;
    scanConfig: ScanConfig;
    onScanConfigChange: (config: ScanConfig) => void;
    enabledTools?: EnabledTools;
    onEnabledToolsChange?: (tools: EnabledTools) => void;
    disabled?: boolean;
}

// =============================================================================
// Default Config
// =============================================================================

const DEFAULT_SCAN_CONFIG: ScanConfig = {
    sonarqube: {
        projectKey: "",
        extraProperties: "",
    },
    trivy: {
        severity: "CRITICAL,HIGH,MEDIUM",
        ignoreUnfixed: false,
        scanners: "vuln,misconfig,secret",
        extraArgs: "",
    },
};

const DEFAULT_ENABLED_TOOLS: EnabledTools = {
    sonarqube: false,
    trivy: false,
};

// =============================================================================
// Component
// =============================================================================

export function ScanConfigPanel({
    selectedSonarMetrics,
    selectedTrivyMetrics,
    onSonarMetricsChange,
    onTrivyMetricsChange,
    scanConfig,
    onScanConfigChange,
    enabledTools = DEFAULT_ENABLED_TOOLS,
    onEnabledToolsChange,
    disabled = false,
}: ScanConfigPanelProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [internalEnabledTools, setInternalEnabledTools] = useState<EnabledTools>(enabledTools);

    // Use external or internal state
    const tools = onEnabledToolsChange ? enabledTools : internalEnabledTools;
    const setTools = onEnabledToolsChange || setInternalEnabledTools;

    const totalMetrics = selectedSonarMetrics.length + selectedTrivyMetrics.length;
    const enabledCount = (tools.sonarqube ? 1 : 0) + (tools.trivy ? 1 : 0);

    // Toggle tool
    const toggleTool = (tool: keyof EnabledTools) => {
        const newTools = { ...tools, [tool]: !tools[tool] };
        setTools(newTools);

        // Clear metrics when disabling tool
        if (tools[tool]) {
            if (tool === "sonarqube") onSonarMetricsChange([]);
            if (tool === "trivy") onTrivyMetricsChange([]);
        }
    };

    // Update SonarQube config
    const updateSonarConfig = (key: keyof SonarConfig, value: string | boolean) => {
        onScanConfigChange({
            ...scanConfig,
            sonarqube: {
                ...scanConfig.sonarqube,
                [key]: value,
            },
        });
    };

    // Update Trivy config
    const updateTrivyConfig = (key: keyof TrivyConfig, value: string | boolean) => {
        onScanConfigChange({
            ...scanConfig,
            trivy: {
                ...scanConfig.trivy,
                [key]: value,
            },
        });
    };

    return (
        <Collapsible open={isOpen} onOpenChange={setIsOpen}>
            <CollapsibleTrigger asChild>
                <Button
                    variant="outline"
                    className="w-full justify-between"
                    disabled={disabled}
                >
                    <span className="flex items-center gap-2">
                        <Settings className="h-4 w-4" />
                        Scan Configuration
                        {enabledCount > 0 && (
                            <span className="bg-primary/10 text-primary text-xs px-2 py-0.5 rounded-full">
                                {enabledCount} tool{enabledCount > 1 ? "s" : ""}
                                {totalMetrics > 0 && ` • ${totalMetrics} metrics`}
                            </span>
                        )}
                    </span>
                    {isOpen ? (
                        <ChevronUp className="h-4 w-4" />
                    ) : (
                        <ChevronDown className="h-4 w-4" />
                    )}
                </Button>
            </CollapsibleTrigger>

            <CollapsibleContent className="pt-4">
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Select Scan Tools</CardTitle>
                        <CardDescription>
                            Choose which tools to run, then configure each tool below
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {/* Tool Selection */}
                        <div className="flex flex-wrap gap-4">
                            <label
                                className={`flex items-center gap-3 px-4 py-3 rounded-lg border cursor-pointer transition-all ${tools.sonarqube
                                        ? "bg-blue-50 border-blue-300 dark:bg-blue-900/20"
                                        : "hover:bg-muted/50"
                                    }`}
                            >
                                <Checkbox
                                    checked={tools.sonarqube}
                                    onCheckedChange={() => toggleTool("sonarqube")}
                                />
                                <div className="flex items-center gap-2">
                                    <BarChart3 className="h-4 w-4 text-blue-600" />
                                    <span className="font-medium">SonarQube</span>
                                </div>
                                {selectedSonarMetrics.length > 0 && (
                                    <Badge variant="secondary" className="ml-2">
                                        {selectedSonarMetrics.length} metrics
                                    </Badge>
                                )}
                            </label>

                            <label
                                className={`flex items-center gap-3 px-4 py-3 rounded-lg border cursor-pointer transition-all ${tools.trivy
                                        ? "bg-green-50 border-green-300 dark:bg-green-900/20"
                                        : "hover:bg-muted/50"
                                    }`}
                            >
                                <Checkbox
                                    checked={tools.trivy}
                                    onCheckedChange={() => toggleTool("trivy")}
                                />
                                <div className="flex items-center gap-2">
                                    <Shield className="h-4 w-4 text-green-600" />
                                    <span className="font-medium">Trivy</span>
                                </div>
                                {selectedTrivyMetrics.length > 0 && (
                                    <Badge variant="secondary" className="ml-2">
                                        {selectedTrivyMetrics.length} metrics
                                    </Badge>
                                )}
                            </label>
                        </div>

                        {/* Tool Configuration Sections */}
                        {(tools.sonarqube || tools.trivy) && (
                            <Accordion type="multiple" className="mt-4">
                                {/* SonarQube Section */}
                                {tools.sonarqube && (
                                    <AccordionItem value="sonarqube">
                                        <AccordionTrigger className="hover:no-underline">
                                            <div className="flex items-center gap-2">
                                                <BarChart3 className="h-4 w-4 text-blue-600" />
                                                <span>SonarQube Settings</span>
                                                <Badge variant="outline" className="ml-2">
                                                    {selectedSonarMetrics.length} metrics
                                                </Badge>
                                            </div>
                                        </AccordionTrigger>
                                        <AccordionContent className="pt-4 space-y-6">
                                            {/* Configuration */}
                                            <div className="space-y-4">
                                                <h5 className="text-sm font-medium text-muted-foreground">
                                                    Configuration
                                                </h5>
                                                <div className="grid gap-4 pl-4">
                                                    <div className="grid gap-2">
                                                        <Label htmlFor="sonar-project-key">
                                                            Project Key (Optional)
                                                        </Label>
                                                        <Input
                                                            id="sonar-project-key"
                                                            placeholder="my-project-key"
                                                            value={scanConfig.sonarqube.projectKey || ""}
                                                            onChange={(e) =>
                                                                updateSonarConfig("projectKey", e.target.value)
                                                            }
                                                        />
                                                        <p className="text-xs text-muted-foreground">
                                                            Override auto-generated project key
                                                        </p>
                                                    </div>
                                                    <div className="grid gap-2">
                                                        <Label htmlFor="sonar-extra">
                                                            Extra Scanner Properties
                                                        </Label>
                                                        <Textarea
                                                            id="sonar-extra"
                                                            placeholder={`sonar.java.binaries=target/classes
sonar.exclusions=**/test/**`}
                                                            value={scanConfig.sonarqube.extraProperties || ""}
                                                            onChange={(e) =>
                                                                updateSonarConfig("extraProperties", e.target.value)
                                                            }
                                                            rows={3}
                                                            className="font-mono text-sm"
                                                        />
                                                    </div>
                                                </div>
                                            </div>

                                            {/* Metrics Selection */}
                                            <div className="space-y-4 border-t pt-4">
                                                <h5 className="text-sm font-medium text-muted-foreground">
                                                    Metrics Selection
                                                </h5>
                                                <ScanMetricsSelector
                                                    selectedSonarMetrics={selectedSonarMetrics}
                                                    selectedTrivyMetrics={[]}
                                                    onSonarChange={onSonarMetricsChange}
                                                    onTrivyChange={() => { }}
                                                    showOnlyTool="sonarqube"
                                                />
                                            </div>
                                        </AccordionContent>
                                    </AccordionItem>
                                )}

                                {/* Trivy Section */}
                                {tools.trivy && (
                                    <AccordionItem value="trivy">
                                        <AccordionTrigger className="hover:no-underline">
                                            <div className="flex items-center gap-2">
                                                <Shield className="h-4 w-4 text-green-600" />
                                                <span>Trivy Settings</span>
                                                <Badge variant="outline" className="ml-2">
                                                    {selectedTrivyMetrics.length} metrics
                                                </Badge>
                                            </div>
                                        </AccordionTrigger>
                                        <AccordionContent className="pt-4 space-y-6">
                                            {/* Configuration */}
                                            <div className="space-y-4">
                                                <h5 className="text-sm font-medium text-muted-foreground">
                                                    Configuration
                                                </h5>
                                                <div className="grid gap-4 pl-4">
                                                    <div className="grid gap-2">
                                                        <Label htmlFor="trivy-severity">
                                                            Severity Filter
                                                        </Label>
                                                        <Input
                                                            id="trivy-severity"
                                                            placeholder="CRITICAL,HIGH,MEDIUM"
                                                            value={scanConfig.trivy.severity || ""}
                                                            onChange={(e) =>
                                                                updateTrivyConfig("severity", e.target.value)
                                                            }
                                                        />
                                                        <p className="text-xs text-muted-foreground">
                                                            Comma-separated severity levels
                                                        </p>
                                                    </div>
                                                    <div className="grid gap-2">
                                                        <Label htmlFor="trivy-scanners">Scanners</Label>
                                                        <Input
                                                            id="trivy-scanners"
                                                            placeholder="vuln,misconfig,secret"
                                                            value={scanConfig.trivy.scanners || ""}
                                                            onChange={(e) =>
                                                                updateTrivyConfig("scanners", e.target.value)
                                                            }
                                                        />
                                                        <p className="text-xs text-muted-foreground">
                                                            Scanner types: vuln, misconfig, secret, license
                                                        </p>
                                                    </div>
                                                    <div className="grid gap-2">
                                                        <Label htmlFor="trivy-extra">Extra CLI Arguments</Label>
                                                        <Textarea
                                                            id="trivy-extra"
                                                            placeholder={`--ignore-unfixed
--skip-dirs node_modules`}
                                                            value={scanConfig.trivy.extraArgs || ""}
                                                            onChange={(e) =>
                                                                updateTrivyConfig("extraArgs", e.target.value)
                                                            }
                                                            rows={2}
                                                            className="font-mono text-sm"
                                                        />
                                                    </div>
                                                </div>
                                            </div>

                                            {/* Metrics Selection */}
                                            <div className="space-y-4 border-t pt-4">
                                                <h5 className="text-sm font-medium text-muted-foreground">
                                                    Metrics Selection
                                                </h5>
                                                <ScanMetricsSelector
                                                    selectedSonarMetrics={[]}
                                                    selectedTrivyMetrics={selectedTrivyMetrics}
                                                    onSonarChange={() => { }}
                                                    onTrivyChange={onTrivyMetricsChange}
                                                    showOnlyTool="trivy"
                                                />
                                            </div>
                                        </AccordionContent>
                                    </AccordionItem>
                                )}
                            </Accordion>
                        )}

                        {/* Empty State */}
                        {!tools.sonarqube && !tools.trivy && (
                            <div className="text-center py-6 text-muted-foreground">
                                Select a tool above to configure it
                            </div>
                        )}
                    </CardContent>
                </Card>
            </CollapsibleContent>
        </Collapsible>
    );
}

export { DEFAULT_SCAN_CONFIG, DEFAULT_ENABLED_TOOLS };
