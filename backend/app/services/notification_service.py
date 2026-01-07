"""
Unified Notification Service - In-app and Gmail API notifications.

Channels:
- In-app: Always sent, stored in MongoDB for UI display
- Gmail: Gmail API (OAuth2) for critical alerts only

Gmail API Setup:
1. Create a project in Google Cloud Console
2. Enable Gmail API
3. Create OAuth 2.0 credentials (Desktop app)
4. Run: python -m app.services.gmail_api_service --setup
5. Set environment variables:
   - GOOGLE_CLIENT_ID: OAuth client ID
   - GOOGLE_CLIENT_SECRET: OAuth client secret
   - GMAIL_TOKEN_JSON: Token JSON from setup script

Channel Usage Guidelines:
┌─────────────────────────────────┬─────────┬─────────┐
│ Event Type                      │ In-App  │ Gmail   │
├─────────────────────────────────┼─────────┼─────────┤
│ Pipeline completed              │ ✓       │         │
│ Pipeline failed                 │ ✓       │         │
│ Dataset validation completed    │ ✓       │         │
│ Dataset enrichment completed    │ ✓       │         │
│ Scan vulnerabilities found      │ ✓       │         │
│ Rate limit WARNING              │ ✓       │         │
│ Rate limit EXHAUSTED (all)      │ ✓       │ ✓ *     │
│ System alerts                   │ ✓       │         │
└─────────────────────────────────┴─────────┴─────────┘
* Gmail only for critical alerts when all tokens are exhausted
"""

import logging
from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from pymongo.database import Database

from app.entities.notification import Notification, NotificationType
from app.repositories.notification import NotificationRepository
from app.services.email_templates import render_email

logger = logging.getLogger(__name__)


# =============================================================================
# NotificationService - CRUD operations for API Layer
# =============================================================================


class NotificationService:
    """
    Service for notification CRUD operations.

    Used by API layer following the layered architecture pattern:
    API -> Service -> Repository -> Database
    """

    def __init__(self, db: Database):
        self.db = db
        self.notification_repo = NotificationRepository(db)

    def list_notifications(
        self,
        user_id: ObjectId,
        skip: int = 0,
        limit: int = 20,
        unread_only: bool = False,
        cursor: str | None = None,
    ) -> tuple[list[Notification], int, int, str | None]:
        """
        List notifications for a user.

        Returns: (items, total, unread_count, next_cursor)
        """
        # If cursor is provided, we should typically ignore skip, but repo handles logic
        items, total = self.notification_repo.find_by_user(
            user_id, skip=skip, limit=limit, unread_only=unread_only, cursor_id=cursor
        )
        unread_count = self.notification_repo.count_unread(user_id)

        next_cursor = None
        if items and len(items) == limit:
            # We explicitly check against limit to determine if there might be more
            # The next cursor is the ID of the last item
            next_cursor = str(items[-1].id)

        return items, total, unread_count, next_cursor

    def get_unread_count(self, user_id: ObjectId) -> int:
        """Get the count of unread notifications for a user."""
        return self.notification_repo.count_unread(user_id)

    def mark_as_read(self, user_id: ObjectId, notification_id: str) -> bool:
        """
        Mark a single notification as read.

        Raises HTTPException if notification not found or not owned by user.
        """
        from fastapi import HTTPException

        notification = self.notification_repo.find_by_id(notification_id)
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")

        if notification.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        return self.notification_repo.mark_as_read(ObjectId(notification_id))

    def mark_all_as_read(self, user_id: ObjectId) -> int:
        """Mark all notifications as read for a user."""
        return self.notification_repo.mark_all_as_read(user_id)

    def create_notification(
        self,
        user_id: ObjectId,
        notification_type: NotificationType,
        title: str,
        message: str,
        link: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Notification:
        """Create a new notification."""
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            link=link,
            metadata=metadata,
        )
        return self.notification_repo.insert_one(notification)

    def notify_rate_limit_exhausted(
        self,
        retry_after: Optional[datetime] = None,
        task_name: Optional[str] = None,
    ) -> None:
        """
        Notify admins when all GitHub tokens are exhausted.

        Called from Celery tasks when GithubAllRateLimitError is raised after max retries.
        Sends in-app notifications to all admin users and Gmail alert.

        Args:
            retry_after: datetime when tokens will reset
            task_name: Name of the task that triggered the notification
        """
        from app.repositories.user import UserRepository
        from app.services.github.redis_token_pool import get_redis_token_pool

        # Get token pool status
        try:
            pool = get_redis_token_pool()
            pool_status = pool.get_pool_status()
            total_tokens = pool_status.get("total_tokens", 0)
            rate_limited = pool_status.get("rate_limited_tokens", 0)
        except Exception:
            total_tokens = 0
            rate_limited = 0

        reset_str = retry_after.strftime("%H:%M UTC") if retry_after else "unknown"

        # Find all admin users
        user_repo = UserRepository(self.db)
        admin_users = user_repo.find_by_role("admin")

        for admin in admin_users:
            try:
                self.create_notification(
                    user_id=admin.id,
                    notification_type=NotificationType.RATE_LIMIT_EXHAUSTED,
                    title="🚨 All GitHub Tokens Exhausted",
                    message=f"All {rate_limited}/{total_tokens} tokens are rate limited. "
                    f"Task '{task_name}' failed. Tokens reset at {reset_str}.",
                    link="/admin/settings",
                    metadata={
                        "rate_limited_tokens": rate_limited,
                        "total_tokens": total_tokens,
                        "next_reset_at": reset_str,
                        "task_name": task_name,
                    },
                )
            except Exception as e:
                logger.warning(
                    f"Failed to create notification for admin {admin.id}: {e}"
                )

        # Send Gmail alert to admins
        try:
            manager = get_notification_manager(self.db)
            admin_emails = [admin.email for admin in admin_users if admin.email]
            if admin_emails:
                html_body = render_email(
                    "rate_limit_exhausted",
                    {
                        "exhausted_tokens": rate_limited,
                        "total_tokens": total_tokens,
                        "next_reset_at": reset_str,
                        "task_name": task_name,
                    },
                    subject="🚨 CRITICAL: All GitHub Tokens Exhausted",
                )
                manager.send_gmail(
                    subject="🚨 CRITICAL: All GitHub Tokens Exhausted",
                    html_body=html_body,
                    to_recipients=admin_emails,
                )
        except Exception as e:
            logger.warning(f"Failed to send Gmail notification: {e}")


# =============================================================================
# Multi-Channel Notification Manager
# =============================================================================


class NotificationManager:
    """
    Unified notification manager that sends to multiple channels.

    Channels:
    - In-app: MongoDB stored notifications (always)
    - Gmail: Gmail API (OAuth2) for critical alerts (optional)
    """

    def __init__(
        self,
        db: Optional[Database] = None,
    ):
        self.db = db

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
    # Gmail Notifications
    # -------------------------------------------------------------------------

    def send_gmail(
        self,
        subject: str,
        to_recipients: List[str],
        html_body: str,
    ) -> bool:
        """
        Send an email via Gmail API (OAuth2).

        Args:
            subject: Email subject
            html_body: HTML body
            to_recipients: List of email addresses to send to.

        Returns:
            True if sent successfully, False otherwise
        """
        if len(to_recipients) == 0:
            logger.debug("No Gmail recipients specified")
            return False

        try:
            from app.services.gmail_api_service import (
                is_gmail_api_available,
                send_email_via_gmail_api,
            )

            if not is_gmail_api_available():
                logger.warning("Gmail API is not configured or available")
                return False

            return send_email_via_gmail_api(
                to=to_recipients,
                subject=subject,
                html_body=html_body,
            )
        except ImportError:
            logger.error(
                "Gmail API dependencies not installed. "
                "Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
            )
            return False
        except Exception as e:
            logger.error(f"Gmail API error: {e}")
            return False


_manager: Optional[NotificationManager] = None


def get_notification_manager(db: Optional[Database] = None) -> NotificationManager:
    """Get or create the global notification manager."""
    global _manager
    if _manager is None or (db and _manager.db is None):
        _manager = NotificationManager(db=db)
    return _manager


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
) -> Notification:
    """Pipeline failed - in-app only."""
    return create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.PIPELINE_FAILED,
        title="Pipeline Failed",
        message=f"Feature extraction for {repo_name} build #{build_id} failed: {error}",
        link="/admin/repos",
        metadata={"repo_name": repo_name, "build_id": build_id, "error": error},
    )


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
    builds_features_extracted: int,
    builds_total: int,
) -> Notification:
    """Dataset enrichment completed - in-app only."""
    return create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.DATASET_ENRICHMENT_COMPLETED,
        title="Dataset Enrichment Completed",
        message=f"Enrichment for '{dataset_name}' completed. {builds_features_extracted}/{builds_total} builds processed.",
        link=f"/admin/datasets/{dataset_id}",
        metadata={
            "dataset_id": dataset_id,
            "builds_features_extracted": builds_features_extracted,
            "builds_total": builds_total,
        },
    )


def notify_scan_vulnerabilities_found(
    db: Database,
    user_id: ObjectId,
    repo_name: str,
    scan_type: str,
    issues_count: int,
) -> Notification:
    """Scan found vulnerabilities - in-app only."""
    return create_notification(
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


# =============================================================================
# GitHub Token Rate Limit Notifications
# =============================================================================


def notify_rate_limit_exhausted(
    db: Database,
    user_id: ObjectId,
    exhausted_tokens: int,
    total_tokens: int,
    next_reset_at: Optional[datetime] = None,
    send_gmail: bool = True,
) -> Notification:
    """
    All tokens exhausted - CRITICAL - in-app + Gmail.

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

    # Gmail - for critical alerts using Handlebars template
    if send_gmail:
        manager = get_notification_manager()
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
            html_body=html_body,
            # TODO: Add to_recipients here
            to_recipients=["hunglaithe117@gmail.com"],
        )

    return notification


def notify_system_alert(
    db: Database,
    user_id: ObjectId,
    title: str,
    message: str,
) -> Notification:
    """Generic system alert - in-app only."""
    return create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.SYSTEM,
        title=title,
        message=message,
        link=None,
        metadata=None,
    )


def notify_system_error_to_admins(
    db: Database,
    source: str,
    message: str,
    correlation_id: Optional[str] = None,
) -> None:
    """
    Notify all admins about a system error.

    Called from MongoDBLogHandler when ERROR/CRITICAL logs occur.
    Uses in-app notifications only (not Gmail to avoid spam).

    Args:
        db: Database connection
        source: Log source/module name
        message: Error message (truncated to 500 chars)
        correlation_id: Correlation ID for Loki cross-reference
    """
    from app.repositories.user import UserRepository

    # Truncate message to avoid huge notifications
    truncated_message = message[:500] + "..." if len(message) > 500 else message

    # Find all admin users
    user_repo = UserRepository(db)
    admin_users = user_repo.find_by_role("admin")

    for admin in admin_users:
        try:
            create_notification(
                db=db,
                user_id=admin.id,
                type=NotificationType.SYSTEM,
                title=f"⚠️ System Error: {source}",
                message=truncated_message,
                link="/admin/monitoring",
                metadata={
                    "source": source,
                    "correlation_id": correlation_id,
                },
            )
        except Exception as e:
            logger.warning(
                f"Failed to create error notification for admin {admin.id}: {e}"
            )


# =============================================================================
# User-Facing Notifications
# =============================================================================


def notify_high_risk_detected(
    db: Database,
    user_id: ObjectId,
    repo_name: str,
    build_number: int,
    repo_id: str,
) -> Notification:
    """
    Alert user when HIGH risk build detected in their repo.

    Use when prediction phase finds a HIGH risk build for a repo
    that the user has access to via GitHub.
    """
    return create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.HIGH_RISK_DETECTED,
        title="⚠️ High Risk Build Detected",
        message=f"Build #{build_number} in {repo_name} predicted as HIGH risk.",
        link=f"/my-repos/{repo_id}/builds",
        metadata={
            "repo_name": repo_name,
            "build_number": build_number,
            "repo_id": repo_id,
            "risk_level": "HIGH",
        },
    )


def notify_prediction_ready(
    db: Database,
    user_id: ObjectId,
    repo_name: str,
    repo_id: str,
    high_count: int = 0,
    medium_count: int = 0,
    low_count: int = 0,
) -> Notification:
    """
    Notify user when predictions complete for their repo.

    Summary notification sent after prediction phase finishes.
    """
    total = high_count + medium_count + low_count
    message = f"{repo_name}: {total} builds analyzed."
    if high_count > 0:
        message += f" {high_count} HIGH risk."
    if medium_count > 0:
        message += f" {medium_count} MEDIUM risk."

    return create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.BUILD_PREDICTION_READY,
        title="🎯 Predictions Ready",
        message=message,
        link=f"/my-repos/{repo_id}/builds",
        metadata={
            "repo_name": repo_name,
            "repo_id": repo_id,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
            "total": total,
        },
    )


def notify_users_for_repo(
    db: Database,
    raw_repo_id: ObjectId,
    repo_name: str,
    repo_id: str,
    high_risk_builds: Optional[List[dict]] = None,
    prediction_summary: Optional[dict] = None,
) -> None:
    """
    Notify all users with access to a repository about predictions.

    Args:
        db: Database connection
        raw_repo_id: RawRepository ObjectId (for user access lookup)
        repo_name: Repository full name for display
        repo_id: ModelRepoConfig ID for links
        high_risk_builds: List of HIGH risk build dicts (max 3 alerts sent)
        prediction_summary: Dict with high/medium/low counts
    """
    from app.repositories.user import UserRepository

    user_repo = UserRepository(db)
    users = user_repo.find_users_with_repo_access(raw_repo_id)

    for user in users:
        try:
            # Summary notification
            if prediction_summary:
                notify_prediction_ready(
                    db=db,
                    user_id=user.id,
                    repo_name=repo_name,
                    repo_id=repo_id,
                    high_count=prediction_summary.get("high", 0),
                    medium_count=prediction_summary.get("medium", 0),
                    low_count=prediction_summary.get("low", 0),
                )

            # Alert for HIGH risk builds (limit to 3)
            if high_risk_builds:
                for build in high_risk_builds[:3]:
                    notify_high_risk_detected(
                        db=db,
                        user_id=user.id,
                        repo_name=repo_name,
                        build_number=build.get("build_number", 0),
                        repo_id=repo_id,
                    )
        except Exception as e:
            logger.warning(f"Failed to notify user {user.id} for repo {repo_name}: {e}")


# =============================================================================
# Admin Notifications - Model Pipeline
# =============================================================================


def notify_pipeline_completed_to_admins(
    db: Database,
    repo_name: str,
    predicted_count: int,
    failed_count: int,
    high_count: int = 0,
    medium_count: int = 0,
    low_count: int = 0,
) -> None:
    """
    Notify all admins when Model Pipeline prediction phase completes.

    Called from finalize_prediction task.
    """
    from app.repositories.user import UserRepository

    user_repo = UserRepository(db)
    admin_users = user_repo.find_by_role("admin")

    total = high_count + medium_count + low_count
    message = f"{repo_name}: {predicted_count}/{total} predicted."
    if failed_count > 0:
        message += f" {failed_count} failed."
    if high_count > 0:
        message += f" {high_count} HIGH risk."

    for admin in admin_users:
        try:
            create_notification(
                db=db,
                user_id=admin.id,
                type=NotificationType.PIPELINE_COMPLETED,
                title="✅ Pipeline Complete",
                message=message,
                link=f"/repositories",
                metadata={
                    "repo_name": repo_name,
                    "predicted": predicted_count,
                    "failed": failed_count,
                    "high": high_count,
                    "medium": medium_count,
                    "low": low_count,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to notify admin {admin.id}: {e}")


def notify_pipeline_failed_to_admins(
    db: Database,
    repo_name: str,
    error_message: str,
) -> None:
    """
    Notify all admins when Model Pipeline fails completely.
    """
    from app.repositories.user import UserRepository

    user_repo = UserRepository(db)
    admin_users = user_repo.find_by_role("admin")

    for admin in admin_users:
        try:
            create_notification(
                db=db,
                user_id=admin.id,
                type=NotificationType.PIPELINE_FAILED,
                title="❌ Pipeline Failed",
                message=f"{repo_name}: {error_message[:200]}",
                link=f"/repositories",
                metadata={
                    "repo_name": repo_name,
                    "error": error_message,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to notify admin {admin.id}: {e}")


# =============================================================================
# Admin Notifications - Dataset Enrichment
# =============================================================================


def notify_dataset_validation_to_admin(
    db: Database,
    user_id: ObjectId,
    dataset_name: str,
    dataset_id: str,
    repos_valid: int,
    builds_valid: int,
    builds_total: int,
) -> Notification:
    """
    Notify admin when dataset validation phase completes.

    Called from aggregate_validation_results task.
    """
    return create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.DATASET_VALIDATION_COMPLETED,
        title="✔️ Dataset Validation Complete",
        message=f"{dataset_name}: {repos_valid} repos, {builds_valid}/{builds_total} builds validated.",
        link=f"/projects/{dataset_id}",
        metadata={
            "dataset_name": dataset_name,
            "dataset_id": dataset_id,
            "repos_valid": repos_valid,
            "builds_valid": builds_valid,
            "builds_total": builds_total,
        },
    )


def notify_enrichment_completed_to_admin(
    db: Database,
    user_id: ObjectId,
    dataset_name: str,
    version_id: str,
    builds_features_extracted: int,
    builds_total: int,
    features_count: int = 0,
    scan_metrics_count: int = 0,
) -> Notification:
    """
    Notify admin when dataset enrichment fully completes (features + scans).

    Called from check_and_notify_enrichment_completed when all data is ready.
    """
    message = f"{dataset_name}: {builds_features_extracted}/{builds_total} builds."
    if features_count > 0:
        message += f" {features_count} features."
    if scan_metrics_count > 0:
        message += f" {scan_metrics_count} scan metrics."

    return create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.DATASET_ENRICHMENT_COMPLETED,
        title="🔧 Enrichment Complete",
        message=message,
        link=f"/projects/{version_id.split('/')[0] if '/' in version_id else version_id}",
        metadata={
            "dataset_name": dataset_name,
            "version_id": version_id,
            "builds_features_extracted": builds_features_extracted,
            "builds_total": builds_total,
            "features_count": features_count,
            "scan_metrics_count": scan_metrics_count,
        },
    )


def notify_enrichment_failed_to_admin(
    db: Database,
    version_id: str,
    error_message: str,
    completed_count: int = 0,
    failed_count: int = 0,
) -> None:
    """
    Notify dataset creator when enrichment processing chain fails.

    Called from handle_enrichment_processing_chain_error.
    """
    from app.repositories.dataset import DatasetRepository
    from app.repositories.dataset_version import DatasetVersionRepository

    version_repo = DatasetVersionRepository(db)
    version = version_repo.find_by_id(version_id)
    if not version:
        logger.warning(f"Version {version_id} not found for failure notification")
        return

    dataset_repo = DatasetRepository(db)
    dataset = dataset_repo.find_by_id(version.dataset_id)
    if not dataset:
        logger.warning(f"Dataset not found for version {version_id}")
        return

    message = f"{dataset.name}: {completed_count} completed, {failed_count} failed."
    if error_message:
        # Truncate long error messages
        short_error = (
            error_message[:100] + "..." if len(error_message) > 100 else error_message
        )
        message += f" Error: {short_error}"

    create_notification(
        db=db,
        user_id=dataset.user_id,
        type=NotificationType.DATASET_ENRICHMENT_COMPLETED,
        title="⚠️ Enrichment Failed",
        message=message,
        link=f"/projects/{str(dataset.id)}",
        metadata={
            "dataset_name": dataset.name,
            "version_id": version_id,
            "completed_count": completed_count,
            "failed_count": failed_count,
            "error": error_message,
            "status": "failed",
        },
    )


def check_and_notify_enrichment_completed(
    db: Database,
    version_id: str,
) -> bool:
    """
    Check if enrichment is fully complete (features + scan metrics) and send notification.

    Called from:
    1. finalize_enrichment - after features complete
    2. start_trivy_scan_for_version_commit - after each Trivy scan
    3. export_metrics_from_webhook - after each SonarQube webhook

    Returns True if notification was sent, False if still pending.
    """
    from app.repositories.dataset_version import DatasetVersionRepository

    version_repo = DatasetVersionRepository(db)
    version = version_repo.find_by_id(version_id)

    if not version:
        logger.warning(
            f"Version {version_id} not found for enrichment notification check"
        )
        return False

    # Check 1: Already notified? (avoid duplicates)
    if getattr(version, "enrichment_notified", False):
        logger.debug(f"Version {version_id} already notified")
        return False

    # Check 2: Features extraction complete?
    if not getattr(version, "feature_extraction_completed", False):
        logger.debug(f"Version {version_id} features not complete yet")
        return False

    # Check 3: All builds processed?
    builds_features_extracted = version.builds_features_extracted or 0
    builds_total = version.builds_total or 0
    if builds_total > 0 and builds_features_extracted < builds_total:
        logger.debug(
            f"Version {version_id} not all builds processed: "
            f"{builds_features_extracted}/{builds_total}"
        )
        return False

    # Check 4: Do we have any scans configured?
    scans_total = getattr(version, "scans_total", 0) or 0
    scans_completed = getattr(version, "scans_completed", 0) or 0
    scans_failed = getattr(version, "scans_failed", 0) or 0

    # If scans are configured, check if all done
    if scans_total > 0:
        scans_done = scans_completed + scans_failed
        if scans_done < scans_total:
            logger.debug(
                f"Version {version_id} scans not complete: "
                f"{scans_done}/{scans_total}"
            )
            return False

        # Mark scan extraction as complete
        if not getattr(version, "scan_extraction_completed", False):
            version_repo.mark_scan_extraction_completed(str(version_id))

    # All done! Send notification
    logger.info(f"Version {version_id} enrichment complete - sending notification")

    # Get dataset info for notification
    from app.repositories.dataset import DatasetRepository

    dataset_repo = DatasetRepository(db)
    dataset = dataset_repo.find_by_id(version.dataset_id)

    if dataset:
        notify_enrichment_completed_to_admin(
            db=db,
            user_id=dataset.user_id,
            dataset_name=dataset.name,
            version_id=str(version_id),
            builds_features_extracted=version.builds_features_extracted or 0,
            builds_total=version.builds_total or 0,
            scan_metrics_count=scans_completed,
        )

        # Mark as notified using repository method
        version_repo.mark_enrichment_notified(str(version_id))

    return True
