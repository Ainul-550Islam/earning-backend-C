"""
Gamification Context Processors — Injects gamification data into template context.
"""

from __future__ import annotations

import logging
from typing import Any

from django.http import HttpRequest

logger = logging.getLogger(__name__)


def active_contest_cycle(request: HttpRequest) -> dict[str, Any]:
    """
    Inject the current active ContestCycle into template context.

    Uses request.active_contest_cycle if already set by middleware,
    otherwise falls back to a DB lookup.

    Context variables added:
        active_contest_cycle — ContestCycle | None
    """
    cycle = getattr(request, "active_contest_cycle", _SENTINEL)
    if cycle is _SENTINEL:
        try:
            from .models import ContestCycle
            cycle = ContestCycle.objects.get_current()
        except Exception as exc:
            logger.error(
                "active_contest_cycle context processor: failed to fetch cycle: %s", exc
            )
            cycle = None
    return {"active_contest_cycle": cycle}


_SENTINEL = object()  # distinct from None to detect missing attribute
