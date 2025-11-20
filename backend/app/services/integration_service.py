from fastapi import HTTPException, status
from pymongo.database import Database

from app.dtos.github import (
    GithubInstallationListResponse,
    GithubInstallationResponse,
)


class IntegrationService:
    def __init__(self, db: Database):
        self.db = db

    def list_github_installations(self) -> GithubInstallationListResponse:
        """List all GitHub App installations."""
        installations_cursor = self.db.github_installations.find().sort(
            "installed_at", -1
        )
        installations = [
            GithubInstallationResponse(**inst) for inst in installations_cursor
        ]
        return GithubInstallationListResponse(installations=installations)

    def get_github_installation(
        self, installation_id: str
    ) -> GithubInstallationResponse:
        """Get details of a specific GitHub App installation."""
        installation = self.db.github_installations.find_one({"_id": installation_id})
        if not installation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installation {installation_id} not found",
            )
        return GithubInstallationResponse(**installation)
