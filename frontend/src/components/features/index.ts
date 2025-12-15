/**
 * Shared feature selection components.
 *
 * Usage:
 * import { FeatureDAGVisualization, useFeatureSelector } from "@/components/features";
 * import { GraphView, ListView, SelectedFeaturesPanel } from "@/components/features/FeatureSelection";
 */

// Main DAG visualization
export { FeatureDAGVisualization } from "./FeatureDAGVisualization";

// Types
export type {
    DAGNode,
    DAGEdge,
    ExecutionLevel,
    FeatureDAGData,
    FeatureDefinition,
    NodeInfo,
    FeaturesByNodeResponse,
} from "./types";

// Hook
export { useFeatureSelector } from "./hooks/useFeatureSelector";
export type { UseFeatureSelectorReturn } from "./hooks/useFeatureSelector";
