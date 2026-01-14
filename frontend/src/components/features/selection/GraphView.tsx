"use client";

import { memo } from "react";
import {
    FeatureDAGVisualization,
    type FeatureDAGData,
} from "@/components/features";

interface GraphViewProps {
    dagData: FeatureDAGData | null;
    selectedFeatures: Set<string>;
    onFeaturesChange: (features: string[]) => void;
    isLoading?: boolean;
}

export const GraphView = memo(function GraphView({
    dagData,
    selectedFeatures,
    onFeaturesChange,
    isLoading = false,
}: GraphViewProps) {
    // Convert Set to array for the DAG component
    const selectedArray = Array.from(selectedFeatures);

    return (
        <div className="h-full flex flex-col relative">
            <FeatureDAGVisualization
                dagData={dagData}
                selectedFeatures={selectedArray}
                onFeaturesChange={onFeaturesChange}
                isLoading={isLoading}
                className="flex-1"
            />
            <p className="absolute bottom-2 left-0 right-0 text-center text-xs text-muted-foreground pointer-events-none">
                💡 Click on an extractor node to select/deselect all its features.
                Drag to pan, scroll to zoom.
            </p>
        </div>
    );
});
