from abc import ABC

from .base import PipelineContext, PipelineStep


class PipelineHook(ABC):
    """
    Interface for pipeline hooks to intercept execution events.
    """

    def on_pipeline_start(self, context: PipelineContext):
        pass

    def on_pipeline_finish(self, context: PipelineContext):
        pass

    def on_pipeline_failure(self, context: PipelineContext, error: Exception):
        pass

    def on_step_start(self, step: PipelineStep, context: PipelineContext):
        pass

    def on_step_success(self, step: PipelineStep, context: PipelineContext):
        pass

    def on_step_failure(self, step: PipelineStep, context: PipelineContext, error: Exception):
        pass
