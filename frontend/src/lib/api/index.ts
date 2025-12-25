/**
 * Unified API module - Re-exports all API clients from their respective modules.
 * 
 * Usage:
 *   import { buildApi, reposApi, ... } from '@/lib/api';
 * 
 * Or import specific modules:
 *   import { buildApi } from '@/lib/api/builds';
 */

// Core client and utilities
export { api, ApiError, getApiErrorMessage, getValidationErrors } from './client';

// Domain-specific APIs
export { buildApi } from './builds';
export { dashboardApi } from './dashboard';
export { integrationApi, usersApi } from './auth';
export { reposApi } from './repos';
export { datasetsApi } from './datasets';
export { tokensApi } from './tokens';
export { featuresApi, sonarApi } from './features';
export { adminUsersApi, adminInvitationsApi, adminReposApi } from './admin';
export { enrichmentApi } from './enrichment';
export { exportApi } from './export';
export { datasetValidationApi } from './validation';
export { settingsApi, notificationsApi } from './settings';
export { datasetScanApi, datasetVersionApi } from './versions';
export { qualityApi, userSettingsApi } from './quality';
export { statisticsApi, enrichmentLogsApi } from './statistics';
export { comparisonApi } from './comparison';

// Re-export types from admin
export type {
    UserListResponse,
    UserCreatePayload,
    UserUpdatePayload,
    UserRoleUpdatePayload,
    Invitation,
    InvitationListResponse,
    InvitationCreatePayload,
    RepoAccessSummary,
    RepoAccessListResponse,
    RepoAccessResponse,
} from './admin';

// Re-export types from export
export type {
    ExportPreviewResponse,
    ExportJobResponse,
    ExportAsyncResponse,
    ExportJobListItem,
} from './export';

// Re-export types from versions
export type {
    ScanResultItem,
    ScanResultsResponse,
    ScanSummaryResponse,
    EnrichedBuildData,
    VersionDataResponse,
} from './versions';

// Re-export types from quality
export type {
    QualityIssue,
    QualityMetric,
    QualityReport,
    EvaluateQualityResponse,
    UserSettingsResponse,
    UpdateUserSettingsRequest,
} from './quality';

// Re-export types from statistics
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
    NodeExecutionResult,
    FeatureAuditLogDto,
    AuditLogListResponse,
} from './statistics';

// Re-export types from comparison
export type {
    ComparableVersion,
    ComparableDataset,
    CompareInternalRequest,
    VersionSummary,
    ExternalDatasetSummary,
    FeatureComparison,
    QualityComparison,
    RowOverlap,
    CompareResponse,
    CompareExternalResponse,
} from './comparison';
