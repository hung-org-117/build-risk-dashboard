"use client";

import { useEffect, useMemo, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FeatureConfigForm, type FeatureConfigsData } from "@/components/features/config/FeatureConfigForm";
import { useWizard } from "./WizardContext";

import { useRepoLanguages } from "@/hooks/use-repo-languages";

export function StepFeatureConfiguration() {
    const {
        state,
        setFeatureConfigs: setFeatureConfigsContext,
    } = useWizard();
    const { previewRepos, features } = state;
    const selectedFeatures = useMemo(
        () => new Set(features.dag_features),
        [features.dag_features]
    );

    // Feature configs local state
    const [featureConfigs, setFeatureConfigs] = useState<FeatureConfigsData>(
        Object.keys(state.featureConfigs).length > 0
            ? state.featureConfigs as FeatureConfigsData
            : { global: {}, repos: {} }
    );

    // Fetch repo languages for feature config
    const repoLangInput = useMemo(() => previewRepos?.map(r => ({
        id: r.id,
        full_name: r.full_name,
    })) || [], [previewRepos]);

    // Note: Since this component is only rendered in Configuration step, 
    // we don't need a conditional 'enabled' flag anymore.
    const { repoLanguages } = useRepoLanguages(repoLangInput);

    // Sync state to context continuously
    useEffect(() => {
        setFeatureConfigsContext(featureConfigs);
    }, [featureConfigs, setFeatureConfigsContext]);

    return (
        <div className="h-full flex flex-col overflow-hidden">
            {/* Content Area */}
            <div className="flex-1 border rounded-lg overflow-hidden bg-background shadow-sm">
                <div className="flex h-full overflow-hidden">
                    {/* Config Sidebar/Tabs */}
                    <Tabs defaultValue="features" className="flex-1 flex flex-col overflow-hidden">
                        <div className="flex-shrink-0 px-6 pt-4 border-b bg-slate-50/50 dark:bg-slate-900/50">
                            <TabsList className="bg-transparent p-0 h-auto gap-6 -mb-px">
                                <TabsTrigger
                                    value="features"
                                    disabled={selectedFeatures.size === 0}
                                    className="rounded-none border-b-2 border-transparent data-[state=active]:border-purple-600 data-[state=active]:bg-transparent pb-3"
                                >
                                    Feature Config
                                </TabsTrigger>
                            </TabsList>
                        </div>

                        <div className="flex-1 overflow-y-auto p-6 bg-slate-50/30 dark:bg-slate-950/30">
                            <div className="max-w-4xl mx-auto space-y-6">
                                <TabsContent value="features" className="m-0">
                                    <FeatureConfigForm
                                        selectedFeatures={selectedFeatures}
                                        value={featureConfigs}
                                        onChange={setFeatureConfigs}
                                        repos={previewRepos}
                                        repoLanguages={repoLanguages}
                                        showValidationStatusColumn={false}
                                    />
                                </TabsContent>
                            </div>
                        </div>
                    </Tabs>
                </div>
            </div>
        </div>
    );
}
