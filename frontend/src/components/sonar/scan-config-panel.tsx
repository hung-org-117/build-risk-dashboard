"use client";

import { useState } from "react";
import { Settings, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScanMetricsSelector } from "./scan-metrics-selector";

// =============================================================================
// Types
// =============================================================================

export interface SonarConfig {
    projectKey?: string;
    sonarToken?: string;
    sonarUrl?: string;
    extraProperties?: string; // Additional sonar-scanner properties
}

export interface TrivyConfig {
    severity?: string; // e.g., "CRITICAL,HIGH,MEDIUM"
    ignoreUnfixed?: boolean;
    scanners?: string; // e.g., "vuln,misconfig,secret"
    extraArgs?: string; // Additional CLI arguments
}

export interface ScanConfig {
    sonarqube: SonarConfig;
    trivy: TrivyConfig;
}

interface ScanConfigPanelProps {
    selectedSonarMetrics: string[];
    selectedTrivyMetrics: string[];
    onSonarMetricsChange: (metrics: string[]) => void;
    onTrivyMetricsChange: (metrics: string[]) => void;
    scanConfig: ScanConfig;
    onScanConfigChange: (config: ScanConfig) => void;
    disabled?: boolean;
}

// =============================================================================
// Default Config
// =============================================================================

const DEFAULT_SCAN_CONFIG: ScanConfig = {
    sonarqube: {
        projectKey: "",
        sonarToken: "",
        sonarUrl: "",
        extraProperties: "",
    },
    trivy: {
        severity: "CRITICAL,HIGH,MEDIUM",
        ignoreUnfixed: false,
        scanners: "vuln,misconfig,secret",
        extraArgs: "",
    },
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
    disabled = false,
}: ScanConfigPanelProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [activeTab, setActiveTab] = useState("metrics");

    const totalMetrics = selectedSonarMetrics.length + selectedTrivyMetrics.length;
    const hasConfig =
        scanConfig.sonarqube.projectKey ||
        scanConfig.sonarqube.sonarToken ||
        scanConfig.trivy.extraArgs;

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
                        {(totalMetrics > 0 || hasConfig) && (
                            <span className="bg-primary/10 text-primary text-xs px-2 py-0.5 rounded-full">
                                {totalMetrics} metrics
                                {hasConfig && " • configured"}
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
                        <CardTitle className="text-base">
                            Scan Settings & Metrics Selection
                        </CardTitle>
                        <CardDescription>
                            Configure scan tools and select metrics to include in features
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Tabs value={activeTab} onValueChange={setActiveTab}>
                            <TabsList className="grid w-full grid-cols-2 mb-4">
                                <TabsTrigger value="metrics">
                                    📊 Metrics Selection
                                </TabsTrigger>
                                <TabsTrigger value="config">
                                    ⚙️ Tool Configuration
                                </TabsTrigger>
                            </TabsList>

                            {/* Metrics Selection Tab */}
                            <TabsContent value="metrics">
                                <ScanMetricsSelector
                                    selectedSonarMetrics={selectedSonarMetrics}
                                    selectedTrivyMetrics={selectedTrivyMetrics}
                                    onSonarChange={onSonarMetricsChange}
                                    onTrivyChange={onTrivyMetricsChange}
                                />
                            </TabsContent>

                            {/* Configuration Tab */}
                            <TabsContent value="config" className="space-y-6">
                                {/* SonarQube Configuration */}
                                <div className="space-y-4">
                                    <h4 className="font-medium flex items-center gap-2">
                                        <span className="text-blue-600">🔵</span>
                                        SonarQube Configuration
                                    </h4>

                                    <div className="grid gap-4 pl-6">
                                        <div className="grid gap-2">
                                            <Label htmlFor="sonar-url">
                                                SonarQube Server URL
                                            </Label>
                                            <Input
                                                id="sonar-url"
                                                placeholder="https://sonarqube.example.com"
                                                value={scanConfig.sonarqube.sonarUrl || ""}
                                                onChange={(e) =>
                                                    updateSonarConfig("sonarUrl", e.target.value)
                                                }
                                                disabled={disabled}
                                            />
                                            <p className="text-xs text-muted-foreground">
                                                Leave empty to use default server
                                            </p>
                                        </div>

                                        <div className="grid gap-2">
                                            <Label htmlFor="sonar-token">
                                                SonarQube Token
                                            </Label>
                                            <Input
                                                id="sonar-token"
                                                type="password"
                                                placeholder="squ_xxxxx..."
                                                value={scanConfig.sonarqube.sonarToken || ""}
                                                onChange={(e) =>
                                                    updateSonarConfig("sonarToken", e.target.value)
                                                }
                                                disabled={disabled}
                                            />
                                            <p className="text-xs text-muted-foreground">
                                                Authentication token for SonarQube API
                                            </p>
                                        </div>

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
                                                disabled={disabled}
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
sonar.coverage.jacoco.xmlReportPaths=coverage.xml
sonar.exclusions=**/test/**`}
                                                value={scanConfig.sonarqube.extraProperties || ""}
                                                onChange={(e) =>
                                                    updateSonarConfig("extraProperties", e.target.value)
                                                }
                                                disabled={disabled}
                                                rows={4}
                                                className="font-mono text-sm"
                                            />
                                            <p className="text-xs text-muted-foreground">
                                                Additional sonar-scanner properties (one per line)
                                            </p>
                                        </div>
                                    </div>
                                </div>

                                {/* Trivy Configuration */}
                                <div className="space-y-4 border-t pt-6">
                                    <h4 className="font-medium flex items-center gap-2">
                                        <span className="text-green-600">🟢</span>
                                        Trivy Configuration
                                    </h4>

                                    <div className="grid gap-4 pl-6">
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
                                                disabled={disabled}
                                            />
                                            <p className="text-xs text-muted-foreground">
                                                Comma-separated severity levels to include
                                            </p>
                                        </div>

                                        <div className="grid gap-2">
                                            <Label htmlFor="trivy-scanners">
                                                Scanners
                                            </Label>
                                            <Input
                                                id="trivy-scanners"
                                                placeholder="vuln,misconfig,secret"
                                                value={scanConfig.trivy.scanners || ""}
                                                onChange={(e) =>
                                                    updateTrivyConfig("scanners", e.target.value)
                                                }
                                                disabled={disabled}
                                            />
                                            <p className="text-xs text-muted-foreground">
                                                Comma-separated scanner types: vuln, misconfig,
                                                secret, license
                                            </p>
                                        </div>

                                        <div className="grid gap-2">
                                            <Label htmlFor="trivy-extra">
                                                Extra CLI Arguments
                                            </Label>
                                            <Textarea
                                                id="trivy-extra"
                                                placeholder={`--ignore-unfixed
--skip-dirs node_modules
--cache-dir /tmp/trivy`}
                                                value={scanConfig.trivy.extraArgs || ""}
                                                onChange={(e) =>
                                                    updateTrivyConfig("extraArgs", e.target.value)
                                                }
                                                disabled={disabled}
                                                rows={3}
                                                className="font-mono text-sm"
                                            />
                                            <p className="text-xs text-muted-foreground">
                                                Additional Trivy CLI arguments (one per line)
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </TabsContent>
                        </Tabs>
                    </CardContent>
                </Card>
            </CollapsibleContent>
        </Collapsible>
    );
}

export { DEFAULT_SCAN_CONFIG };
