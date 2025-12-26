"use client";

import { Wrench, BarChart3, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from "@/components/ui/accordion";
import { RepoScanOverrideSection } from "./RepoScanOverrideSection";
import type { ScanConfig, SonarConfig, TrivyConfig, EnabledTools } from "./scan-config-panel";

interface RepoInfo {
    id: string;
    full_name: string;
}

interface ScanPropertiesPanelProps {
    scanConfig: ScanConfig;
    onScanConfigChange: (config: ScanConfig) => void;
    enabledTools: EnabledTools;
    disabled?: boolean;
    repos?: RepoInfo[];
}

export function ScanPropertiesPanel({
    scanConfig,
    onScanConfigChange,
    enabledTools,
    disabled = false,
    repos = [],
}: ScanPropertiesPanelProps) {

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
    const updateTrivyConfig = (key: keyof TrivyConfig, value: string) => {
        onScanConfigChange({
            ...scanConfig,
            trivy: {
                ...scanConfig.trivy,
                [key]: value,
            },
        });
    };

    // Check if any config is set
    const hasConfig = Boolean(
        scanConfig.sonarqube.projectKey ||
        scanConfig.sonarqube.extraProperties ||
        scanConfig.trivy.trivyYaml
    );

    // Show panel if at least one tool is enabled
    // OR if there is existing config (so user can see/clear it)
    const shouldShow = enabledTools.sonarqube || enabledTools.trivy || hasConfig;

    if (!shouldShow) return null;

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div className="space-y-1">
                    <div className="flex items-center gap-2">
                        <Wrench className="h-4 w-4 text-muted-foreground" />
                        <h3 className="text-lg font-medium">Scan Configuration</h3>
                    </div>
                    <p className="text-sm text-muted-foreground">
                        Configure scanner properties (optional)
                    </p>
                </div>
                {hasConfig && (
                    <Badge variant="secondary" className="text-xs">
                        configured
                    </Badge>
                )}
            </div>

            <div className="space-y-6">
                <Accordion type="multiple" defaultValue={[]}>
                    {/* SonarQube Config */}
                    {enabledTools.sonarqube && (
                        <AccordionItem value="sonarqube">
                            <AccordionTrigger className="hover:no-underline py-2">
                                <div className="flex items-center gap-2">
                                    <BarChart3 className="h-4 w-4 text-blue-600" />
                                    <span className="text-sm">SonarQube Properties</span>
                                </div>
                            </AccordionTrigger>
                            <AccordionContent className="pt-2 space-y-4">
                                <div className="grid gap-3 pl-4">
                                    <div className="grid gap-2">
                                        <Label htmlFor="sonar-project-key" className="text-xs">
                                            Project Key (Optional)
                                        </Label>
                                        <Input
                                            id="sonar-project-key"
                                            placeholder="my-project-key"
                                            value={scanConfig.sonarqube.projectKey || ""}
                                            onChange={(e) =>
                                                updateSonarConfig("projectKey", e.target.value)
                                            }
                                            className="h-8 text-sm"
                                            disabled={disabled}
                                        />
                                        <p className="text-xs text-muted-foreground">
                                            Override auto-generated project key
                                        </p>
                                    </div>
                                    <div className="grid gap-2">
                                        <Label htmlFor="sonar-extra" className="text-xs">
                                            Extra Scanner Properties
                                        </Label>
                                        <Textarea
                                            id="sonar-extra"
                                            placeholder={`sonar.sources=.\nsonar.sourceEncoding=UTF-8`}
                                            value={scanConfig.sonarqube.extraProperties || ""}
                                            onChange={(e) =>
                                                updateSonarConfig("extraProperties", e.target.value)
                                            }
                                            rows={4}
                                            className="font-mono text-xs"
                                            disabled={disabled}
                                        />
                                    </div>
                                </div>
                            </AccordionContent>
                        </AccordionItem>
                    )}

                    {/* Trivy Config */}
                    {enabledTools.trivy && (
                        <AccordionItem value="trivy">
                            <AccordionTrigger className="hover:no-underline py-2">
                                <div className="flex items-center gap-2">
                                    <Shield className="h-4 w-4 text-green-600" />
                                    <span className="text-sm">Trivy Configuration</span>
                                </div>
                            </AccordionTrigger>
                            <AccordionContent className="pt-2 space-y-4">
                                <div className="grid gap-3 pl-4">
                                    <div className="grid gap-2">
                                        <Label htmlFor="trivy-yaml" className="text-xs">
                                            Config File (trivy.yaml)
                                        </Label>
                                        <Textarea
                                            id="trivy-yaml"
                                            placeholder={`timeout: 10m\nformat: json\nseverity:\n  - CRITICAL\n  - HIGH`}
                                            value={scanConfig.trivy.trivyYaml || ""}
                                            onChange={(e) =>
                                                updateTrivyConfig("trivyYaml", e.target.value)
                                            }
                                            rows={8}
                                            className="font-mono text-xs"
                                            disabled={disabled}
                                        />
                                        <p className="text-xs text-muted-foreground">
                                            Paste trivy.yaml content here
                                        </p>
                                    </div>
                                </div>
                            </AccordionContent>
                        </AccordionItem>
                    )}
                </Accordion>

                {/* Per-Repo Overrides */}
                {repos.length > 0 && (enabledTools.sonarqube || enabledTools.trivy) && (
                    <RepoScanOverrideSection
                        repos={repos}
                        scanConfig={scanConfig}
                        onScanConfigChange={onScanConfigChange}
                        disabled={disabled}
                    />
                )}
            </div>
        </div>
    );
}
