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

# Token file path (relative to backend directory)
TOKEN_FILE = Path(__file__).parent.parent.parent / "gmail_token.json"
CREDENTIALS_FILE = Path(__file__).parent.parent.parent / "gmail_credentials.json"


def _get_gmail_service():
    """
    Get authenticated Gmail API service.

    Returns:
        Gmail API service or None if not configured/available
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        logger.warning(
            "Gmail API dependencies not installed. "
            "Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )
        return None

    if not CREDENTIALS_FILE.exists():
        logger.debug(f"Gmail credentials file not found: {CREDENTIALS_FILE}")
        return None

    creds = None

    # Load existing token if available
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception as e:
            logger.warning(f"Failed to load Gmail token: {e}")

    # Refresh or get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Failed to refresh Gmail token: {e}")
                creds = None

        if not creds:
            # Need to run authorization flow
            logger.warning(
                "Gmail API not authorized. Run the setup script to authorize: "
                "python -m app.services.gmail_api_service --setup"
            )
            return None

    # Save the token for future use
    if creds:
        try:
            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())
        except Exception as e:
            logger.warning(f"Failed to save Gmail token: {e}")

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

    Run this once to authorize the application and generate token.json.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Error: Gmail API dependencies not installed.")
        print(
            "Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )
        return False

    if not CREDENTIALS_FILE.exists():
        print(f"Error: Credentials file not found: {CREDENTIALS_FILE}")
        print("Please download OAuth 2.0 credentials from Google Cloud Console")
        print("and save as 'gmail_credentials.json' in the backend directory.")
        return False

    print("Starting Gmail API authorization...")
    print(f"Credentials file: {CREDENTIALS_FILE}")
    print(f"Token will be saved to: {TOKEN_FILE}")
    print()

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
        creds = flow.run_local_server(port=8888)

        # Save the credentials
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

        print()
        print("✓ Gmail API authorized successfully!")
        print(f"✓ Token saved to: {TOKEN_FILE}")
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
        print(
            f"  Credentials file: {CREDENTIALS_FILE} - {'EXISTS' if CREDENTIALS_FILE.exists() else 'NOT FOUND'}"
        )
        print(
            f"  Token file: {TOKEN_FILE} - {'EXISTS' if TOKEN_FILE.exists() else 'NOT FOUND'}"
        )
        print(f"  Gmail API available: {is_gmail_api_available()}")
