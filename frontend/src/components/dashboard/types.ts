/**
 * Dashboard Widget Types & Interfaces
 * 
 * RBAC Guarantee:
 * - Backend filters data by user's github_accessible_repos
 * - Admin widgets get admin_extras (null for users)
 * - User widgets only use filtered metrics from summary
 */

import type { DashboardSummaryResponse, Build } from "@/types";

/**
 * Base props for all widgets
 * Data is already filtered by backend based on user's role and permissions
 */
export interface BaseWidgetProps {
  /** Dashboard summary with RBAC-filtered data */
  summary: DashboardSummaryResponse;
  /** Recent builds from accessible repos only */
  recentBuilds: Build[];
  /** Total count of accessible repositories */
  totalRepositories: number;
  /** Whether dashboard is in editing mode */
  isEditing: boolean;
  /** Router for navigation */
  router: any;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Widget IDs - categorized by permission level
 */
export type WidgetId =
  // Common widgets (VIEW_BUILDS, VIEW_REPOS permissions)
  | "total_builds"
  | "success_rate"
  | "avg_duration"
  | "active_repos"
  | "repo_distribution"
  | "recent_builds"
  // User widgets (VIEW_BUILDS, VIEW_OWN_DASHBOARD)
  | "risk_distribution"
  | "risk_trend"
  | "high_risk_builds"
  // Admin widgets (ADMIN_FULL, VIEW_DATASETS, MANAGE_USERS)
  | "model_pipeline_summary"
  | "training_scenario_summary"
  | "monitoring_summary"
  | "user_activity";

/**
 * Widget category for documentation and filtering
 */
export type WidgetCategory = "common" | "user" | "admin";

/**
 * Widget metadata for registry
 */
export interface WidgetMetadata {
  id: WidgetId;
  category: WidgetCategory;
  /** Permission required (informational, backend enforces) */
  requiredPermission?: string;
  /** Whether widget requires admin_extras data */
  requiresAdminExtras?: boolean;
}
