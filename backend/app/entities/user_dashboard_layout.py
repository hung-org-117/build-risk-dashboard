"""Entity for storing user dashboard layout preferences."""

from datetime import datetime
from typing import List

from pydantic import Field

from app.entities.base import BaseEntity, PyObjectId


class WidgetConfig(BaseEntity):
    """Configuration for a single widget in the dashboard."""

    widget_id: str  # Unique widget identifier (e.g., "total_builds", "success_rate")
    widget_type: str  # Widget type (e.g., "stat", "chart", "table")
    title: str  # Display title
    enabled: bool = True  # Whether widget is visible
    # Grid position (react-grid-layout format)
    x: int = 0  # X position in grid units
    y: int = 0  # Y position in grid units
    w: int = 1  # Width in grid units
    h: int = 1  # Height in grid units


class UserDashboardLayout(BaseEntity):
    """Stores per-user dashboard layout preferences."""

    user_id: PyObjectId
    widgets: List[WidgetConfig] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Default widgets for new users
DEFAULT_WIDGETS = [
    WidgetConfig(
        widget_id="total_builds",
        widget_type="stat",
        title="Total Builds",
        x=0,
        y=0,
        w=1,
        h=1,
    ),
    WidgetConfig(
        widget_id="success_rate",
        widget_type="stat",
        title="Success Rate",
        x=1,
        y=0,
        w=1,
        h=1,
    ),
    WidgetConfig(
        widget_id="avg_duration",
        widget_type="stat",
        title="Avg Duration",
        x=2,
        y=0,
        w=1,
        h=1,
    ),
    WidgetConfig(
        widget_id="active_repos",
        widget_type="stat",
        title="Active Repos",
        x=3,
        y=0,
        w=1,
        h=1,
    ),
    WidgetConfig(
        widget_id="repo_distribution",
        widget_type="table",
        title="Repository Distribution",
        x=0,
        y=1,
        w=2,
        h=2,
    ),
    WidgetConfig(
        widget_id="recent_builds",
        widget_type="table",
        title="Recent Builds",
        x=2,
        y=1,
        w=2,
        h=2,
    ),
]
