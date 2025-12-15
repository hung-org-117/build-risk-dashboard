/**
 * Shared types for feature selection components.
 */

// DAG Types
export interface DAGNode {
    id: string;
    type: "extractor" | "resource";
    label: string;
    features: string[];
    feature_count: number;
    requires_resources: string[];
    requires_features: string[];
    level: number;
}

export interface DAGEdge {
    id: string;
    source: string;
    target: string;
    type: "feature_dependency" | "resource_dependency";
}

export interface ExecutionLevel {
    level: number;
    nodes: string[];
}

export interface FeatureDAGData {
    nodes: DAGNode[];
    edges: DAGEdge[];
    execution_levels: ExecutionLevel[];
    total_features: number;
    total_nodes: number;
}

// Feature Definition Types
export interface FeatureDefinition {
    name: string;
    display_name: string;
    description: string;
    data_type: string;
    is_active: boolean;
    depends_on_features: string[];
    depends_on_resources: string[];
    node: string;
}

export interface NodeInfo {
    name: string;
    display_name: string;
    description: string;
    group: string;
    is_configured: boolean;
    requires_resources: string[];
    features: FeatureDefinition[];
    feature_count: number;
}

export interface FeaturesByNodeResponse {
    nodes: Record<string, NodeInfo>;
}
