"use client";

import { useRouter } from "next/navigation";
import {
    ChevronLeft,
    Database,
    FileCheck,
    Layers,
    Settings2,
    Loader2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";

import { WizardProvider, useWizard } from "./_components/WizardContext";
import { StepDataSource } from "./_components/StepDataSource";
import { StepFeatures } from "./_components/StepFeatures";
import { StepSplitting } from "./_components/StepSplitting";





import { trainingScenariosApi } from "@/lib/api/training-scenarios";
import { useToast } from "@/components/ui/use-toast";

function StepReview() {
    const { state, setStep, setIsSubmitting } = useWizard();
    const router = useRouter();
    const { toast } = useToast();

    const handleStart = async () => {
        setIsSubmitting(true);
        try {
            // Map wizard state to payload
            const payload = {
                name: state.name || "Untitled Scenario", // Should be set in Step 1 or global
                description: state.description,
                data_source_config: {
                    filter_by: state.dataSource.filter_by,
                    languages: state.dataSource.languages,
                    repo_names: state.dataSource.repo_names,
                    date_start: state.dataSource.date_start || undefined,
                    date_end: state.dataSource.date_end || undefined,
                    conclusions: state.dataSource.conclusions,
                    ci_provider: state.dataSource.ci_provider,
                },
                feature_config: {
                    dag_features: state.features.dag_features,
                    scan_metrics: state.features.scan_metrics,
                    exclude: state.features.exclude,
                    // Detailed configs from context
                    scan_tool_config: state.scanConfigs,
                    // featureConfigs structure: { global: {}, repos: {} } 
                    // API expects extractor_configs (global?) and maybe something else for repos? 
                    // Assuming featureConfigs.global maps to extractor_configs 
                    extractor_configs: state.featureConfigs.global,
                },
                splitting_config: {
                    strategy: state.splitting.strategy,
                    group_by: state.splitting.group_by,
                    groups: state.splitting.groups,
                    ratios: state.splitting.ratios,
                    stratify_by: state.splitting.stratify_by,
                },
            };

            const scenario = await trainingScenariosApi.create(payload);

            toast({
                title: "Scenario created",
                description: "Starting ingestion process...",
            });

            // Start ingestion immediately? Or just redirect?
            // Usually we start it.
            await trainingScenariosApi.startIngestion(scenario.id);

            router.push(`/training-scenarios/${scenario.id}`);
        } catch (error) {
            console.error("Failed to create scenario", error);
            toast({
                title: "Creation failed",
                description: "Failed to create scenario. Please try again.",
                variant: "destructive",
            });
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle>Review & Start</CardTitle>
                <CardDescription>Review your configuration and start the scenario</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="rounded-lg border p-4">
                    <h4 className="font-medium mb-2">Scenario Details</h4>
                    <p className="text-sm text-muted-foreground">
                        <span className="font-medium">Name:</span> {state.name || "Untitled"}<br />
                        <span className="font-medium">Description:</span> {state.description || "None"}
                    </p>
                </div>

                <div className="rounded-lg border p-4">
                    <h4 className="font-medium mb-2">Data Source</h4>
                    <p className="text-sm text-muted-foreground">
                        {state.previewStats?.total_builds.toLocaleString() || 0} builds from{" "}
                        {state.previewStats?.total_repos.toLocaleString() || 0} repositories
                    </p>
                    <div className="mt-2 text-xs text-muted-foreground">
                        {state.dataSource.languages?.length ? (
                            <div>Languages: {state.dataSource.languages.join(", ")}</div>
                        ) : null}
                    </div>
                </div>
                <div className="rounded-lg border p-4">
                    <h4 className="font-medium mb-2">Features</h4>
                    <p className="text-sm text-muted-foreground">
                        {state.features.dag_features.length} feature groups selected
                    </p>
                    <div className="mt-2 text-xs text-muted-foreground">
                        {(state.features.scan_metrics.sonarqube?.length > 0 || state.features.scan_metrics.trivy?.length > 0) && (
                            <div>Scans enabled: {[
                                state.features.scan_metrics.sonarqube?.length ? "SonarQube" : null,
                                state.features.scan_metrics.trivy?.length ? "Trivy" : null
                            ].filter(Boolean).join(", ")}</div>
                        )}
                    </div>
                </div>
                <div className="rounded-lg border p-4">
                    <h4 className="font-medium mb-2">Splitting</h4>
                    <p className="text-sm text-muted-foreground">
                        Strategy: {state.splitting.strategy?.replace(/_/g, " ")}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                        Train: {(state.splitting.ratios.train * 100).toFixed(0)}% |
                        Val: {(state.splitting.ratios.val * 100).toFixed(0)}% |
                        Test: {(state.splitting.ratios.test * 100).toFixed(0)}%
                    </p>
                </div>
                <div className="flex justify-between pt-4">
                    <Button variant="outline" onClick={() => setStep(3)} disabled={state.isSubmitting}>
                        Back
                    </Button>
                    <Button
                        onClick={handleStart}
                        className="bg-green-600 hover:bg-green-700"
                        disabled={state.isSubmitting}
                    >
                        {state.isSubmitting ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Creating...
                            </>
                        ) : (
                            "Start Ingestion"
                        )}
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}

// Step indicator component
function StepIndicator() {
    const { state, setStep } = useWizard();
    const currentStep = state.step;

    const steps = [
        { num: 1, label: "Data Source", icon: Database },
        { num: 2, label: "Features", icon: Settings2 },
        { num: 3, label: "Splitting", icon: Layers },
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

// Main wizard content
function WizardContent() {
    const { state } = useWizard();
    const router = useRouter();

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => router.push("/scenarios")}
                    className="gap-2"
                >
                    <ChevronLeft className="h-4 w-4" />
                    Back to Scenarios
                </Button>
            </div>

            <div>
                <h1 className="text-2xl font-bold">Create Training Scenario</h1>
                <p className="text-muted-foreground">
                    Configure a new training dataset scenario with filters, features, and splitting strategy.
                </p>
            </div>

            {/* Step Indicator */}
            <StepIndicator />

            {/* Step Content */}
            {state.step === 1 && <StepDataSource />}
            {state.step === 2 && <StepFeatures />}
            {state.step === 3 && <StepSplitting />}
            {state.step === 4 && <StepReview />}
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
