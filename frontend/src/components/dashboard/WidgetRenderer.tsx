"use client";

/**
 * Widget Renderer - Registry Pattern
 * 
 * Maps widget_id to Component with RBAC guarantees:
 * - Common widgets: Use RBAC-filtered data (repos, builds from accessible_repos)
 * - User widgets: Use filtered data + user-specific features
 * - Admin widgets: Use admin_extras (null for non-admin)
 * 
 * Backend RBAC Filtering:
 * - dashboard_service.py filters repos by github_accessible_repos
 * - build_service.py filters recent builds by accessible repos
 * - admin_extras only populated if user.role === "admin"
 */

import type { WidgetConfig } from "@/types";
import type { BaseWidgetProps, WidgetId } from "./types";
import { Card, CardContent } from "@/components/ui/card";

// Import Common Widgets
import { TotalBuildsWidget } from "./widgets/common/TotalBuildsWidget";
import { SuccessRateWidget } from "./widgets/common/SuccessRateWidget";
import { AvgDurationWidget } from "./widgets/common/AvgDurationWidget";
import { ActiveReposWidget } from "./widgets/common/ActiveReposWidget";
import { RepoDistributionWidget } from "./widgets/common/RepoDistributionWidget";
import { RecentBuildsWidget } from "./widgets/common/RecentBuildsWidget";

// Import User Widgets
import { RiskDistributionWidget } from "./widgets/user/RiskDistributionWidget";
import { RiskTrendWidget } from "./widgets/user/RiskTrendWidget";
import { HighRiskBuildsWidget } from "./widgets/user/HighRiskBuildsWidget";

// Import Admin Widgets
import { ModelPipelineSummaryWidget } from "./widgets/admin/ModelPipelineSummaryWidget";
import { TrainingScenarioSummaryWidget } from "./widgets/admin/TrainingScenarioSummaryWidget";
import { MonitoringSummaryWidget } from "./widgets/admin/MonitoringSummaryWidget";
import { UserActivityWidget } from "./widgets/admin/UserActivityWidget";

/**
 * Widget Registry - Maps widget_id to React Component
 * 
 * All components receive BaseWidgetProps with RBAC-filtered data
 */
const WIDGET_REGISTRY: Record<WidgetId, React.ComponentType<BaseWidgetProps>> = {
  // Common widgets (VIEW_BUILDS, VIEW_REPOS permissions)
  total_builds: TotalBuildsWidget,
  success_rate: SuccessRateWidget,
  avg_duration: AvgDurationWidget,
  active_repos: ActiveReposWidget,
  repo_distribution: RepoDistributionWidget,
  recent_builds: RecentBuildsWidget,

  // User widgets (VIEW_BUILDS, VIEW_OWN_DASHBOARD)
  risk_distribution: RiskDistributionWidget,
  risk_trend: RiskTrendWidget,
  high_risk_builds: HighRiskBuildsWidget,

  // Admin widgets (ADMIN_FULL, VIEW_DATASETS, MANAGE_USERS)
  // These require admin_extras which is null for non-admin users
  model_pipeline_summary: ModelPipelineSummaryWidget,
  training_scenario_summary: TrainingScenarioSummaryWidget,
  monitoring_summary: MonitoringSummaryWidget,
  user_activity: UserActivityWidget,
};

interface WidgetRendererProps extends BaseWidgetProps {
  widget: WidgetConfig;
}

/**
 * Widget Renderer Component
 * 
 * Looks up widget component from registry and renders with filtered data
 * All data in BaseWidgetProps is already RBAC-filtered by backend
 */
export function WidgetRenderer({
  widget,
  summary,
  recentBuilds,
  totalRepositories,
  isEditing,
  router,
  className,
}: WidgetRendererProps) {
  const WidgetComponent = WIDGET_REGISTRY[widget.widget_id as WidgetId];

  if (!WidgetComponent) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center justify-center h-full">
          <p className="text-sm text-muted-foreground truncate">
            Unknown widget: {widget.widget_id}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <WidgetComponent
      summary={summary}
      recentBuilds={recentBuilds}
      totalRepositories={totalRepositories}
      isEditing={isEditing}
      router={router}
      className={className}
    />
  );
}
