import logging
from typing import List, Optional

from .base import PipelineContext, PipelineStep
from .hooks import PipelineHook

logger = logging.getLogger(__name__)


class PipelineRunner:
    """
    Orchestrator that executes a sequence of pipeline steps.
    """

    def __init__(self, steps: List[PipelineStep], hooks: Optional[List[PipelineHook]] = None):
        self.steps = steps
        self.hooks = hooks or []

    def run(self, context: PipelineContext) -> PipelineContext:
        """
        Execute all steps in order.
        """
        self._notify_pipeline_start(context)

        try:
            for step in self.steps:
                if context.is_stopped:
                    logger.info(f"Pipeline {context.pipeline_id} stopped before step {step.name}")
                    break

                self._execute_step(step, context)

            self._notify_pipeline_finish(context)
            return context

        except Exception as e:
            logger.error(f"Pipeline {context.pipeline_id} failed: {e}")
            self._notify_pipeline_failure(context, e)
            raise e

    def _execute_step(self, step: PipelineStep, context: PipelineContext):
        self._notify_step_start(step, context)
        try:
            step.execute(context)
            self._notify_step_success(step, context)
        except Exception as e:
            self._notify_step_failure(step, context, e)
            raise e

    # --- Hook Notifications ---

    def _notify_pipeline_start(self, context: PipelineContext):
        for hook in self.hooks:
            try:
                hook.on_pipeline_start(context)
            except Exception as e:
                logger.warning(f"Hook on_pipeline_start failed: {e}")

    def _notify_pipeline_finish(self, context: PipelineContext):
        for hook in self.hooks:
            try:
                hook.on_pipeline_finish(context)
            except Exception as e:
                logger.warning(f"Hook on_pipeline_finish failed: {e}")

    def _notify_pipeline_failure(self, context: PipelineContext, error: Exception):
        for hook in self.hooks:
            try:
                hook.on_pipeline_failure(context, error)
            except Exception as e:
                logger.warning(f"Hook on_pipeline_failure failed: {e}")

    def _notify_step_start(self, step: PipelineStep, context: PipelineContext):
        for hook in self.hooks:
            try:
                hook.on_step_start(step, context)
            except Exception as e:
                logger.warning(f"Hook on_step_start failed: {e}")

    def _notify_step_success(self, step: PipelineStep, context: PipelineContext):
        for hook in self.hooks:
            try:
                hook.on_step_success(step, context)
            except Exception as e:
                logger.warning(f"Hook on_step_success failed: {e}")

    def _notify_step_failure(self, step: PipelineStep, context: PipelineContext, error: Exception):
        for hook in self.hooks:
            try:
                hook.on_step_failure(step, context, error)
            except Exception as e:
                logger.warning(f"Hook on_step_failure failed: {e}")
