"""GitHub OAuth helper utilities (MongoDB)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

import httpx
from fastapi import HTTPException, status
from pymongo.database import Database

from app.config import settings

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"


def _require_github_credentials() -> None:
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub OAuth credentials are not configured. Set GITHUB_CLIENT_ID/SECRET.",
        )


def build_authorize_url(state: str) -> str:
    scopes = settings.GITHUB_SCOPES or ["read:user", "repo", "read:org", "workflow"]
    scope_param = " ".join(scopes)
    return (
        f"{GITHUB_AUTHORIZE_URL}"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&scope={scope_param}"
        f"&redirect_uri={settings.GITHUB_REDIRECT_URI}"
        f"&state={state}"
    )


def create_oauth_state(db: Database, redirect_url: Optional[str] = None) -> dict:
    _require_github_credentials()
    state = uuid.uuid4().hex
    document = {
        "_id": state,
        "redirect_url": redirect_url,
        "created_at": datetime.now(timezone.utc),
        "used": False,
        "used_at": None,
    }
    db.github_states.insert_one(document)
    return document


async def exchange_code_for_token(db: Database, code: str, state: str) -> Tuple[dict, Optional[str]]:
    _require_github_credentials()

    oauth_state = db.github_states.find_one({"_id": state, "used": False})
    if not oauth_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OAuth state")

    async with httpx.AsyncClient(timeout=10) as client:
        token_response = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GITHUB_REDIRECT_URI,
                "state": state,
            },
        )
    token_response.raise_for_status()
    token_data = token_response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub did not return an access token")

    token_type = token_data.get("token_type")
    scope = token_data.get("scope")

    async with httpx.AsyncClient(timeout=10) as client:
        user_response = await client.get(
            GITHUB_USER_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {access_token}",
            },
        )
    user_response.raise_for_status()
    user_data = user_response.json()

    connection_doc = {
        "_id": "primary",
        "access_token": access_token,
        "token_type": token_type,
        "scope": scope,
        "account_login": user_data.get("login"),
        "account_name": user_data.get("name"),
        "account_avatar_url": user_data.get("avatar_url"),
        "organization": user_data.get("company"),
        "connected_at": datetime.now(timezone.utc),
        "last_sync_status": "success",
        "last_sync_message": "GitHub OAuth token stored successfully.",
    }

    db.github_connection.replace_one({"_id": "primary"}, connection_doc, upsert=True)
    db.github_states.update_one(
        {"_id": state},
        {"$set": {"used": True, "used_at": datetime.now(timezone.utc)}},
    )

    redirect_url = oauth_state.get("redirect_url")
    return connection_doc, redirect_url
