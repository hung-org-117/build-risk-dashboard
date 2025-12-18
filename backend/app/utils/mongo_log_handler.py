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

            log_entry = {
                "timestamp": datetime.now(timezone.utc),
                "level": record.levelname,
                "source": record.name,
                "message": self.format(record),
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
        except Exception:
            # Silent fail - don't break the app if logging fails
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
