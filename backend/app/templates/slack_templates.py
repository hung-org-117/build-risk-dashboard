"""
Slack Block Kit Templates for notifications.

This module provides functions that generate Slack Block Kit message structures.
Each function returns a dict with 'blocks' and 'text' keys ready for sending.

Docs: https://api.slack.com/block-kit
"""

from typing import Any, Dict, List


def pipeline_failed(repo_name: str, build_id: str, error: str) -> Dict[str, Any]:
    """Slack template for pipeline failure notification."""
    error_preview = error[:150] + "..." if len(error) > 150 else error

    return {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔴 Pipeline Failed",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Repository:*\n{repo_name}"},
                    {"type": "mrkdwn", "text": f"*Build:*\n`{build_id[:8]}...`"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error:*\n```{error_preview}```",
                },
            },
        ],
        "text": f"Pipeline failed for {repo_name}",
    }


def scan_vulnerabilities_found(
    repo_name: str, scan_type: str, issues_count: int
) -> Dict[str, Any]:
    """Slack template for scan vulnerabilities notification."""
    return {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"⚠️ *{scan_type.capitalize()} Scan*: Found {issues_count} issues in `{repo_name}`",
                },
            }
        ],
        "text": f"Scan found {issues_count} issues in {repo_name}",
    }


def rate_limit_warning(
    token_label: str, remaining: int, reset_at: str
) -> Dict[str, Any]:
    """Slack template for rate limit warning notification."""
    return {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"⚠️ *GitHub Rate Limit Warning*\n"
                    f"Token `{token_label}` has {remaining} requests left. Resets at {reset_at}.",
                },
            }
        ],
        "text": f"Rate limit warning for token {token_label}",
    }


def rate_limit_exhausted(
    exhausted_tokens: int, total_tokens: int, reset_at: str
) -> Dict[str, Any]:
    """Slack template for rate limit exhausted (critical) notification."""
    return {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 GitHub Rate Limit Exhausted",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*All {exhausted_tokens}/{total_tokens} tokens are rate limited!*\n"
                    f"GitHub API calls are blocked.\n"
                    f"Next reset: `{reset_at}`",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "💡 *Actions:*\n"
                    "• Add more GitHub tokens at `/admin/settings`\n"
                    "• Wait for rate limit reset\n"
                    "• Reduce concurrent operations",
                },
            },
        ],
        "text": "CRITICAL: All GitHub tokens exhausted",
    }


def system_alert(title: str, message: str) -> Dict[str, Any]:
    """Slack template for generic system alert."""
    return {
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"ℹ️ *{title}*\n{message}"},
            }
        ],
        "text": title,
    }
