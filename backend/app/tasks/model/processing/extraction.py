"""
Model Processing Extraction Task.

Single build feature extraction:
- process_workflow_run: Extract features for a single build
"""

import logging
from datetime import datetime
from typing import Any, Dict

from bson import ObjectId

from app.celery_app import celery_app
from app.entities.enums import ExtractionStatus
from app.entities.feature_audit_log import AuditLogCategory
from app.repositories.model_repo_config import ModelRepoConfigRepository
from app.repositories.model_training_build import ModelTrainingBuildRepository
from app.repositories.raw_build_run import RawBuildRunRepository
from app.repositories.raw_repository import RawRepositoryRepository
from app.tasks.base import TaskState
from app.tasks.model.processing.base import ModelProcessingTask
from app.tasks.shared import extract_features_for_build
from app.tasks.shared.events import publish_model_processing_updated

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=ModelProcessingTask,
    name="app.tasks.model_processing.process_workflow_run",
    queue="model_processing",
    soft_time_limit=600,
    time_limit=900,
)
def process_workflow_run(
    self: ModelProcessingTask,
    repo_config_id: str,
    model_build_id: str,
    is_reprocess: bool = False,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """Process a single build for feature extraction."""
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""

    model_build_repo = ModelTrainingBuildRepository(self.db)
    repo_config_repo = ModelRepoConfigRepository(self.db)
    raw_build_run_repo = RawBuildRunRepository(self.db)
    raw_repo_repo = RawRepositoryRepository(self.db)

    # Pre-validation
    model_build = model_build_repo.find_one(
        {
            "_id": ObjectId(model_build_id),
            "extraction_status": ExtractionStatus.PENDING.value,
        }
    )
    if not model_build:
        logger.info(f"{corr_prefix} ModelTrainingBuild {model_build_id} not PENDING, skipping")
        return {"status": "skipped", "message": "Not pending or not found"}

    raw_build_run = raw_build_run_repo.find_by_id(model_build.raw_build_run_id)
    if not raw_build_run:
        model_build_repo.update_one(
            model_build_id,
            {
                "extraction_status": ExtractionStatus.FAILED.value,
                "extraction_error": "RawBuildRun not found",
            },
        )
        return {"status": "error", "message": "RawBuildRun not found"}

    repo_config = repo_config_repo.find_by_id(repo_config_id)
    if not repo_config:
        return {"status": "error", "message": "Repository Config not found"}

    raw_repo = raw_repo_repo.find_by_id(repo_config.raw_repo_id)
    if not raw_repo:
        return {"status": "error", "message": "RawRepository not found"}

    build_id = str(model_build.id)

    def _mark_failed(exc: Exception) -> None:
        model_build_repo.update_one(
            build_id,
            {
                "extraction_status": ExtractionStatus.FAILED.value,
                "extraction_error": str(exc),
            },
        )
        if not is_reprocess:
            repo_config_repo.increment_builds_processing_failed(ObjectId(repo_config_id))

    def _work(state: TaskState) -> Dict[str, Any]:
        if state.phase == "START":
            from app.services.dataset_template_service import DatasetTemplateService

            if getattr(repo_config, "dag_features", None):
                combined_features = repo_config.dag_features
            else:
                template_service = DatasetTemplateService(self.db)
                template = template_service.get_template_by_name("Risk Prediction")
                combined_features = template.combined_feature_names

            state.meta["feature_names"] = combined_features

            model_build_repo.update_one(
                build_id, {"extraction_status": ExtractionStatus.IN_PROGRESS.value}
            )
            publish_model_processing_updated(
                repo_id=repo_config_id,
                build_id=build_id,
                extraction_status=ExtractionStatus.IN_PROGRESS.value,
                expected_feature_count=len(combined_features),
                ci_run_id=raw_build_run.ci_run_id,
                commit_sha=raw_build_run.commit_sha,
            )
            state.phase = "EXTRACTING"

        if state.phase == "EXTRACTING":
            feature_names = state.meta.get("feature_names", [])
            if not feature_names:
                if getattr(repo_config, "dag_features", None):
                    feature_names = repo_config.dag_features
                else:
                    from app.services.dataset_template_service import (
                        DatasetTemplateService,
                    )

                    template_service = DatasetTemplateService(self.db)
                    template = template_service.get_template_by_name("Risk Prediction")
                    feature_names = template.combined_feature_names

            result = extract_features_for_build(
                db=self.db,
                raw_repo=raw_repo,
                feature_config=repo_config.feature_configs,
                raw_build_run=raw_build_run,
                selected_features=feature_names,
                category=AuditLogCategory.MODEL_TRAINING,
                model_repo_config_id=repo_config_id,
                output_build_id=build_id,
            )
            state.meta["result"] = result
            state.phase = "DONE"

        result = state.meta.get("result", {"status": "failed"})
        updates = {"feature_vector_id": result.get("feature_vector_id")}

        if result["status"] == "completed":
            updates["extraction_status"] = ExtractionStatus.COMPLETED.value
            updates["extracted_at"] = datetime.utcnow()
        elif result["status"] == "partial":
            updates["extraction_status"] = ExtractionStatus.PARTIAL.value
            updates["extracted_at"] = datetime.utcnow()
        else:
            updates["extraction_status"] = ExtractionStatus.FAILED.value

        if result.get("errors"):
            updates["extraction_error"] = "; ".join(result["errors"])
        elif result.get("warnings"):
            updates["extraction_error"] = "Warning: " + "; ".join(result["warnings"])

        model_build_repo.update_one(build_id, updates)

        if not is_reprocess and updates["extraction_status"] == ExtractionStatus.FAILED.value:
            repo_config_repo.increment_builds_processing_failed(ObjectId(repo_config_id))

        publish_model_processing_updated(
            repo_id=repo_config_id,
            build_id=build_id,
            extraction_status=updates["extraction_status"],
            feature_count=result.get("feature_count", 0),
            expected_feature_count=len(feature_names) if feature_names else 0,
            error=updates.get("extraction_error"),
            ci_run_id=raw_build_run.ci_run_id,
            commit_sha=raw_build_run.commit_sha,
        )

        return {
            "status": result["status"],
            "build_id": build_id,
            "feature_count": result.get("feature_count", 0),
            "errors": result.get("errors", []),
        }

    return self.run_safe(
        job_id=f"{repo_config_id}:{model_build_id}",
        work=_work,
        mark_failed_fn=_mark_failed,
        cleanup_fn=None,
        fail_on_unknown=False,
    )
