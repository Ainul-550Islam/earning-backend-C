"""
Gamification Template Tags — Custom tags and filters for gamification UI.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from django import template
from django.utils.safestring import mark_safe
from django.utils.html import format_html

logger = logging.getLogger(__name__)
register = template.Library()


@register.filter(name="gamif_points_display")
def points_display(value: Any) -> str:
    """
    Format a points integer as a locale-style string with thousands separator.

    Usage: {{ user_points|gamif_points_display }}
    Returns "0" for invalid inputs instead of raising.
    """
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        logger.debug("gamif_points_display: cannot format value %r as integer.", value)
        return "0"


@register.filter(name="gamif_rank_suffix")
def rank_suffix(value: Any) -> str:
    """
    Append an ordinal suffix to a rank integer (1st, 2nd, 3rd, 4th...).

    Usage: {{ rank|gamif_rank_suffix }}
    """
    try:
        n = int(value)
    except (TypeError, ValueError):
        return str(value)

    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


@register.simple_tag(takes_context=True)
def gamif_user_points(context: dict, user: Any, cycle: Optional[Any] = None) -> int:
    """
    Return total awarded points for *user*, optionally scoped to *cycle*.

    Usage: {% gamif_user_points request.user cycle=active_contest_cycle %}

    Returns 0 on any error to keep templates safe.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return 0
    try:
        from ..services import get_user_total_points
        return get_user_total_points(
            user_id=user.pk,
            cycle_id=getattr(cycle, "pk", None) if cycle else None,
        )
    except Exception as exc:
        logger.warning("gamif_user_points tag error for user=%s: %s", getattr(user, "pk", "?"), exc)
        return 0


@register.inclusion_tag("gamification/tags/leaderboard_widget.html", takes_context=True)
def gamif_leaderboard_widget(context: dict, cycle: Optional[Any] = None, top_n: int = 10) -> dict:
    """
    Render a compact leaderboard widget for the given cycle.

    Requires template: gamification/tags/leaderboard_widget.html

    Usage: {% gamif_leaderboard_widget cycle=active_contest_cycle top_n=5 %}
    """
    entries = []
    if cycle is not None:
        try:
            from ..services import get_latest_snapshot
            snapshot = get_latest_snapshot(cycle_id=cycle.pk)
            if snapshot and snapshot.snapshot_data:
                entries = snapshot.snapshot_data[:max(1, int(top_n))]
        except Exception as exc:
            logger.warning("gamif_leaderboard_widget error: %s", exc)

    return {
        "cycle": cycle,
        "entries": entries,
        "request": context.get("request"),
    }
