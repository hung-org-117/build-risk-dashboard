"use client";

import { useEffect, useState } from "react";

import { useFeatureSelector } from "@/components/features";
import { FeatureSelectionStep } from "@/components/features/selection/FeatureSelectionStep";

import { useWizard } from "./WizardContext";

export function StepFeatureSelection() {
    const {
        state,
        updateFeatures,
    } = useWizard();

    // Initialize feature selector with state from wizard context
    const featureSelector = useFeatureSelector(new Set(state.features.dag_features));
    const {
        selectedFeatures,
    } = featureSelector;

    // Scan metrics state
    const [scanMetrics, setScanMetrics] = useState({
        sonarqube: state.features.scan_metrics.sonarqube,
        trivy: state.features.scan_metrics.trivy,
    });

    // Sync state to context continuously
    useEffect(() => {
        updateFeatures({
            dag_features: Array.from(selectedFeatures),
            scan_metrics: scanMetrics,
        });
    }, [selectedFeatures, scanMetrics, updateFeatures]);

    return (
        <FeatureSelectionStep
            featureSelector={featureSelector}
            scanMetrics={scanMetrics}
            onScanMetricsChange={setScanMetrics}
        />
    );
}
