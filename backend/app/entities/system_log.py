"""
SystemLog Entity - Application log entries stored in MongoDB.

This entity represents log entries stored in the system_logs collection,
used for monitoring and debugging application behavior.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import Field

from app.entities.base import BaseEntity


class SystemLog(BaseEntity):
    """System log entry stored in MongoDB."""

    class Config:
        collection = "system_logs"

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the log was created",
    )

    level: str = Field(
        default="INFO",
        description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )

    source: str = Field(
        default="unknown",
        description="Source component/module that generated the log",
    )

    message: str = Field(
        default="",
        description="Log message content",
    )

    correlation_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for cross-referencing with Loki traces",
    )

    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional structured data for the log entry",
    )
