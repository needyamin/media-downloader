"""URL-domain policy checks used by downloader workflows."""

from __future__ import annotations

from desktop_tools.app.config.runtime_flags import get_disabled_domain_match as _get_match


def get_blocked_domain(url: str, disabled_domains: list[str]) -> str | None:
    """Return the matching blocked domain for a URL when policy blocks it."""
    return _get_match(url, disabled_domains)

