"""
Model Processing Prediction Tasks.

Prediction phase tasks:
- finalize_model_processing: Aggregate results and dispatch prediction
- finalize_prediction: Complete prediction phase
- predict_batch: Batch prediction (alias for predict_builds_batch)
- handle_processing_chain_error: Error handler
"""

# cspell:ignore bson

import logging
from datetime import datetime
from typing import Any, Dict, List

from bson import ObjectId
from celery import chord

from app.celery_app import celery_app
from app.config import settings
from app.entities.enums import ExtractionStatus
from app.entities.model_repo_config import ModelImportStatus
from app.repositories.model_repo_config import ModelRepoConfigRepository
from app.repositories.model_training_build import ModelTrainingBuildRepository
from app.tasks.base import PipelineTask, SafeTask, TaskState
from app.tasks.model.processing.base import ModelPredictionTask
from app.tasks.model.processing.common import (
    create_repo_config_failure_handler,
    publish_status,
)
from app.tasks.shared.events import publish_model_prediction_updated

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="model.processing.complete",
    queue="model_processing",
    soft_time_limit=30,
    time_limit=60,
)
def handle_pipeline_completion(
    self: SafeTask,
    repo_config_id: str,
    created_count: int,
    correlation_id: str = "",
    last_import_build_id: str = "",
) -> Dict[str, Any]:
    """Chain end: Aggregates results after extraction (and prediction)."""

    def mark_failed(e: Exception):
        handler = create_repo_config_failure_handler(
            self.redis, repo_config_id, self.db
        )
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
        logger.info(f"{corr_prefix} Finalizing model processing for {repo_config_id}")

        model_build_repo = ModelTrainingBuildRepository(self.db)
        aggregated_stats = model_build_repo.aggregate_stats_by_repo_config(
            ObjectId(repo_config_id)
        )

        success_count = aggregated_stats.get("builds_features_extracted", 0)
        failed_count = aggregated_stats.get("builds_processing_failed", 0)
        pending_count = aggregated_stats.get("total_pending", 0)
        total_count = success_count + failed_count + pending_count

        logger.info(
            f"{corr_prefix} Processing results from DB: "
            f"success={success_count}, failed={failed_count}, total={total_count}"
        )

        if failed_count > 0 and success_count == 0:
            logger.warning(
                f"{corr_prefix} All builds failed processing ({failed_count})"
            )

        builds_ready = model_build_repo.find_builds_for_prediction(
            ObjectId(repo_config_id)
        )
        builds_for_prediction = [str(b.id) for b in builds_ready]

        repo_config_repo = ModelRepoConfigRepository(self.db)
        update_data = {
            "last_synced_at": datetime.utcnow(),
            "builds_processing_failed": aggregated_stats["builds_processing_failed"],
        }

        if last_import_build_id:
            update_data["last_processed_import_build_id"] = ObjectId(
                last_import_build_id
            )
            logger.info(f"{corr_prefix} Setting checkpoint to {last_import_build_id}")

        repo_config_repo.update_repository(repo_config_id, update_data)

        publish_status(
            repo_config_id,
            "processing",
            f"Extracted features from {success_count}/{total_count} builds, starting prediction...",
            stats={
                "builds_processing_failed": failed_count,
            },
        )

        if builds_for_prediction:
            batch_size = settings.PREDICTION_BUILDS_PER_BATCH
            batches = [
                builds_for_prediction[i : i + batch_size]
                for i in range(0, len(builds_for_prediction), batch_size)
            ]

            logger.info(
                f"{corr_prefix} Dispatching {len(batches)} prediction batches "
                f"({len(builds_for_prediction)} builds, batch_size={batch_size})"
            )

            prediction_tasks = [
                predict_risk_batch.si(
                    repo_config_id=repo_config_id,
                    model_build_ids=batch,
                )
                for batch in batches
            ]
            callback = handle_prediction_completion.si(
                repo_config_id=repo_config_id,
                total_builds=len(builds_for_prediction),
                correlation_id=correlation_id,
            )
            chord(prediction_tasks)(callback)
        else:
            repo_config_repo.update_repository(
                repo_config_id, {"status": ModelImportStatus.PROCESSED.value}
            )
            publish_status(repo_config_id, "processed", "No builds to predict")

        return {
            "repo_config_id": repo_config_id,
            "created": created_count,
            "processed": total_count,
            "success": success_count,
            "failed": failed_count,
            "status": "predicting",
            "aggregated_stats": aggregated_stats,
        }

    return self.run_safe(
        job_id=repo_config_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )


@celery_app.task(
    bind=True,
    base=SafeTask,
    name="model.processing.prediction.complete",
    queue="model_prediction",
    soft_time_limit=30,
    time_limit=60,
)
def handle_prediction_completion(
    self: SafeTask,
    repo_config_id: str,
    total_builds: int,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """Finalize prediction phase after all prediction batches complete."""

    def mark_failed(e: Exception):
        handler = create_repo_config_failure_handler(
            self.redis, repo_config_id, self.db
        )
        handler("failed", str(e))

    def _work(state: TaskState) -> Dict[str, Any]:
        corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
        logger.info(f"{corr_prefix} Finalizing prediction for {repo_config_id}")

        repo_config_repo = ModelRepoConfigRepository(self.db)
        model_build_repo = ModelTrainingBuildRepository(self.db)

        prediction_stats = model_build_repo.aggregate_prediction_stats(
            ObjectId(repo_config_id)
        )
        predicted_count = prediction_stats.get("predicted", 0)
        prediction_failed = prediction_stats.get("failed", 0)

        extraction_stats = model_build_repo.aggregate_stats_by_repo_config(
            ObjectId(repo_config_id)
        )
        extraction_failed = extraction_stats.get("builds_processing_failed", 0)
        total_failed = extraction_failed + prediction_failed

        repo_config_repo.update_repository(
            repo_config_id,
            {
                "status": ModelImportStatus.PROCESSED.value,
                "builds_processing_failed": total_failed,
            },
        )

        logger.info(
            f"{corr_prefix} Prediction complete: {predicted_count} predicted, "
            f"{prediction_failed} prediction failed. Total failures: {total_failed}"
        )

        publish_status(
            repo_config_id,
            "processed",
            f"Processing complete: {predicted_count}/{total_builds} builds predicted",
            stats={
                "predicted": predicted_count,
                "prediction_failed": prediction_failed,
                "builds_processing_failed": total_failed,
            },
        )

        # Notify users
        try:
            from app.services.notification_service import notify_users_for_repo

            repo_config = repo_config_repo.find_by_id(repo_config_id)
            if repo_config and repo_config.raw_repo_id:
                risk_counts = model_build_repo.aggregate_risk_counts(
                    ObjectId(repo_config_id)
                )
                high_count = risk_counts.get("HIGH", 0)
                medium_count = risk_counts.get("MEDIUM", 0)
                low_count = risk_counts.get("LOW", 0)

                high_risk_builds = []
                if high_count > 0:
                    high_risk_builds = model_build_repo.find_high_risk_builds(
                        ObjectId(repo_config_id), limit=3
                    )

                notify_users_for_repo(
                    db=self.db,
                    raw_repo_id=repo_config.raw_repo_id,
                    repo_name=repo_config.full_name,
                    repo_id=repo_config_id,
                    high_risk_builds=[
                        {"build_number": b.build_number} for b in high_risk_builds
                    ],
                    prediction_summary={
                        "high": high_count,
                        "medium": medium_count,
                        "low": low_count,
                    },
                )
                logger.info(
                    f"{corr_prefix} Sent notifications: {high_count} HIGH, "
                    f"{medium_count} MEDIUM, {low_count} LOW"
                )
        except Exception as e:
            logger.warning(f"{corr_prefix} Failed to send user notifications: {e}")

        return {
            "repo_config_id": repo_config_id,
            "status": "processed",
            "predicted": predicted_count,
            "failed": prediction_failed,
            "total": total_builds,
        }

    return self.run_safe(
        job_id=repo_config_id,
        work=_work,
        mark_failed_fn=mark_failed,
    )


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.model_processing.handle_processing_chain_error",
    queue="model_processing",
    soft_time_limit=60,
    time_limit=120,
)
def handle_processing_chain_error(
    self: PipelineTask,
    request,
    exc,
    traceback,
    repo_config_id: str,
    correlation_id: str = "",
) -> Dict[str, Any]:
    """Error callback for processing chain failure."""
    corr_prefix = f"[corr={correlation_id[:8]}]" if correlation_id else ""
    error_msg = str(exc) if exc else "Unknown processing error"

    logger.error(
        f"{corr_prefix} Processing chain failed for {repo_config_id}: {error_msg}"
    )

    model_build_repo = ModelTrainingBuildRepository(self.db)
    repo_config_repo = ModelRepoConfigRepository(self.db)

    in_progress_builds = model_build_repo.find_by_status(
        repo_config_id,
        ExtractionStatus.IN_PROGRESS,
    )

    failed_count = 0
    for build in in_progress_builds:
        model_build_repo.update_one(
            str(build.id),
            {
                "extraction_status": ExtractionStatus.FAILED.value,
                "extraction_error": f"Chain failed: {error_msg}",
            },
        )
        failed_count += 1

    logger.warning(f"{corr_prefix} Marked {failed_count} IN_PROGRESS builds as FAILED")

    completed_builds = model_build_repo.find_by_status(
        repo_config_id,
        ExtractionStatus.COMPLETED,
    )

    if completed_builds:
        repo_config_repo.update_repository(
            repo_config_id,
            {
                "status": ModelImportStatus.PROCESSED.value,
                "error_message": f"Processing had some failures: {error_msg}",
            },
        )
        publish_status(
            repo_config_id,
            ModelImportStatus.PROCESSED.value,
            f"Processing done: {len(completed_builds)} ok, {failed_count} failed.",
        )
    else:
        repo_config_repo.update_repository(
            repo_config_id,
            {
                "status": ModelImportStatus.FAILED.value,
                "error_message": error_msg,
            },
        )
        publish_status(
            repo_config_id,
            "failed",
            f"Processing failed: {error_msg}. Use Retry Failed to retry.",
        )

    try:
        from app.services.notification_service import (
            notify_model_pipeline_failed_to_admins,
        )

        repo_config = repo_config_repo.find_by_id(repo_config_id)
        repo_name = repo_config.full_name if repo_config else repo_config_id
        notify_model_pipeline_failed_to_admins(
            db=self.db,
            repo_name=repo_name,
            error_message=f"Processing failed: {error_msg}",
        )
    except Exception as e:
        logger.warning(f"{corr_prefix} Failed to send failure notification: {e}")

    return {
        "status": "handled",
        "failed_builds": failed_count,
        "completed_builds": len(completed_builds) if completed_builds else 0,
        "error": error_msg,
    }


@celery_app.task(
    bind=True,
    base=ModelPredictionTask,
    name="model.processing.predict_risk",
    queue="model_prediction",
    soft_time_limit=300,
    time_limit=600,
)
def predict_risk_batch(
    self: ModelPredictionTask,
    repo_config_id: str,
    model_build_ids: List[str],
) -> Dict[str, Any]:  # noqa: C901
    """Batch prediction for multiple builds."""
    from app.repositories.feature_vector import FeatureVectorRepository
    from app.services.prediction_service import PredictionService

    if not model_build_ids:
        return {"status": "completed", "processed": 0}

    model_build_repo = ModelTrainingBuildRepository(self.db)
    feature_vector_repo = FeatureVectorRepository(self.db)
    repo_config_repo = ModelRepoConfigRepository(self.db)
    prediction_service = PredictionService()

    def _mark_failed(exc: Exception) -> None:
        for build_id in model_build_ids:
            model_build_repo.collection.update_one(
                {
                    "_id": ObjectId(build_id),
                    "prediction_status": {
                        "$in": [
                            ExtractionStatus.PENDING.value,
                            ExtractionStatus.IN_PROGRESS.value,
                        ]
                    },
                },
                {
                    "$set": {
                        "prediction_status": ExtractionStatus.FAILED.value,
                        "prediction_error": f"Batch prediction failed: {str(exc)}",
                    }
                },
            )

    def _cleanup(state: TaskState) -> None:
        for build_id in model_build_ids:
            model_build_repo.collection.update_one(
                {
                    "_id": ObjectId(build_id),
                    "prediction_status": ExtractionStatus.IN_PROGRESS.value,
                },
                {
                    "$set": {
                        "prediction_status": ExtractionStatus.PENDING.value,
                        "prediction_error": None,
                    }
                },
            )

    def _work(state: TaskState) -> Dict[str, Any]:  # noqa: C901
        if state.phase == "START":
            builds_to_predict = []

            for build_id in model_build_ids:
                model_build = model_build_repo.find_by_id(ObjectId(build_id))
                if not model_build:
                    continue
                if model_build.predicted_label and not model_build.prediction_error:
                    continue

                if not model_build.feature_vector_id:
                    model_build_repo.update_one(
                        build_id,
                        {
                            "prediction_status": ExtractionStatus.FAILED.value,
                            "prediction_error": "No feature_vector_id available",
                        },
                    )
                    continue

                feature_vector = feature_vector_repo.find_by_id(
                    model_build.feature_vector_id
                )
                if not feature_vector or not feature_vector.features:
                    model_build_repo.update_one(
                        build_id,
                        {
                            "prediction_status": ExtractionStatus.FAILED.value,
                            "prediction_error": "FeatureVector not found or empty",
                        },
                    )
                    continue

                temporal_history = None
                tr_prev_build_id = feature_vector.tr_prev_build
                if tr_prev_build_id:
                    try:
                        history_vectors = feature_vector_repo.walk_temporal_chain(
                            raw_repo_id=feature_vector.raw_repo_id,
                            starting_ci_run_id=tr_prev_build_id,
                            max_depth=9,
                        )
                        if history_vectors:
                            temporal_history = [
                                v.features for v in reversed(history_vectors)
                            ]
                    except Exception as e:
                        logger.warning(
                            f"Failed to fetch temporal history for {build_id}: {e}"
                        )

                was_previously_failed = (
                    model_build.prediction_status == ExtractionStatus.FAILED.value
                )

                builds_to_predict.append(
                    {
                        "id": build_id,
                        "features": feature_vector.features,
                        "feature_vector_id": feature_vector.id,
                        "temporal_history": temporal_history,
                        "was_previously_failed": was_previously_failed,
                    }
                )

            state.meta["builds_to_predict"] = builds_to_predict

            if not builds_to_predict:
                state.phase = "DONE"
                state.meta["result"] = {
                    "status": "completed",
                    "processed": 0,
                    "skipped": len(model_build_ids),
                }
            else:
                state.phase = "NORMALIZING"

        if state.phase == "NORMALIZING":
            builds_to_predict = state.meta["builds_to_predict"]

            for build_info in builds_to_predict:
                model_build_repo.update_one(
                    build_info["id"],
                    {"prediction_status": ExtractionStatus.IN_PROGRESS.value},
                )
                publish_model_prediction_updated(
                    repo_id=repo_config_id,
                    build_id=build_info["id"],
                    prediction_status=ExtractionStatus.IN_PROGRESS.value,
                )

            for build_info in builds_to_predict:
                normalized = prediction_service.normalize_features(
                    build_info["features"]
                )
                build_info["normalized_features"] = normalized
                feature_vector_repo.update_normalized_features(
                    build_info["feature_vector_id"],
                    normalized,
                )
                if build_info["temporal_history"]:
                    build_info["normalized_history"] = [
                        prediction_service.normalize_features(h)
                        for h in build_info["temporal_history"]
                    ]
                else:
                    build_info["normalized_history"] = None

            state.meta["builds_to_predict"] = builds_to_predict
            state.phase = "PREDICTING"

        if state.phase == "PREDICTING":
            builds_to_predict = state.meta["builds_to_predict"]
            results = []

            for build_info in builds_to_predict:
                result = prediction_service.predict(
                    features=build_info["normalized_features"],
                    temporal_history=build_info["normalized_history"],
                    use_prescaled=True,
                )
                results.append(result)

            state.meta["results"] = results
            state.phase = "STORING"

        if state.phase == "STORING":
            builds_to_predict = state.meta["builds_to_predict"]
            results = state.meta["results"]

            succeeded = 0
            failed = 0
            retried_success_count = 0
            new_failure_count = 0

            for i, build_info in enumerate(builds_to_predict):
                if i >= len(results):
                    failed += 1
                    continue

                prediction = results[i]

                updates = {
                    "predicted_label": prediction.risk_level,
                    "prediction_confidence": prediction.risk_score,
                    "prediction_uncertainty": prediction.uncertainty,
                    "prediction_model_version": prediction.model_version,
                    "predicted_at": datetime.utcnow(),
                }

                if prediction.error:
                    updates["prediction_status"] = ExtractionStatus.FAILED.value
                    updates["prediction_error"] = prediction.error
                    failed += 1
                    if not build_info.get("was_previously_failed", False):
                        new_failure_count += 1
                else:
                    updates["prediction_status"] = ExtractionStatus.COMPLETED.value
                    updates["prediction_error"] = None
                    succeeded += 1
                    if build_info.get("was_previously_failed", False):
                        retried_success_count += 1

                model_build_repo.update_one(build_info["id"], updates)

                publish_model_prediction_updated(
                    repo_id=repo_config_id,
                    build_id=build_info["id"],
                    prediction_status=updates["prediction_status"],
                    predicted_label=updates.get("predicted_label"),
                    prediction_confidence=updates.get("prediction_confidence"),
                    error=updates.get("prediction_error"),
                )

            if retried_success_count > 0:
                repo_config_repo.decrement_builds_processing_failed(
                    ObjectId(repo_config_id), retried_success_count
                )
            if new_failure_count > 0:
                repo_config_repo.increment_builds_processing_failed(
                    ObjectId(repo_config_id), new_failure_count
                )
            if succeeded > 0:
                repo_config_repo.increment_builds_completed(
                    ObjectId(repo_config_id), succeeded
                )

            if retried_success_count > 0 or new_failure_count > 0 or succeeded > 0:
                config = repo_config_repo.find_by_id(repo_config_id)
                if config:
                    publish_status(
                        repo_config_id,
                        config.status,
                        stats={
                            "builds_completed": config.builds_completed,
                            "builds_processing_failed": config.builds_processing_failed,
                        },
                    )

            logger.info(f"Batch prediction: {succeeded} succeeded, {failed} failed")

            state.meta["result"] = {
                "status": "completed",
                "processed": len(builds_to_predict),
                "succeeded": succeeded,
                "failed": failed,
            }
            state.phase = "DONE"

        return state.meta.get("result", {"status": "completed", "processed": 0})

    return self.run_safe(
        job_id=f"predict:{repo_config_id}:{len(model_build_ids)}",
        work=_work,
        mark_failed_fn=_mark_failed,
        cleanup_fn=_cleanup,
        fail_on_unknown=False,
    )
