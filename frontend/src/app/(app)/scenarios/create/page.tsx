"use client";

import { useRouter } from "next/navigation";
import {
    ArrowRight,
    ArrowLeft,
    Database,
    FileCheck,
    Settings2,
    Loader2,
    Save,
    ChevronLeft,
    Shield,
    LayoutDashboard,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";

import { WizardProvider, useWizard } from "./_components/WizardContext";
import { StepDataSource } from "./_components/StepDataSource";
import { StepFeatureSelection } from "./_components/StepFeatureSelection";
import { StepFeatureConfiguration } from "./_components/StepFeatureConfiguration";
import { trainingScenariosApi } from "@/lib/api/training-scenarios";
import { getApiErrorMessage } from "@/lib/api/client";
import { useState } from "react";

// Step Review Component
function StepReview() {
    const { state, setName, setDescription } = useWizard();
    const [showAllFeatures, setShowAllFeatures] = useState(false);
    const [showAllMetrics, setShowAllMetrics] = useState(false);

    // Stats for review
    const features = state.features.dag_features.slice().sort();
    const totalFeatures = features.length;

    // Scan stats
    const sonarMetrics = state.features.scan_metrics.sonarqube || [];
    const trivyMetrics = state.features.scan_metrics.trivy || [];
    const allMetrics = [
        ...sonarMetrics.map(m => ({ tool: 'SonarQube', name: m })),
        ...trivyMetrics.map(m => ({ tool: 'Trivy', name: m }))
    ];

    const displayFeatures = showAllFeatures ? features : features.slice(0, 20);
    const hasMoreFeatures = features.length > 20;

    return (
        <div className="space-y-6">
            <div className="grid gap-6 md:grid-cols-2">
                {/* Scenario Info */}
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base flex items-center gap-2">
                            Scenario Details
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-4">
                            <div className="grid gap-2">
                                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Name <span className="text-red-500">*</span></span>
                                <Input
                                    value={state.name}
                                    onChange={(e) => setName(e.target.value)}
                                    placeholder="Enter scenario name"
                                    className="font-medium"
                                    required
                                />
                            </div>
                            <div className="grid gap-2">
                                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Description <span className="text-muted-foreground/70 lowercase font-normal">(optional)</span></span>
                                <Textarea
                                    value={state.description}
                                    onChange={(e) => setDescription(e.target.value)}
                                    placeholder="Describe the purpose of this dataset..."
                                    className="resize-none h-24"
                                />
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Data Source Configuration */}
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base flex items-center gap-2">
                            Data Source
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid gap-1">
                            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Scope</span>
                            <div className="flex items-center gap-2">
                                <Badge variant="outline" className="text-sm py-1 px-3">
                                    {state.previewStats?.total_builds.toLocaleString() || 0} Builds
                                </Badge>
                                <span className="text-sm text-muted-foreground">from</span>
                                <Badge variant="outline" className="text-sm py-1 px-3">
                                    {state.previewStats?.total_repos.toLocaleString() || 0} Repositories
                                </Badge>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-x-4 gap-y-4 pt-2 border-t">
                            {/* Environment / Repos */}
                            <div className="grid gap-1">
                                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                    Languages
                                </span>
                                <div className="flex flex-wrap gap-1">
                                    {state.dataSource.languages?.map(lang => (
                                        <Badge key={lang} variant="secondary" className="text-xs capitalize">{lang}</Badge>
                                    ))}
                                    {(!state.dataSource.languages?.length) && <span className="text-sm text-muted-foreground">All Languages</span>}
                                </div>
                            </div>

                            {/* CI Provider */}
                            <div className="grid gap-1">
                                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">CI Provider</span>
                                <div className="text-sm text-muted-foreground">
                                    {state.dataSource.ci_providers.length === 0
                                        ? "All Providers"
                                        : state.dataSource.ci_providers.map(p => p.replace('_', ' ')).join(", ")}
                                </div>
                            </div>

                            {/* Date Range */}
                            <div className="grid gap-1">
                                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Date Range</span>
                                <div className="text-sm">
                                    {state.dataSource.date_start ? (
                                        <span className="font-medium">
                                            {new Date(state.dataSource.date_start).toLocaleDateString()}
                                            {" - "}
                                            {state.dataSource.date_end ? new Date(state.dataSource.date_end).toLocaleDateString() : "Now"}
                                        </span>
                                    ) : (
                                        <span className="text-muted-foreground">All time</span>
                                    )}
                                </div>
                            </div>

                            {/* Conclusions */}
                            <div className="grid gap-1">
                                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Conclusions</span>
                                <div className="flex gap-1 flex-wrap">
                                    {state.dataSource.conclusions.length === 0 ? (
                                        <Badge variant="outline" className="text-muted-foreground">All Outcomes</Badge>
                                    ) : (
                                        state.dataSource.conclusions.map(c => (
                                            <Badge
                                                key={c}
                                                variant="outline"
                                                className={c === 'success' ? "border-green-200 text-green-700 bg-green-50" : "border-red-200 text-red-700 bg-red-50"}
                                            >
                                                {c}
                                            </Badge>
                                        ))
                                    )}
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Features Configuration */}
            <Card className="border-indigo-100 dark:border-indigo-900 overflow-hidden">
                <CardHeader className="pb-3 bg-slate-50/50 dark:bg-slate-900/50 border-b">
                    <CardTitle className="text-base flex items-center gap-2">
                        Features & Metrics
                    </CardTitle>
                    <CardDescription>
                        Configuration for feature extraction and analysis
                    </CardDescription>
                </CardHeader>
                <CardContent className="pt-6 grid md:grid-cols-2 gap-6">
                    {/* DAG Features */}
                    <div className="space-y-3 flex flex-col">
                        <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Extraction Features ({totalFeatures})</span>
                        </div>

                        <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-3 border flex-1 min-h-[100px]">
                            <div className="flex flex-wrap gap-2 max-h-[300px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-200 dark:scrollbar-thumb-slate-700">
                                {features.map(feature => (
                                    <Badge key={feature} variant="secondary" className="font-mono text-xs font-normal">
                                        {feature}
                                    </Badge>
                                ))}
                                {features.length === 0 && (
                                    <span className="text-sm text-muted-foreground italic">No features selected</span>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Scan Metrics */}
                    <div className="space-y-3 flex flex-col">
                        <span className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Scan Metrics ({allMetrics.length})</span>
                        {allMetrics.length > 0 ? (
                            <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-3 border flex-1 min-h-[100px]">
                                <div className="flex flex-wrap gap-2 max-h-[300px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-200 dark:scrollbar-thumb-slate-700">
                                    {allMetrics.map((metric, idx) => (
                                        <Badge
                                            key={`${metric.tool}-${metric.name}-${idx}`}
                                            variant="outline"
                                            className={metric.tool === 'SonarQube' ? "border-blue-200 bg-blue-50 text-blue-700" : "border-cyan-200 bg-cyan-50 text-cyan-700"}
                                        >
                                            <span className="font-semibold mr-1">{metric.tool}:</span>
                                            {metric.name}
                                        </Badge>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <div className="text-sm text-muted-foreground italic flex items-center gap-2 pl-1 h-full items-start pt-3">
                                <Shield className="h-3 w-3" /> No security scan metrics enabled
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

// Step indicator component
function StepIndicator() {
    const { state, setStep } = useWizard();
    const currentStep = state.step;

    const steps = [
        { num: 1, label: "Data Source", icon: Database },
        { num: 2, label: "Selection", icon: LayoutDashboard }, // Changed Icon to LayoutDashboard if available
        { num: 3, label: "Configuration", icon: Settings2 },
        { num: 4, label: "Review", icon: FileCheck },
    ];

    return (
        <div className="flex items-center justify-center gap-2 mb-6">
            {steps.map((step, idx) => {
                const isActive = currentStep === step.num;
                const isCompleted = currentStep > step.num;
                const Icon = step.icon;

                return (
                    <div key={step.num} className="flex items-center">
                        <button
                            onClick={() => isCompleted && setStep(step.num)}
                            disabled={!isCompleted}
                            className={`
                flex items-center gap-2 px-4 py-2 rounded-lg transition-colors
                ${isActive
                                    ? "bg-primary text-primary-foreground"
                                    : isCompleted
                                        ? "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300 cursor-pointer hover:bg-green-200"
                                        : "bg-slate-100 text-slate-400 dark:bg-slate-800 cursor-not-allowed"
                                }
              `}
                        >
                            <Icon className="h-4 w-4" />
                            <span className="text-sm font-medium hidden sm:inline">{step.label}</span>
                        </button>
                        {idx < steps.length - 1 && (
                            <div
                                className={`w-8 h-0.5 mx-1 ${currentStep > step.num ? "bg-green-500" : "bg-slate-300"
                                    }`}
                            />
                        )}
                    </div>
                );
            })}
        </div>
    );
}

function WizardContent() {
    const { state, setStep, setIsSubmitting } = useWizard();
    const router = useRouter();
    const { toast } = useToast();

    const handleCreate = async () => {
        setIsSubmitting(true);
        try {
            const payload = {
                name: state.name,
                description: state.description,
                data_source_config: {
                    languages: state.dataSource.languages,
                    build_source_ids: state.dataSource.build_source_ids,
                    date_start: state.dataSource.date_start || undefined,
                    date_end: state.dataSource.date_end || undefined,
                    conclusions: state.dataSource.conclusions,
                    ci_providers: state.dataSource.ci_providers,
                },
                feature_config: {
                    dag_features: state.features.dag_features,
                    scan_metrics: state.features.scan_metrics,
                    scan_tool_config: state.scanConfigs,
                    extractor_configs: {
                        global: state.featureConfigs.global || {},
                        repos: state.featureConfigs.repos || {},
                    },
                },
            };

            const scenario = await trainingScenariosApi.create(payload);

            toast({
                title: "Scenario created",
                description: "Starting ingestion process...",
            });

            await trainingScenariosApi.startIngestion(scenario.id);
            router.push(`/scenarios/${scenario.id}`);
        } catch (error) {
            console.error("Failed to create scenario", error);
            const message = getApiErrorMessage(error);
            toast({
                title: "Creation failed",
                description: message || "Failed to create scenario. Please try again.",
                variant: "destructive",
            });
        } finally {
            setIsSubmitting(false);
        }
    };

    // Derived state for button handling
    const canGoNext = () => {
        if (state.step === 1) {
            return state.previewStats && state.previewStats.total_builds > 0 && !state.isPreviewLoading;
        }
        if (state.step === 2) {
            // Selection Step
            const hasFeatures = state.features.dag_features.length > 0;
            const hasScans = state.features.scan_metrics.sonarqube.length > 0 || state.features.scan_metrics.trivy.length > 0;
            return hasFeatures || hasScans;
        }
        if (state.step === 3) {
            // Configuration Step - always valid to proceed
            return true;
        }
        if (state.step === 4) {
            // Review Step
            return !!state.name && state.name.trim().length > 0;
        }
        return false;
    };

    const handleNextAction = () => {
        if (!canGoNext()) return;
        if (state.step < 4) {
            setStep(state.step + 1);
        } else {
            handleCreate();
        }
    };

    return (
        <div className="flex flex-col h-[calc(100vh-64px)] overflow-hidden">
            {/* Header Area */}
            <div className="flex-shrink-0 px-6 py-4 border-b bg-background z-10">
                <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                    <div className="space-y-1">
                        <div className="flex items-center gap-2">
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => router.push("/scenarios")}
                                className="gap-2 px-0 hover:bg-transparent -ml-2"
                            >
                                <ChevronLeft className="h-4 w-4" />
                                Back to Datasets
                            </Button>
                        </div>

                        <div>
                            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Create Dataset Version</h1>
                            <p className="text-sm text-muted-foreground">
                                Configure filters and features for your dataset.
                            </p>
                        </div>
                    </div>

                    {/* Primary Action Button */}
                    <div className="flex items-center gap-3 pt-4 md:pt-0">
                        {state.step > 1 && (
                            <Button
                                variant="outline"
                                onClick={() => setStep(state.step - 1)}
                                disabled={state.isSubmitting}
                            >
                                <ArrowLeft className="h-4 w-4 mr-2" />
                                Back
                            </Button>
                        )}
                        <Button
                            onClick={handleNextAction}
                            disabled={!canGoNext() || state.isSubmitting}
                            className="bg-green-600 hover:bg-green-700 text-white"
                        >
                            {state.isSubmitting ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Processing...
                                </>
                            ) : state.step === 4 ? (
                                <>
                                    Start
                                </>
                            ) : (
                                <>
                                    Next: {["", "Selection", "Configuration", "Review"][state.step]}
                                    <ArrowRight className="ml-2 h-4 w-4" />
                                </>
                            )}
                        </Button>
                    </div>
                </div>
            </div>

            {/* Step Indicator - Fixed top below header */}
            <div className="flex-shrink-0 pt-4 pb-2 bg-slate-50/50 dark:bg-slate-900/50 border-b">
                <StepIndicator />
            </div>

            {/* Step Content - Scrollable Area */}
            <div className="flex-1 overflow-hidden relative bg-slate-50/30 dark:bg-slate-950/30 p-4 md:p-6">
                <div className="h-full w-full max-w-[1600px] mx-auto">
                    {state.step === 1 && <StepDataSource />}
                    {state.step === 2 && <StepFeatureSelection />}
                    {state.step === 3 && <StepFeatureConfiguration />}
                    {state.step === 4 && <StepReview />}
                </div>
            </div>
        </div>
    );
}

export default function CreateScenarioPage() {
    return (
        <WizardProvider>
            <WizardContent />
        </WizardProvider>
    );
}
