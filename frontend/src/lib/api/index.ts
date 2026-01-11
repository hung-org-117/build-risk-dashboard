// Core client and utilities
export { api, ApiError, getApiErrorMessage, getValidationErrors } from './client';

// Domain-specific APIs
export { buildApi } from './builds';
export { dashboardApi } from './dashboard';
export { integrationApi, usersApi } from './auth';
export { reposApi } from './repos';
export { tokensApi } from './tokens';
export { featuresApi, sonarApi } from './features';
export { adminUsersApi, adminReposApi } from './admin';

export { exportApi } from './export';

export { settingsApi, notificationsApi } from './settings';

export { qualityApi, userSettingsApi } from './quality';
export { statisticsApi } from './statistics';
export { trainingScenariosApi } from './training-scenarios';
export { buildSourcesApi } from './build-sources';
export { templatesApi } from './templates';

export type {
    BuildSourceRecord,
    BuildSourceListResponse,
    SourceBuildRecord,
    SourceRepoStatsRecord,
    ValidationStats as SourceValidationStats,
    ValidationStatus as SourceValidationStatus,
    SourceMapping,
} from './build-sources';


export type {
    TrainingScenarioRecord,
    TrainingScenarioStatus,
    TrainingScenarioListResponse,
    TrainingDatasetSplitRecord,
    PreviewBuild,
    PreviewBuildStats,
    PreviewBuildsResponse,
    PreviewBuildsParams,
    CreateTrainingScenarioPayload,
} from './training-scenarios';


export type {
    UserListResponse,
    UserCreatePayload,
    UserUpdatePayload,
    UserRoleUpdatePayload,
    RepoAccessSummary,
    RepoAccessListResponse,
    RepoAccessResponse,
} from './admin';

export type {
    ExportPreviewResponse,
    ExportJobResponse,
    ExportAsyncResponse,
    ExportJobListItem,
} from './export';




export type {
    QualityIssue,
    QualityMetric,
    QualityReport,
    EvaluateQualityResponse,
    UserSettingsResponse,
    UpdateUserSettingsRequest,
} from './quality';

export type {
    VersionStatistics,
    BuildStatusBreakdown,
    FeatureCompleteness,
    VersionStatisticsResponse,
    HistogramBin,
    NumericStats,
    NumericDistribution,
    CategoricalValue,
    CategoricalDistribution,
    FeatureDistributionResponse,
    CorrelationPair,
    CorrelationMatrixResponse,
    MetricSummary,
    TrivySummary,
    SonarSummary,
    ScanSummary,
    ScanMetricsStatisticsResponse,
} from './statistics';

