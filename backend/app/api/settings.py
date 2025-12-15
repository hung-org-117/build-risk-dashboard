"""Application settings API endpoints."""

from fastapi import APIRouter, Depends, status
from pymongo.database import Database

from app.database.mongo import get_db
from app.middleware.auth import get_current_user
from app.dtos.settings import (
    ApplicationSettingsResponse,
    ApplicationSettingsUpdateRequest,
)
from app.services.settings_service import SettingsService


router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/", response_model=ApplicationSettingsResponse)
def get_settings(
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get current application settings."""
    service = SettingsService(db)
    return service.get_settings()


@router.patch("/", response_model=ApplicationSettingsResponse)
def update_settings(
    request: ApplicationSettingsUpdateRequest,
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update application settings."""
    service = SettingsService(db)
    return service.update_settings(request)
