"""
Prediction Tasks - Celery tasks for ML risk prediction.

Follows app-flow rules:
- Full implementation (no stubs)
- Explicit naming (training_build_id, prediction_service)
- Service layer integration
"""

import logging
from typing import Any, Dict

from celery import shared_task

from app.database import get_database
from app.services.prediction_service import PredictionService

logger = logging.getLogger(__name__)


@shared_task(
    name="app.tasks.prediction_tasks.predict_build_risk",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def predict_build_risk(self, training_build_id: str) -> Dict[str, Any]:
    """
    Predict risk level for a single build.

    Args:
        training_build_id: The ModelTrainingBuild ID to predict

    Returns:
        Dict with prediction result or error
    """
    logger.info(f"Starting risk prediction for build: {training_build_id}")

    try:
        db = get_database()
        prediction_service = PredictionService(db)

        result = prediction_service.predict_build_risk(training_build_id)

        if result:
            return {
                "success": True,
                "training_build_id": training_build_id,
                "risk_level": result.risk_level,
                "uncertainty": result.uncertainty,
                "model_version": result.model_version,
            }
        else:
            return {
                "success": False,
                "training_build_id": training_build_id,
                "error": "Prediction failed - build not found or no features",
            }

    except Exception as exc:
        logger.exception(f"Prediction task failed for build {training_build_id}")
        # Retry on transient errors
        raise self.retry(exc=exc)


@shared_task(
    name="app.tasks.prediction_tasks.predict_batch",
    bind=True,
)
def predict_batch(self, training_build_ids: list) -> Dict[str, Any]:
    """
    Predict risk level for multiple builds in batch.

    Args:
        training_build_ids: List of ModelTrainingBuild IDs

    Returns:
        Dict with success/failure counts
    """
    logger.info(f"Starting batch prediction for {len(training_build_ids)} builds")

    db = get_database()
    prediction_service = PredictionService(db)

    success_count = 0
    failure_count = 0
    results = []

    for training_build_id in training_build_ids:
        try:
            result = prediction_service.predict_build_risk(training_build_id)
            if result:
                success_count += 1
                results.append(
                    {
                        "training_build_id": training_build_id,
                        "risk_level": result.risk_level,
                        "success": True,
                    }
                )
            else:
                failure_count += 1
                results.append(
                    {
                        "training_build_id": training_build_id,
                        "success": False,
                        "error": "No features available",
                    }
                )
        except Exception as exc:
            failure_count += 1
            logger.error(f"Prediction failed for {training_build_id}: {exc}")
            results.append(
                {
                    "training_build_id": training_build_id,
                    "success": False,
                    "error": str(exc),
                }
            )

    return {
        "total": len(training_build_ids),
        "success_count": success_count,
        "failure_count": failure_count,
        "results": results,
    }
