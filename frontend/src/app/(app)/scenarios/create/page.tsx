"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
    ArrowRight,
    ArrowLeft,
    Check,
    ChevronLeft,
    Database,
    FileCheck,
    Layers,
    Settings2,
    Loader2,
    Save,
} from "lucide-react";

import { Button } from "@/components/ui/button";
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
import { StepFeatures } from "./_components/StepFeatures";
import { StepSplitting } from "./_components/StepSplitting";
import { trainingScenariosApi } from "@/lib/api/training-scenarios";

// Step Review Component
function StepReview() {
    const { state, setStep } = useWizard();

    // Stats for review
    const totalFeatures = state.features.dag_features.length;
    const scansEnabled = [
        state.features.scan_metrics.sonarqube?.length ? "SonarQube" : null,
        state.features.scan_metrics.trivy?.length ? "Trivy" : null
    ].filter(Boolean);

    return (
        <Card>
            <CardHeader>
                <CardTitle>Review & Start</CardTitle>
                <CardDescription>Review your configuration and start processing</CardDescription>
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
                        {totalFeatures} feature groups selected
                    </p>
                    <div className="mt-2 text-xs text-muted-foreground">
                        {scansEnabled.length > 0 && (
                            <div>Scans enabled: {scansEnabled.join(", ")}</div>
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

function WizardContent() {
    const { state, loadFromYaml, setStep, setIsSubmitting } = useWizard();
    const router = useRouter();
    const { toast } = useToast();
    const [importChecked, setImportChecked] = useState(false);

    // Check for drafted import from YAML page
    useEffect(() => {
        if (importChecked) return;

        try {
            const draft = localStorage.getItem("scenario_import_draft");
            if (draft) {
                const parsed = JSON.parse(draft);
                loadFromYaml(parsed);
                localStorage.removeItem("scenario_import_draft");
                toast({
                    title: "Configuration Loaded",
                    description: "Your scenario configuration has been imported.",
                });
            }
        } catch (e) {
            console.error("Failed to load draft", e);
        } finally {
            setImportChecked(true);
        }
    }, [importChecked, loadFromYaml, toast]);


    const handleCreate = async () => {
        setIsSubmitting(true);
        try {
            const payload = {
                name: state.name || `Scenario ${new Date().toISOString().split('T')[0]}`,
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
                    scan_tool_config: state.scanConfigs,
                    extractor_configs: state.featureConfigs.global,
                },
                splitting_config: {
                    strategy: state.splitting.strategy,
                    group_by: state.splitting.group_by,
                    groups: state.splitting.groups,
                    ratios: state.splitting.ratios,
                    stratify_by: state.splitting.stratify_by,
                    temporal_ordering: state.splitting.temporal_ordering,
                    test_groups: state.splitting.test_groups,
                    val_groups: state.splitting.val_groups,
                    train_groups: state.splitting.train_groups,
                    reduce_label: state.splitting.reduce_label,
                    reduce_ratio: state.splitting.reduce_ratio,
                    novelty_group: state.splitting.novelty_group,
                    novelty_label: state.splitting.novelty_label,
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
            toast({
                title: "Creation failed",
                description: "Failed to create scenario. Please try again.",
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
            // Check if any feature or scanner is selected
            const hasFeatures = state.features.dag_features.length > 0;
            const hasScans = state.features.scan_metrics.sonarqube.length > 0 || state.features.scan_metrics.trivy.length > 0;
            // Also checking if generic "scan enabled" state is available isn't easy without local state, 
            // but StepFeatures syncs scan_metrics if selected. 
            // If user just enabled toggle but selected no metrics, scan_metrics is empty.
            // Assumption: User must select actual metrics or features.
            return hasFeatures || hasScans;
        }
        return true; // Step 3 always valid for now
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
        <div className="flex flex-col h-[calc(100vh-4rem)] overflow-hidden">
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
                                Configure filters, features, and splitting strategy for your dataset.
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
                            className={state.step === 4 ? "bg-green-600 hover:bg-green-700" : ""}
                        >
                            {state.isSubmitting ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Processing...
                                </>
                            ) : state.step === 4 ? (
                                <>
                                    Start Ingestion
                                    <Save className="ml-2 h-4 w-4" />
                                </>
                            ) : (
                                <>
                                    Next: {["", "Features", "Splitting", "Review"][state.step]}
                                    <ArrowRight className="ml-2 h-4 w-4" />
                                </>
                            )}
                        </Button>
                    </div>
                </div>

                {state.step === 1 && (
                    <div className="mt-2 text-xs text-purple-600 hover:text-purple-700 dark:text-purple-400 dark:hover:text-purple-300">
                        <span className="text-muted-foreground">Have a configuration file? </span>
                        <a href="/scenarios/create/import-yaml" className="font-medium underline underline-offset-4">
                            Import from YAML
                        </a>
                    </div>
                )}
            </div>

            {/* Step Indicator - Fixed top below header */}
            <div className="flex-shrink-0 pt-4 pb-2 bg-slate-50/50 dark:bg-slate-900/50 border-b">
                <StepIndicator />
            </div>

            {/* Step Content - Scrollable Area */}
            <div className="flex-1 overflow-hidden relative bg-slate-50/30 dark:bg-slate-950/30 p-4 md:p-6">
                <div className="h-full w-full max-w-[1600px] mx-auto">
                    {state.step === 1 && <StepDataSource />}
                    {state.step === 2 && <StepFeatures />}
                    {state.step === 3 && <StepSplitting />}
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
