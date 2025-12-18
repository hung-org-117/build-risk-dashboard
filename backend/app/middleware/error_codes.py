"""Error codes for standardized API error responses.

Maps HTTP status codes to semantic error codes for consistent client-side handling.
"""

from enum import Enum
from typing import Optional


class ErrorCode(str, Enum):
    """Standardized error codes for API responses."""

    # Client errors (4xx)
    BAD_REQUEST = "BAD_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    UNPROCESSABLE = "UNPROCESSABLE"

    # Server errors (5xx)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    GATEWAY_ERROR = "GATEWAY_ERROR"


# HTTP status code to ErrorCode mapping
STATUS_TO_ERROR_CODE: dict[int, ErrorCode] = {
    400: ErrorCode.BAD_REQUEST,
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    409: ErrorCode.CONFLICT,
    422: ErrorCode.VALIDATION_ERROR,
    429: ErrorCode.RATE_LIMITED,
    500: ErrorCode.INTERNAL_ERROR,
    502: ErrorCode.GATEWAY_ERROR,
    503: ErrorCode.SERVICE_UNAVAILABLE,
}


def get_error_code(status_code: int) -> ErrorCode:
    """Get ErrorCode from HTTP status code."""
    return STATUS_TO_ERROR_CODE.get(status_code, ErrorCode.INTERNAL_ERROR)
