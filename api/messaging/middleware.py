"""
Messaging Middleware — Injects unread inbox count onto request.
"""
from __future__ import annotations

import logging
from typing import Callable
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


class InboxUnreadCountMiddleware:
    """
    Injects request.unread_inbox_count for authenticated users.
    Uses cache to avoid DB hit on every request.
    Never blocks the request on failure.
    """

    def __init__(self, get_response: Callable) -> None:
        if not callable(get_response):
            raise TypeError(f"get_response must be callable, got {type(get_response).__name__}.")
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.unread_inbox_count = 0
        if hasattr(request, "user") and getattr(request.user, "is_authenticated", False):
            try:
                from django.core.cache import cache
                cache_key = f"inbox_unread:{request.user.pk}"
                count = cache.get(cache_key)
                if count is None:
                    from .models import UserInbox
                    count = UserInbox.objects.unread_count(request.user.pk)
                    cache.set(cache_key, count, timeout=60)
                request.unread_inbox_count = count
            except Exception as exc:
                logger.error("InboxUnreadCountMiddleware: failed: %s", exc)
        return self.get_response(request)
