from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import Field

from .base import BaseEntity


class User(BaseEntity):
    email: str
    name: Optional[str] = None
    role: Literal["admin", "user", "guest"] = "user"
    notification_email: Optional[str] = None

    # Stores list of repo full_names the user has access to on GitHub
    github_accessible_repos: List[str] = Field(default_factory=list)
    github_repos_synced_at: Optional[datetime] = None
