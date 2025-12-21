"""Integration DTOs - Simplified for version-scoped scan flow."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# =============================================================================
# Tool DTOs
# =============================================================================


class ToolInfoResponse(BaseModel):
    """Response DTO for tool information."""

    name: str
    type: str
    description: str
    scan_mode: str
    is_available: bool
    config: Dict[str, Any]


class ToolsListResponse(BaseModel):
    """Response DTO for tools list."""

    tools: List[ToolInfoResponse]


# =============================================================================
# Webhook DTO
# =============================================================================


class SonarWebhookPayload(BaseModel):
    """Payload DTO for SonarQube webhook."""

    project: dict
    status: str
    analysedAt: Optional[str] = None
