from typing import Any, Dict

from app.pipelines.components.ingestion.git import GitIngestionStep
from app.pipelines.components.ingestion.logs import BuildLogsIngestionStep
from app.pipelines.components.processing.hamilton import HamiltonProcessingStep
from app.pipelines.components.processing.prediction import PredictionStep
from app.pipelines.core.base import PipelineContext
from app.pipelines.core.runner import PipelineRunner


class RiskEvaluationPipeline:
    """
    Factory to create the Risk Evaluation Pipeline.
    """

    @classmethod
    def create(cls, db: Any, config: Dict[str, Any]) -> PipelineRunner:
        repo_id = config["raw_repo_id"]
        github_id = config["github_repo_id"]
        full_name = config["full_name"]
        ci_provider = config["ci_provider"]

        steps = [
            GitIngestionStep(repo_id, github_id, full_name),
            BuildLogsIngestionStep(repo_id, github_id, full_name, ci_provider),
            HamiltonProcessingStep(db),
            PredictionStep(db),
        ]

        return PipelineRunner(steps)

    @classmethod
    def run(cls, db: Any, pipeline_id: str, config: Dict[str, Any]):
        runner = cls.create(db, config)
        context = PipelineContext(pipeline_id, config)
        return runner.run(context)
