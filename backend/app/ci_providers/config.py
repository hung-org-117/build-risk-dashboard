from typing import Optional

from pymongo.database import Database

from app.config import settings

from .models import CIProvider, ProviderConfig


def get_provider_config(
    provider_type: CIProvider, db: Optional[Database] = None
) -> ProviderConfig:
    """
    Get ProviderConfig for a CI provider.

    Prioritizes database settings over environment variables:
    1. If db is provided, use SettingsService to get decrypted token from DB
    2. Fall back to environment variables if db is None or token not found

    Args:
        provider_type: The CI provider type
        db: Optional database instance for fetching tokens from settings

    Returns:
        ProviderConfig populated with settings
    """
    token = None
    base_url = None

    # Try to get token from database if db is provided
    if db:
        try:
            from app.services.settings_service import SettingsService

            settings_service = SettingsService(db)

            if provider_type == CIProvider.CIRCLECI:
                token = settings_service.get_decrypted_token("circleci")
            elif provider_type == CIProvider.TRAVIS_CI:
                token = settings_service.get_decrypted_token("travis")
        except Exception:
            # Silently fall back to ENV if settings retrieval fails
            pass

    # Provider-specific configuration with ENV fallback
    if provider_type == CIProvider.GITHUB_ACTIONS:
        # GitHub uses token pool, get first available token
        if not token:
            token = settings.GITHUB_TOKENS[0] if settings.GITHUB_TOKENS else None
        base_url = settings.GITHUB_API_URL
        return ProviderConfig(
            provider=provider_type,
            token=token,
            base_url=base_url,
        )

    elif provider_type == CIProvider.CIRCLECI:
        if not token:
            token = settings.CIRCLECI_TOKEN
        base_url = settings.CIRCLECI_BASE_URL
        return ProviderConfig(
            provider=provider_type,
            token=token,
            base_url=base_url,
        )

    elif provider_type == CIProvider.TRAVIS_CI:
        if not token:
            token = settings.TRAVIS_TOKEN
        base_url = settings.TRAVIS_BASE_URL
        return ProviderConfig(
            provider=provider_type,
            token=token,
            base_url=base_url,
        )

    return ProviderConfig(provider=provider_type)


def get_configured_provider(provider_type: CIProvider, db: Optional[Database] = None):
    """
    Get a fully configured CI provider instance.

    Args:
        provider_type: The CI provider type
        db: Optional database instance for fetching tokens from settings

    Returns:
        CIProviderInterface instance ready to use
    """
    from .factory import get_ci_provider

    config = get_provider_config(provider_type, db=db)
    return get_ci_provider(provider_type, config, db=db)
