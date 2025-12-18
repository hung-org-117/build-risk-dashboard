"""
Gmail API Service - OAuth2-based email sending via Gmail API.

This module provides Gmail API integration as an alternative to SMTP.
It uses OAuth2 for authentication and requires a client_secret.json file
from Google Cloud Console.

Setup:
1. Create a project in Google Cloud Console
2. Enable Gmail API
3. Create OAuth 2.0 credentials (Desktop app)
4. Download client_secret.json and place in backend directory
5. Run the setup script to generate token.json
"""

import base64
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# Global cache for credentials to avoid refreshing on every request
_CACHED_CREDS = None


def _get_gmail_service():
    """
    Get authenticated Gmail API service.

    Returns:
        Gmail API service or None if not configured/available
    """
    global _CACHED_CREDS

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        import json
    except ImportError:
        logger.warning(
            "Gmail API dependencies not installed. "
            "Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )
        return None

    creds = _CACHED_CREDS

    # If no cached creds, try loading from Environment Variables
    if not creds and settings.GMAIL_TOKEN_JSON:
        try:
            token_info = json.loads(settings.GMAIL_TOKEN_JSON)
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
        except Exception as e:
            logger.warning(f"Failed to load Gmail token from environment: {e}")

    # Auto-Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            logger.info("Gmail API token expired, refreshing...")
            creds.refresh(Request())
        except Exception as e:
            logger.error(f"Failed to refresh Gmail token: {e}")
            creds = None

    # Update cache if we have valid creds
    if creds and creds.valid:
        _CACHED_CREDS = creds
    else:
        # If we failed to get/refresh valid creds, check config status for warning
        has_token_config = settings.GMAIL_TOKEN_JSON is not None
        if has_token_config:
            logger.warning(
                "Gmail API token is present but invalid/expired and could not be refreshed."
            )
        return None

    try:
        return build("gmail", "v1", credentials=creds)
    except Exception as e:
        logger.error(f"Failed to build Gmail service: {e}")
        return None


def send_email_via_gmail_api(
    to: List[str],
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    from_email: Optional[str] = None,
) -> bool:
    """
    Send email using Gmail API.

    Args:
        to: List of recipient email addresses
        subject: Email subject
        body: Plain text body
        html_body: Optional HTML body
        from_email: Sender email (uses authenticated user if not specified)

    Returns:
        True if sent successfully, False otherwise
    """
    service = _get_gmail_service()
    if not service:
        return False

    try:
        # Create message
        if html_body:
            message = MIMEMultipart("alternative")
            message.attach(MIMEText(body, "plain", "utf-8"))
            message.attach(MIMEText(html_body, "html", "utf-8"))
        else:
            message = MIMEText(body, "plain", "utf-8")

        message["To"] = ", ".join(to)
        message["Subject"] = f"[{settings.APP_NAME}] {subject}"

        if from_email:
            message["From"] = from_email

        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        # Send
        service.users().messages().send(
            userId="me", body={"raw": raw_message}
        ).execute()

        logger.info(f"Gmail API: Email sent to {len(to)} recipients: {subject}")
        return True

    except Exception as e:
        logger.error(f"Gmail API: Failed to send email: {e}")
        return False


def is_gmail_api_available() -> bool:
    """Check if Gmail API is configured and available."""
    return _get_gmail_service() is not None


def setup_gmail_api():
    """
    Interactive setup for Gmail API authorization.

    Run this once to authorize the application and generate token.json content.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Error: Gmail API dependencies not installed.")
        print(
            "Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )
        return False

    client_id = settings.GOOGLE_CLIENT_ID
    client_secret = settings.GOOGLE_CLIENT_SECRET

    if not client_id or not client_secret:
        print("Error: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set")
        print("in your environment variables to run this setup.")
        return False

    # Construct config from env vars
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": ["http://localhost"],
        }
    }

    print("Starting Gmail API authorization...")
    print("Please follow the instructions in the browser to authorize the app.")
    print()

    try:
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(port=8888)

        print()
        print("✓ Gmail API authorized successfully!")
        print("-" * 50)
        print("IMPORTANT: Copy the JSON content below")
        print("and set it as GMAIL_TOKEN_JSON environment variable:")
        print("-" * 50)
        print(creds.to_json())
        print("-" * 50)
        return True

    except Exception as e:
        print(f"Error during authorization: {e}")
        return False


if __name__ == "__main__":
    import sys

    if "--setup" in sys.argv:
        setup_gmail_api()
    else:
        print("Gmail API Service")
        print()
        print("Usage:")
        print("  python -m app.services.gmail_api_service --setup")
        print()
        print("Status:")
        print(f"  Gmail API available: {is_gmail_api_available()}")
