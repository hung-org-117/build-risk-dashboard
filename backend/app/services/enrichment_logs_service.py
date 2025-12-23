"""
Enrichment Logs Service - Business logic for enrichment log endpoints.

Follows layered architecture: API -> Service -> Repository
"""

import logging
from datetime import datetime
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException
from pymongo.database import Database

from app.dtos.enrichment_logs import (
    AuditLogListResponse,
    FeatureAuditLogResponse,
    NodeExecutionResultResponse,
    PhaseResultResponse,
    PipelineRunResponse,
)
from app.entities.feature_audit_log import FeatureAuditLog
from app.entities.pipeline_run import PipelineRun
from app.repositories.dataset_version import DatasetVersionRepository
from app.repositories.feature_audit_log import FeatureAuditLogRepository
from app.repositories.pipeline_run_repository import PipelineRunRepository

logger = logging.getLogger(__name__)


class EnrichmentLogsService:
    """Service for enrichment logs business logic."""

    def __init__(self, db: Database):
        self._db = db
        self._version_repo = DatasetVersionRepository(db)
        self._pipeline_repo = PipelineRunRepository(db)
        self._audit_repo = FeatureAuditLogRepository(db)

    def _validate_object_id(self, id_value: str, field_name: str) -> ObjectId:
        """Validate and convert string to ObjectId."""
        try:
            return ObjectId(id_value)
        except InvalidId as err:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {field_name} format",
            ) from err

    def _format_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """Format datetime to ISO string."""
        return dt.isoformat() if dt else None

    def _pipeline_run_to_response(self, run: PipelineRun) -> PipelineRunResponse:
        """Convert PipelineRun entity to response DTO."""
        phases = []
        for phase in run.phases:
            phase_dto = PhaseResultResponse(
                phase_name=phase.phase_name,
                status=phase.status,
                started_at=self._format_datetime(phase.started_at),
                completed_at=self._format_datetime(phase.completed_at),
                duration_seconds=phase.duration_seconds,
                total_items=phase.total_items,
                processed_items=phase.processed_items,
                failed_items=phase.failed_items,
                skipped_items=phase.skipped_items,
                errors=phase.errors,
                metadata=phase.metadata,
            )
            phases.append(phase_dto)

        return PipelineRunResponse(
            pipeline_run_id=str(run.id),
            correlation_id=run.correlation_id,
            pipeline_type=run.pipeline_type,
            status=run.status,
            started_at=self._format_datetime(run.started_at),
            completed_at=self._format_datetime(run.completed_at),
            duration_seconds=run.duration_seconds,
            total_builds=run.total_builds,
            processed_builds=run.processed_builds,
            failed_builds=run.failed_builds,
            phases=phases,
            result_summary=run.result_summary,
            error_message=run.error_message,
            triggered_by=run.triggered_by,
        )

    def _audit_log_to_response(self, log: FeatureAuditLog) -> FeatureAuditLogResponse:
        """Convert FeatureAuditLog entity to response DTO."""
        node_results = []
        for node in log.node_results:
            node_dto = NodeExecutionResultResponse(
                node_name=node.node_name,
                status=node.status,
                started_at=self._format_datetime(node.started_at),
                completed_at=self._format_datetime(node.completed_at),
                duration_ms=node.duration_ms,
                features_extracted=node.features_extracted,
                resources_used=node.resources_used,
                resources_missing=node.resources_missing,
                error=node.error,
                warning=node.warning,
                skip_reason=node.skip_reason,
            )
            node_results.append(node_dto)

        return FeatureAuditLogResponse(
            audit_log_id=str(log.id),
            correlation_id=log.correlation_id,
            category=log.category,
            raw_repo_id=str(log.raw_repo_id),
            raw_build_run_id=str(log.raw_build_run_id),
            enrichment_build_id=str(log.enrichment_build_id) if log.enrichment_build_id else None,
            status=log.status,
            started_at=self._format_datetime(log.started_at),
            completed_at=self._format_datetime(log.completed_at),
            duration_ms=log.duration_ms,
            feature_count=log.feature_count,
            features_extracted=log.features_extracted,
            node_results=node_results,
            errors=log.errors,
            warnings=log.warnings,
            nodes_executed=log.nodes_executed,
            nodes_succeeded=log.nodes_succeeded,
            nodes_failed=log.nodes_failed,
            nodes_skipped=log.nodes_skipped,
            total_retries=log.total_retries,
        )

    def get_version_pipeline_run(
        self,
        dataset_id: str,
        version_id: str,
    ) -> Optional[PipelineRunResponse]:
        """
        Get the pipeline run record for a dataset version.

        Args:
            dataset_id: Dataset ID (for validation)
            version_id: Version ID

        Returns:
            Pipeline run response or None if not found
        """
        version_oid = self._validate_object_id(version_id, "version_id")

        # Get version to verify it exists and get correlation_id
        version = self._version_repo.find_by_id(version_oid)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")

        # Find pipeline run by correlation_id
        pipeline_run = self._pipeline_repo.find_by_correlation_id(version.correlation_id)
        if not pipeline_run:
            return None

        return self._pipeline_run_to_response(pipeline_run)

    def get_version_audit_logs(
        self,
        dataset_id: str,
        version_id: str,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
    ) -> AuditLogListResponse:
        """
        Get paginated audit logs for a dataset version.

        Args:
            dataset_id: Dataset ID (for validation)
            version_id: Version ID
            skip: Number of records to skip
            limit: Max records to return
            status: Optional status filter

        Returns:
            Paginated list of audit logs
        """
        version_oid = self._validate_object_id(version_id, "version_id")

        # Get version to get correlation_id
        version = self._version_repo.find_by_id(version_oid)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")

        # Find pipeline run to get correlation_id
        pipeline_run = self._pipeline_repo.find_by_correlation_id(version.correlation_id)
        if not pipeline_run:
            return AuditLogListResponse(items=[], total=0, skip=skip, limit=limit)

        # Query audit logs
        query = {"correlation_id": pipeline_run.correlation_id}
        if status:
            query["status"] = status

        audit_logs, total_count = self._audit_repo.find_with_pagination(
            query=query,
            skip=skip,
            limit=limit,
            sort=[("started_at", -1)],
        )

        items = [self._audit_log_to_response(log) for log in audit_logs]

        return AuditLogListResponse(
            items=items,
            total=total_count,
            skip=skip,
            limit=limit,
        )

    def get_build_audit_log(
        self,
        dataset_id: str,
        version_id: str,
        build_id: str,
    ) -> FeatureAuditLogResponse:
        """
        Get audit log for a specific enrichment build.

        Args:
            dataset_id: Dataset ID (for validation)
            version_id: Version ID (for validation)
            build_id: Enrichment build ID

        Returns:
            Audit log for the build

        Raises:
            HTTPException: If not found
        """
        build_oid = self._validate_object_id(build_id, "build_id")

        # Find audit log by enrichment_build_id
        audit_log = self._audit_repo.find_by_enrichment_build(build_oid)
        if not audit_log:
            raise HTTPException(status_code=404, detail="Audit log not found for build")

        return self._audit_log_to_response(audit_log)
