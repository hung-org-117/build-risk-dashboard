export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

export interface Build {
  id: number
  repository: string
  branch: string
  commit_sha: string
  build_number: string
  workflow_name?: string
  status: string
  conclusion?: string
  started_at?: string
  completed_at?: string
  duration_seconds?: number
  author_name?: string
  author_email?: string
  url?: string
  logs_url?: string
  created_at: string
  updated_at?: string
  sonarqube_result?: SonarQubeResult
  risk_assessment?: RiskAssessment
}

export interface SonarQubeResult {
  id: number
  build_id: number
  bugs: number
  vulnerabilities: number
  code_smells: number
  coverage: number
  duplicated_lines_density: number
  technical_debt_minutes: number
  quality_gate_status?: string
  analyzed_at: string
}

export interface RiskAssessment {
  build_id: number
  risk_score: number
  uncertainty: number
  risk_level: RiskLevel
  calculated_at: string
  model_version?: string
}

export interface RiskDriver {
  key: string
  label: string
  impact: 'increase' | 'decrease'
  contribution: number
  description: string
  metrics: Record<string, string | number>
}

export interface RiskExplanation {
  build_id: number
  risk_score: number
  uncertainty: number
  risk_level: RiskLevel
  summary: string
  confidence: string
  model_version?: string | null
  updated_at: string
  drivers: RiskDriver[]
  feature_breakdown: Record<string, number>
  recommended_actions: string[]
}

export interface BuildDetail extends Build {
  // extends base with related analytics
}

export interface BuildListResponse {
  total: number
  skip: number
  limit: number
  builds: BuildDetail[]
}

export interface DashboardMetrics {
  total_builds: number
  average_risk_score: number
  success_rate: number
  average_duration_minutes: number
  risk_distribution: Record<RiskLevel, number>
}

export interface DashboardTrendPoint {
  date: string
  builds: number
  risk_score: number
  failures: number
}

export interface RepoDistributionEntry {
  repository: string
  builds: number
  highRisk: number
}

export interface RiskHeatmapRow {
  day: string
  low: number
  medium: number
  high: number
  critical: number
}

export interface HighRiskBuild {
  id: number
  repository: string
  branch: string
  workflow_name?: string
  risk_level: RiskLevel
  risk_score: number
  conclusion?: string
  started_at?: string
  completed_at?: string
}

export interface DashboardSummaryResponse {
  metrics: DashboardMetrics
  trends: DashboardTrendPoint[]
  repo_distribution: RepoDistributionEntry[]
  risk_heatmap: RiskHeatmapRow[]
  high_risk_builds: HighRiskBuild[]
}

export interface GithubIntegrationRepository {
  name: string
  lastSync: string | null
  buildCount: number
  highRiskCount: number
  status: 'healthy' | 'degraded' | 'attention'
}

export interface GithubIntegrationStatus {
  connected: boolean
  organization?: string | null
  connectedAt?: string | null
  scopes: string[]
  repositories: GithubIntegrationRepository[]
  lastSyncStatus: 'success' | 'warning' | 'error'
  lastSyncMessage?: string | null
  accountLogin?: string
  accountName?: string
  accountAvatarUrl?: string
}

export interface GithubAuthorizeResponse {
  authorize_url: string
  state: string
}

export interface PipelineStage {
  key: string
  label: string
  status: 'pending' | 'running' | 'completed' | 'blocked'
  percent_complete: number
  duration_seconds?: number
  items_processed?: number
  started_at?: string
  completed_at?: string
  notes?: string
  issues: string[]
}

export interface PipelineStatus {
  last_run: string
  next_run: string
  normalized_features: number
  pending_repositories: number
  anomalies_detected: number
  stages: PipelineStage[]
}

export interface GithubImportJob {
  id: string
  repository: string
  branch: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  builds_imported: number
  commits_analyzed: number
  tests_collected: number
  initiated_by: string
  created_at: string
  started_at?: string
  completed_at?: string
  last_error?: string
  notes?: string
}

export interface SystemSettings {
  model_version: string
  risk_threshold_high: number
  risk_threshold_medium: number
  uncertainty_threshold: number
  auto_rescan_enabled: boolean
  updated_at: string
  updated_by: string
}

export interface SystemSettingsUpdateRequest {
  model_version?: string
  risk_threshold_high?: number
  risk_threshold_medium?: number
  uncertainty_threshold?: number
  auto_rescan_enabled?: boolean
  updated_by?: string
}

export interface ActivityLogEntry {
  _id: string
  action: string
  actor: string
  scope: string
  message: string
  created_at: string
  metadata: Record<string, string>
}

export interface ActivityLogListResponse {
  logs: ActivityLogEntry[]
}

export interface NotificationPolicy {
  risk_threshold_high: number
  uncertainty_threshold: number
  channels: string[]
  muted_repositories: string[]
  last_updated_at: string
  last_updated_by: string
}

export interface NotificationItem {
  _id: string
  build_id: number
  repository: string
  branch: string
  risk_level: RiskLevel
  risk_score: number
  uncertainty: number
  status: 'new' | 'sent' | 'acknowledged'
  created_at: string
  message: string
}

export interface NotificationListResponse {
  notifications: NotificationItem[]
}

export interface NotificationPolicyUpdateRequest {
  risk_threshold_high?: number
  uncertainty_threshold?: number
  channels?: string[]
  muted_repositories?: string[]
  updated_by: string
}

export interface UserRoleDefinition {
  role: string
  description: string
  permissions: string[]
  admin_only: boolean
}

export interface RoleListResponse {
  roles: UserRoleDefinition[]
}
