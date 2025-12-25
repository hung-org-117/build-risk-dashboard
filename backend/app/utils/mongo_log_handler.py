"""
MongoDB Log Handler - Stores application logs to MongoDB for viewing in UI.

This handler should be added to the root logger in main.py to capture
important application logs for administrator review.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from pymongo import MongoClient
from pymongo.collection import Collection

from app.config import settings


class MongoDBLogHandler(logging.Handler):
    """
    Custom logging handler that writes logs to MongoDB.

    Only logs at WARNING level and above are stored to avoid excessive storage.
    """

    def __init__(
        self,
        level: int = logging.WARNING,
        collection_name: str = "system_logs",
    ):
        super().__init__(level)
        self._client: Optional[MongoClient] = None
        self._collection: Optional[Collection] = None
        self.collection_name = collection_name

    @property
    def collection(self) -> Optional[Collection]:
        """Lazy connection to MongoDB."""
        if self._collection is None:
            try:
                self._client = MongoClient(settings.MONGODB_URI)
                db = self._client[settings.MONGODB_DB_NAME]
                self._collection = db[self.collection_name]

                # Create index on timestamp for efficient queries
                self._collection.create_index(
                    "timestamp", expireAfterSeconds=2592000
                )  # 30 days TTL
            except Exception:
                pass
        return self._collection

    def emit(self, record: logging.LogRecord):
        """Write log record to MongoDB."""
        try:
            if self.collection is None:
                return

            # Get correlation_id from TracingContext for Loki cross-reference
            from app.core.tracing import TracingContext

            correlation_id = TracingContext.get_correlation_id() or None

            log_entry = {
                "timestamp": datetime.now(timezone.utc),
                "level": record.levelname,
                "source": record.name,
                "message": self.format(record),
                "correlation_id": correlation_id,
                "details": {
                    "filename": record.filename,
                    "lineno": record.lineno,
                    "funcName": record.funcName,
                },
            }

            # Add exception info if present
            if record.exc_info:
                log_entry["details"]["exception"] = (
                    str(record.exc_info[1]) if record.exc_info[1] else None
                )

            self.collection.insert_one(log_entry)

            # Publish to Redis for real-time WebSocket streaming
            self._publish_to_websocket(log_entry)

            # Alert admins for ERROR/CRITICAL logs (with debounce)
            if record.levelno >= logging.ERROR:
                self._alert_on_error(record, correlation_id)
        except Exception:
            # Silent fail - don't break the app if logging fails
            pass

    def _alert_on_error(self, record: logging.LogRecord, correlation_id: str | None) -> None:
        """
        Alert admins on ERROR/CRITICAL logs with Redis-based debouncing.

        Uses Redis TTL to prevent notification spam - only alerts once per
        source module every 5 minutes.
        """
        try:
            import redis

            from app.config import settings
            from app.database.mongo import get_database
            from app.services.notification_service import notify_system_error_to_admins

            # Debounce key: prevent same source from spamming within 5 minutes
            debounce_key = f"log_alert:{record.name}"
            redis_client = redis.from_url(settings.REDIS_URL)

            # Check if we've already alerted for this source recently
            if redis_client.exists(debounce_key):
                return

            # Set debounce key with 5 minute TTL
            redis_client.setex(debounce_key, 300, "1")

            # Send notification
            db = get_database()
            notify_system_error_to_admins(
                db=db,
                source=record.name,
                message=self.format(record),
                correlation_id=correlation_id,
            )
        except Exception:
            # Silent fail - alerting failure shouldn't break logging
            pass

    def _publish_to_websocket(self, log_entry: dict) -> None:
        """
        Publish log entry to Redis for real-time WebSocket streaming.

        Clients subscribed to 'system_logs' channel will receive these logs.
        """
        try:
            import json

            import redis

            from app.config import settings

            redis_client = redis.from_url(settings.REDIS_URL)

            # Convert datetime to ISO string for JSON serialization
            ws_entry = {
                "timestamp": log_entry["timestamp"].isoformat(),
                "level": log_entry["level"],
                "source": log_entry["source"],
                "message": log_entry["message"],
                "correlation_id": log_entry.get("correlation_id"),
            }

            redis_client.publish("system_logs", json.dumps(ws_entry))
        except Exception:
            # Silent fail - don't break logging if Redis fails
            pass

    def close(self):
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
        super().close()


def setup_mongodb_logging():
    """
    Add MongoDB log handler to root logger.

    Call this in main.py after app initialization.
    """
    handler = MongoDBLogHandler(level=logging.WARNING)
    handler.setFormatter(logging.Formatter("%(message)s"))

    # Add to root logger
    logging.getLogger().addHandler(handler)

    # Also add to specific loggers
    for logger_name in ["app", "uvicorn.error", "celery"]:
        logging.getLogger(logger_name).addHandler(handler)
