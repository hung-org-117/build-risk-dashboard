from typing import Any, Dict

from app.pipelines.components.export.dataset_export import DatasetExportStep
from app.pipelines.components.ingestion.git import GitIngestionStep
from app.pipelines.components.ingestion.logs import BuildLogsIngestionStep
from app.pipelines.components.processing.hamilton import HamiltonProcessingStep
from app.pipelines.components.processing.scan import ScanStep
from app.pipelines.core.base import PipelineContext
from app.pipelines.core.runner import PipelineRunner


class DatasetEnrichmentPipeline:
    """
    Factory to create the Dataset Enrichment Pipeline.
    """

    @classmethod
    def create(cls, db: Any, config: Dict[str, Any]) -> PipelineRunner:
        repo_id = config["raw_repo_id"]
        github_id = config["github_repo_id"]
        full_name = config["full_name"]
        ci_provider = config["ci_provider"]
        enable_scans = config.get("enable_scans", False)

        steps = [
            GitIngestionStep(repo_id, github_id, full_name),
            BuildLogsIngestionStep(repo_id, github_id, full_name, ci_provider),
            HamiltonProcessingStep(db),
        ]

        if enable_scans:
            # Add scan steps if configured
            # This demonstrates extensibility - easy to add multiple steps
            steps.append(ScanStep("trivy", config.get("trivy_config", {})))
            steps.append(ScanStep("sonar", config.get("sonar_config", {})))

        # Export might serve a different lifecycle (triggered manually later)
        # But if part of the flow, it can be here.
        if config.get("run_export"):
            steps.append(DatasetExportStep(db))

        return PipelineRunner(steps)

    @classmethod
    def run(cls, db: Any, pipeline_id: str, config: Dict[str, Any]):
        runner = cls.create(db, config)
        context = PipelineContext(pipeline_id, config)
        return runner.run(context)
