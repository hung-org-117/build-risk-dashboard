"""Authentication utilities: create JWT access tokens for app sessions."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from jose import jwt

from app.config import settings


def create_access_token(subject: str | int, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.utcnow() + expires_delta
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token
