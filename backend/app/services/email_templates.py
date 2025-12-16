"""
Email Template Renderer using Handlebars (pybars3).

This module provides utilities for rendering email templates with Handlebars syntax.
Templates are stored in app/templates/email/ directory.
"""

import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from pybars import Compiler
except ImportError:
    # Fallback if pybars3 is not installed
    Compiler = None

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "email"


class EmailTemplateRenderer:
    """
    Renders email templates using Handlebars (pybars3).

    Usage:
        renderer = EmailTemplateRenderer()
        html = renderer.render("rate_limit_exhausted", {
            "exhausted_tokens": 5,
            "total_tokens": 5,
            "next_reset_at": "14:30 UTC",
        })
    """

    def __init__(self, template_dir: Optional[Path] = None):
        self.template_dir = template_dir or TEMPLATE_DIR
        self.compiler = Compiler() if Compiler else None
        self._base_template = None

        # Default app URL (can be overridden via env)
        self.app_url = os.getenv("APP_URL", "http://localhost:3000")

    @lru_cache(maxsize=20)
    def _load_template(self, name: str) -> str:
        """Load a template file from disk (cached)."""
        template_path = self.template_dir / f"{name}.hbs"
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
        return template_path.read_text(encoding="utf-8")

    def _get_base_template(self):
        """Load and compile the base template."""
        if self._base_template is None and self.compiler:
            base_source = self._load_template("base")
            self._base_template = self.compiler.compile(base_source)
        return self._base_template

    def render(
        self,
        template_name: str,
        context: Dict[str, Any],
        subject: str = "",
    ) -> str:
        """
        Render an email template with the given context.

        Args:
            template_name: Name of the template (without .hbs extension)
            context: Dictionary of variables to pass to the template
            subject: Subject line for the email

        Returns:
            Rendered HTML string

        Raises:
            RuntimeError: If pybars3 is not installed
            FileNotFoundError: If template file not found
            Exception: If template rendering fails
        """
        if not self.compiler:
            raise RuntimeError(
                "pybars3 is not installed. Install it with: uv add pybars3"
            )

        import logging

        logger = logging.getLogger(__name__)

        # Load and compile content template
        content_source = self._load_template(template_name)
        content_template = self.compiler.compile(content_source)

        # Add common context variables
        full_context = {
            **context,
            "app_url": self.app_url,
            "year": datetime.now().year,
            "subject": subject,
        }

        # Render content
        rendered_content = content_template(full_context)

        # Wrap in base template
        base_template = self._get_base_template()
        if base_template:
            full_context["body"] = rendered_content
            return base_template(full_context)

        return rendered_content


# Singleton instance
_renderer: Optional[EmailTemplateRenderer] = None


def get_email_renderer() -> EmailTemplateRenderer:
    """Get the global email template renderer."""
    global _renderer
    if _renderer is None:
        _renderer = EmailTemplateRenderer()
    return _renderer


def render_email(
    template_name: str,
    context: Dict[str, Any],
    subject: str = "",
) -> str:
    """
    Convenience function to render an email template.

    Returns:
        Rendered HTML string
    """
    renderer = get_email_renderer()
    return renderer.render(template_name, context, subject)
