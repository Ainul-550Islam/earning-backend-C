"""
Gamification Middleware — Attaches current active ContestCycle to the request.

Usage:
    Add 'api.gamification.middleware.ActiveContestCycleMiddleware'
    to MIDDLEWARE in settings.py.

After this middleware runs, views can access:
    request.active_contest_cycle  → ContestCycle | None
"""

from __future__ import annotations

import logging
from typing import Callable

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


class ActiveContestCycleMiddleware:
    """
    Injects the current active ContestCycle onto every request object.

    The lookup is a cheap single-query operation. If no active cycle exists,
    request.active_contest_cycle is set to None.

    Failures are caught and logged; the request is never blocked by a
    gamification lookup error.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        if not callable(get_response):
            raise TypeError(
                f"get_response must be callable, got {type(get_response).__name__}."
            )
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            from .models import ContestCycle
            request.active_contest_cycle = ContestCycle.objects.get_current()
        except Exception as exc:
            logger.error(
                "ActiveContestCycleMiddleware: failed to fetch active cycle: %s", exc
            )
            request.active_contest_cycle = None

        response = self.get_response(request)
        return response
