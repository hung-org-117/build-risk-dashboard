import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.utcnow()


def parse_datetime(dt_value, default_now: bool = True) -> datetime | None:
    """
    Parse datetime from API response to naive UTC datetime.

    Handles:
    - ISO string with timezone (e.g., "2024-01-01T00:00:00Z") -> naive UTC datetime
    - datetime object with timezone -> naive UTC datetime
    - datetime object without timezone -> returned as-is
    - None or invalid -> current UTC time (if default_now=True) or None

    Args:
        dt_value: The datetime value to parse (str, datetime, or None)
        default_now: If True, return current UTC time for None/invalid values.
                     If False, return None for None/invalid values.

    Returns:
        Naive UTC datetime or None (if default_now=False and value is None/invalid)
    """
    if dt_value is None:
        return utc_now() if default_now else None

    if isinstance(dt_value, str):
        try:
            # Parse ISO format string (e.g., "2024-01-01T00:00:00Z")
            dt = datetime.fromisoformat(dt_value.replace("Z", "+00:00"))
            # Convert to naive UTC datetime
            return dt.replace(tzinfo=None)
        except (ValueError, AttributeError):
            logger.warning(f"Failed to parse datetime string: {dt_value}")
            return utc_now() if default_now else None

    if isinstance(dt_value, datetime):
        if dt_value.tzinfo is not None:
            # Convert to naive UTC datetime
            return dt_value.astimezone(timezone.utc).replace(tzinfo=None)
        return dt_value

    logger.warning(f"Unexpected datetime type: {type(dt_value)}")
    return utc_now() if default_now else None


def ensure_naive_utc(dt_value: datetime | None) -> datetime | None:
    """
    Ensure a datetime is naive UTC.

    Useful when reading from database where datetime might be stored
    as naive but needs to be compared with other naive UTC datetimes.

    Args:
        dt_value: datetime to normalize

    Returns:
        Naive UTC datetime or None if input is None
    """
    if dt_value is None:
        return None

    if isinstance(dt_value, datetime):
        if dt_value.tzinfo is not None:
            return dt_value.astimezone(timezone.utc).replace(tzinfo=None)
        return dt_value

    return None
