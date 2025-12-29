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


# Default widgets for new users (using 12-column grid to match frontend)
DEFAULT_WIDGETS = [
    WidgetConfig(
        widget_id="total_builds",
        widget_type="stat",
        title="Total Builds",
        x=0,
        y=0,
        w=3,  # 3/12 = 25% width
        h=1,
    ),
    WidgetConfig(
        widget_id="success_rate",
        widget_type="stat",
        title="Success Rate",
        x=3,
        y=0,
        w=3,  # 3/12 = 25% width
        h=1,
    ),
    WidgetConfig(
        widget_id="avg_duration",
        widget_type="stat",
        title="Avg Duration",
        x=6,
        y=0,
        w=3,  # 3/12 = 25% width
        h=1,
    ),
    WidgetConfig(
        widget_id="active_repos",
        widget_type="stat",
        title="Active Repos",
        x=9,
        y=0,
        w=3,  # 3/12 = 25% width
        h=1,
    ),
    WidgetConfig(
        widget_id="repo_distribution",
        widget_type="table",
        title="Repository Distribution",
        x=0,
        y=1,
        w=6,  # 6/12 = 50% width
        h=3,
    ),
    WidgetConfig(
        widget_id="recent_builds",
        widget_type="table",
        title="Recent Builds",
        x=6,
        y=1,
        w=6,  # 6/12 = 50% width
        h=3,
    ),
]
