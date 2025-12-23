"""
Structured Logging Configuration.

Supports two modes:
- text: Human-readable format for development
- json: Structured JSON format for production (enables Loki parsing)

Set LOG_FORMAT environment variable to "json" for production.
"""

import json
import logging
import os
import sys
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings with tracing context.

    Automatically includes correlation_id, dataset_id, etc. from TracingContext
    for easy filtering in Loki/Grafana.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Import here to avoid circular imports
        try:
            from app.core.tracing import TracingContext

            ctx = TracingContext.get()
        except ImportError:
            ctx = {}

        log_record: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "line": record.lineno,
            # Tracing fields for Loki filtering
            "correlation_id": ctx.get("correlation_id", ""),
            "dataset_id": ctx.get("dataset_id", ""),
            "version_id": ctx.get("version_id", ""),
            "repo_id": ctx.get("repo_id", ""),
            "pipeline_type": ctx.get("pipeline_type", ""),
            "task_name": ctx.get("task_name", ""),
        }

        # Add extra fields if provided
        if hasattr(record, "task_id"):
            log_record["task_id"] = record.task_id

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)


def setup_logging() -> None:
    """
    Setup structured logging for the application.

    Uses LOG_FORMAT env var to determine format:
    - "json": Structured JSON for production/Loki
    - "text" (default): Human-readable for development
    """
    root_logger = logging.getLogger()

    # Avoid adding multiple handlers
    if root_logger.handlers:
        return

    root_logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)

    # Use JSON format for production (enables Loki parsing)
    log_format = os.getenv("LOG_FORMAT", "text").lower()

    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        # Human-readable format for development
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)

    root_logger.addHandler(handler)

    # Set lower level for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
