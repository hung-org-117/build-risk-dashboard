"""User management helper endpoints (role definitions)."""
from fastapi import APIRouter

from app.models.schemas import RoleListResponse

router = APIRouter(prefix="/users", tags=["Users"])

ROLE_DEFINITIONS = [
    {
        "role": "Administrator",
        "description": "Quản lý người dùng, repositories, cấu hình hệ thống và rescan dữ liệu.",
        "permissions": [
            "manage_repositories",
            "configure_settings",
            "view_logs",
            "update_notification_policy",
        ],
        "admin_only": True,
    },
    {
        "role": "DevOps Engineer",
        "description": "Import repositories, xem dashboard rủi ro và nhận cảnh báo high-risk/uncertain builds.",
        "permissions": [
            "import_repositories",
            "view_dashboard",
            "acknowledge_alerts",
        ],
        "admin_only": False,
    },
    {
        "role": "Repository Member",
        "description": "Đăng nhập bằng GitHub, xem read-only dashboard cho repository sở hữu hoặc cộng tác.",
        "permissions": [
            "view_assigned_repositories",
            "receive_alerts",
        ],
        "admin_only": False,
    },
]


@router.get("/roles", response_model=RoleListResponse)
def list_roles():
    return {"roles": ROLE_DEFINITIONS}
