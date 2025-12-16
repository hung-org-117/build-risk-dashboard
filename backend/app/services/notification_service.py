"""
Unified Notification Service - In-app, Slack, and Gmail notifications.

Channels:
- In-app: Always sent, stored in MongoDB for UI display
- Slack: For urgent/critical alerts (failures, rate limits)
- Gmail: For summary/digest notifications (critical alerts only)

Gmail Setup:
1. Enable 2-Step Verification in your Google Account
2. Generate an App Password at https://myaccount.google.com/apppasswords
3. Set environment variables:
   - GMAIL_USER: your-email@gmail.com
   - GMAIL_APP_PASSWORD: your-16-character-app-password
   - GMAIL_RECIPIENTS: comma-separated list of recipients

Channel Usage Guidelines:
┌─────────────────────────────────┬─────────┬─────────┬─────────┐
│ Event Type                      │ In-App  │ Slack   │ Gmail   │
├─────────────────────────────────┼─────────┼─────────┼─────────┤
│ Pipeline completed              │ ✓       │         │         │
│ Pipeline failed                 │ ✓       │ ✓       │         │
│ Dataset validation completed    │ ✓       │         │         │
│ Dataset enrichment completed    │ ✓       │         │         │
│ Scan vulnerabilities found      │ ✓       │ ✓       │         │
│ Rate limit WARNING              │ ✓       │ ✓       │         │
│ Rate limit EXHAUSTED (all)      │ ✓       │ ✓       │ ✓ *     │
│ System alerts                   │ ✓       │ ✓       │         │
└─────────────────────────────────┴─────────┴─────────┴─────────┘
* Gmail only for critical alerts when all tokens are exhausted
"""

import logging
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict, List, Optional

import httpx
from bson import ObjectId
from pymongo.database import Database

from app.config import settings
from app.entities.notification import Notification, NotificationType
from app.repositories.notification import NotificationRepository
from app.services.email_templates import render_email
from app.services import slack_templates

logger = logging.getLogger(__name__)


# =============================================================================
# Multi-Channel Notification Manager
# =============================================================================


class NotificationManager:
    """
    Unified notification manager that sends to multiple channels.

    Channels:
    - In-app: MongoDB stored notifications (always)
    - Slack: Webhook for urgent alerts
    - Gmail: SMTP for critical alerts (optional)
    """

    def __init__(
        self,
        db: Optional[Database] = None,
        slack_webhook_url: Optional[str] = None,
        gmail_enabled: Optional[bool] = None,
        gmail_user: Optional[str] = None,
        gmail_app_password: Optional[str] = None,
        gmail_recipients: Optional[List[str]] = None,
    ):
        self.db = db

        # Slack config - from settings or override
        self.slack_webhook_url = slack_webhook_url or settings.SLACK_WEBHOOK_URL

        # Gmail config (using App Password) - from settings or override
        self.gmail_enabled = (
            gmail_enabled
            if gmail_enabled is not None
            else settings.GMAIL_NOTIFICATIONS_ENABLED
        )
        self.gmail_user = gmail_user or settings.GMAIL_USER
        self.gmail_app_password = gmail_app_password or settings.GMAIL_APP_PASSWORD
        self.gmail_recipients = gmail_recipients or list(settings.GMAIL_RECIPIENTS)

    def _parse_recipients(self, recipients_str: str) -> List[str]:
        """Parse comma-separated email recipients."""
        if not recipients_str:
            return []
        return [r.strip() for r in recipients_str.split(",") if r.strip()]

    # -------------------------------------------------------------------------
    # In-App Notifications (MongoDB)
    # -------------------------------------------------------------------------

    def create_in_app(
        self,
        user_id: ObjectId,
        type: NotificationType,
        title: str,
        message: str,
        link: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[Notification]:
        """Create an in-app notification stored in MongoDB."""
        if not self.db:
            logger.warning("Database not configured for in-app notifications")
            return None

        repo = NotificationRepository(self.db)
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            link=link,
            metadata=metadata,
        )
        return repo.insert_one(notification)

    # -------------------------------------------------------------------------
    # Slack Notifications
    # -------------------------------------------------------------------------

    async def send_slack(self, blocks: List[Dict[str, Any]], text: str = "") -> bool:
        """Send a Slack message via Incoming Webhook."""
        if not self.slack_webhook_url:
            logger.debug("Slack webhook not configured")
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.slack_webhook_url,
                    json={"blocks": blocks, "text": text},
                )
                if response.status_code == 200:
                    logger.info("Slack notification sent")
                    return True
                else:
                    logger.warning(f"Slack failed: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"Slack error: {e}")
            return False

    def send_slack_sync(self, blocks: List[Dict[str, Any]], text: str = "") -> bool:
        """Synchronous Slack send for use in non-async contexts."""
        if not self.slack_webhook_url:
            return False

        try:
            import httpx

            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    self.slack_webhook_url,
                    json={"blocks": blocks, "text": text},
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Slack sync error: {e}")
            return False

    # -------------------------------------------------------------------------
    # Gmail Notifications
    # -------------------------------------------------------------------------

    def send_gmail(
        self,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        recipients: Optional[List[str]] = None,
    ) -> bool:
        """
        Send an email via Gmail using App Password.

        Args:
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            recipients: List of email addresses to send to.
                        If None, uses self.gmail_recipients from config.

        Gmail SMTP Settings:
        - Host: smtp.gmail.com
        - Port: 587 (TLS) or 465 (SSL)
        - Auth: Gmail address + App Password (NOT regular password)

        To generate App Password:
        1. Go to https://myaccount.google.com/apppasswords
        2. Select "Mail" and your device
        3. Copy the 16-character password
        """
        if not self.gmail_enabled or not self.gmail_user or not self.gmail_app_password:
            logger.debug("Gmail not configured or disabled")
            return False

        # Use provided recipients or fall back to config
        to_recipients = recipients if recipients else self.gmail_recipients
        if not to_recipients:
            logger.debug("No Gmail recipients specified")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[BuildGuard] {subject}"
            msg["From"] = self.gmail_user
            msg["To"] = ", ".join(to_recipients)

            msg.attach(MIMEText(body, "plain", "utf-8"))
            if html_body:
                msg.attach(MIMEText(html_body, "html", "utf-8"))

            # Gmail SMTP with TLS
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.gmail_user, self.gmail_app_password)
                server.sendmail(self.gmail_user, to_recipients, msg.as_string())

            logger.info(f"Gmail sent to {len(to_recipients)} recipients: {subject}")
            return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error(
                f"Gmail authentication failed. Make sure you're using an App Password, "
                f"not your regular Google password. Error: {e}"
            )
            return False
        except Exception as e:
            logger.error(f"Gmail error: {e}")
            return False


# =============================================================================
# Singleton Instance
# =============================================================================

_manager: Optional[NotificationManager] = None


def get_notification_manager(db: Optional[Database] = None) -> NotificationManager:
    """Get or create the global notification manager."""
    global _manager
    if _manager is None or (db and _manager.db is None):
        _manager = NotificationManager(db=db)
    return _manager


# =============================================================================
# In-App Only Helpers (Backward Compatible)
# =============================================================================


def create_notification(
    db: Database,
    user_id: ObjectId,
    type: NotificationType,
    title: str,
    message: str,
    link: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Notification:
    """Create an in-app notification for a user."""
    repo = NotificationRepository(db)
    notification = Notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        link=link,
        metadata=metadata,
    )
    return repo.insert_one(notification)


# =============================================================================
# Event-Specific Notification Functions
# =============================================================================


def notify_pipeline_completed(
    db: Database,
    user_id: ObjectId,
    repo_name: str,
    build_id: str,
    feature_count: int,
) -> Notification:
    """Pipeline completed - in-app only (not urgent)."""
    return create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.PIPELINE_COMPLETED,
        title="Pipeline Completed",
        message=f"Feature extraction for {repo_name} build #{build_id} completed. {feature_count} features extracted.",
        link="/admin/repos",
        metadata={
            "repo_name": repo_name,
            "build_id": build_id,
            "feature_count": feature_count,
        },
    )


def notify_pipeline_failed(
    db: Database,
    user_id: ObjectId,
    repo_name: str,
    build_id: str,
    error: str,
    send_slack: bool = True,
) -> Notification:
    """Pipeline failed - in-app + Slack (urgent)."""
    notification = create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.PIPELINE_FAILED,
        title="Pipeline Failed",
        message=f"Feature extraction for {repo_name} build #{build_id} failed: {error}",
        link="/admin/repos",
        metadata={"repo_name": repo_name, "build_id": build_id, "error": error},
    )

    # Send to Slack for urgent visibility
    if send_slack:
        manager = get_notification_manager()
        slack_msg = slack_templates.pipeline_failed(repo_name, build_id, error)
        manager.send_slack_sync(blocks=slack_msg["blocks"], text=slack_msg["text"])

    return notification


def notify_dataset_validation_completed(
    db: Database,
    user_id: ObjectId,
    dataset_name: str,
    dataset_id: str,
    repos_valid: int,
    repos_invalid: int,
) -> Notification:
    """Dataset validation completed - in-app only."""
    return create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.DATASET_VALIDATION_COMPLETED,
        title="Dataset Validation Completed",
        message=f"Validation for '{dataset_name}' completed. {repos_valid} valid, {repos_invalid} invalid repos.",
        link=f"/admin/datasets/{dataset_id}",
        metadata={
            "dataset_id": dataset_id,
            "repos_valid": repos_valid,
            "repos_invalid": repos_invalid,
        },
    )


def notify_dataset_enrichment_completed(
    db: Database,
    user_id: ObjectId,
    dataset_name: str,
    dataset_id: str,
    enriched_rows: int,
    total_rows: int,
) -> Notification:
    """Dataset enrichment completed - in-app only."""
    return create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.DATASET_ENRICHMENT_COMPLETED,
        title="Dataset Enrichment Completed",
        message=f"Enrichment for '{dataset_name}' completed. {enriched_rows}/{total_rows} rows enriched.",
        link=f"/admin/datasets/{dataset_id}",
        metadata={
            "dataset_id": dataset_id,
            "enriched_rows": enriched_rows,
            "total_rows": total_rows,
        },
    )


def notify_scan_vulnerabilities_found(
    db: Database,
    user_id: ObjectId,
    repo_name: str,
    scan_type: str,
    issues_count: int,
    send_slack: bool = True,
) -> Notification:
    """Scan found vulnerabilities - in-app + Slack (security concern)."""
    notification = create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.SCAN_VULNERABILITIES_FOUND,
        title=f"{scan_type.capitalize()} Scan: Issues Found",
        message=f"{scan_type.capitalize()} scan for {repo_name} found {issues_count} issues.",
        link="/admin/repos",
        metadata={
            "repo_name": repo_name,
            "scan_type": scan_type,
            "issues_count": issues_count,
        },
    )

    if send_slack:
        manager = get_notification_manager()
        slack_msg = slack_templates.scan_vulnerabilities_found(
            repo_name, scan_type, issues_count
        )
        manager.send_slack_sync(blocks=slack_msg["blocks"], text=slack_msg["text"])

    return notification


# =============================================================================
# GitHub Token Rate Limit Notifications
# =============================================================================


def notify_rate_limit_warning(
    db: Database,
    user_id: ObjectId,
    token_label: str,
    remaining: int,
    reset_at: datetime,
    send_slack: bool = True,
) -> Notification:
    """
    Single token rate limit warning - in-app + Slack.

    Use when a token is running low but not exhausted.
    """
    reset_str = reset_at.strftime("%H:%M UTC") if reset_at else "soon"

    notification = create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.RATE_LIMIT_WARNING,
        title="GitHub Rate Limit Warning",
        message=f"Token '{token_label}' has only {remaining} requests remaining. Resets at {reset_str}.",
        link="/admin/settings",
        metadata={
            "token_label": token_label,
            "remaining": remaining,
            "reset_at": reset_str,
        },
    )

    if send_slack:
        manager = get_notification_manager()
        slack_msg = slack_templates.rate_limit_warning(
            token_label, remaining, reset_str
        )
        manager.send_slack_sync(blocks=slack_msg["blocks"], text=slack_msg["text"])

    return notification


def notify_rate_limit_exhausted(
    db: Database,
    user_id: ObjectId,
    exhausted_tokens: int,
    total_tokens: int,
    next_reset_at: Optional[datetime] = None,
    send_slack: bool = True,
    send_gmail: bool = True,
) -> Notification:
    """
    All tokens exhausted - CRITICAL - in-app + Slack + Gmail.

    Use when ALL tokens are rate limited and the system cannot make GitHub API calls.
    This is critical because it blocks all data ingestion.
    """
    reset_str = next_reset_at.strftime("%H:%M UTC") if next_reset_at else "unknown"

    notification = create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.RATE_LIMIT_EXHAUSTED,
        title="🚨 All GitHub Tokens Exhausted",
        message=f"All {exhausted_tokens}/{total_tokens} tokens are rate limited. GitHub API calls blocked until {reset_str}.",
        link="/admin/settings",
        metadata={
            "exhausted_tokens": exhausted_tokens,
            "total_tokens": total_tokens,
            "next_reset_at": reset_str,
        },
    )

    manager = get_notification_manager()

    # Slack - urgent
    if send_slack:
        slack_msg = slack_templates.rate_limit_exhausted(
            exhausted_tokens, total_tokens, reset_str
        )
        manager.send_slack_sync(blocks=slack_msg["blocks"], text=slack_msg["text"])

    # Gmail - for critical alerts using Handlebars template
    if send_gmail:
        html_body = render_email(
            "rate_limit_exhausted",
            {
                "exhausted_tokens": exhausted_tokens,
                "total_tokens": total_tokens,
                "next_reset_at": reset_str,
            },
            subject="🚨 CRITICAL: All GitHub Tokens Exhausted",
        )
        manager.send_gmail(
            subject="🚨 CRITICAL: All GitHub Tokens Exhausted",
            body="",  # HTML only
            html_body=html_body,
        )

    return notification


def notify_system_alert(
    db: Database,
    user_id: ObjectId,
    title: str,
    message: str,
    send_slack: bool = False,
) -> Notification:
    """Generic system alert - in-app + optional Slack."""
    notification = create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.SYSTEM,
        title=title,
        message=message,
        link=None,
        metadata=None,
    )

    if send_slack:
        manager = get_notification_manager()
        slack_msg = slack_templates.system_alert(title, message)
        manager.send_slack_sync(blocks=slack_msg["blocks"], text=slack_msg["text"])

    return notification
