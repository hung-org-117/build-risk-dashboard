
from pymongo.database import Database

# from app.dtos.github import (
#     GithubInstallationListResponse,
#     GithubInstallationResponse,
# )


class IntegrationService:
    def __init__(self, db: Database):
        self.db = db

    # Removed list_github_installations, get_github_installation, sync_installations
    # as we moved to single-tenant config based installation ID.
