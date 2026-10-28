"""
utils/http.py — Shared HTTP response helpers and base view class.

Fixes:
  - _err() was defined identically in both views.py and views_extra.py (Tech Debt #3)
  - _error_response() was defined in viewsets.py only
  - MessagingAPIView provides a base class so all views inherit these helpers

Usage:
    from .utils.http import _err, _error_response, MessagingAPIView

    class MyView(MessagingAPIView):
        def post(self, request):
            try:
                result = services.do_something()
                return Response(result)
            except SomeError as exc:
                return self._err(exc, 400)

    # Or as standalone helpers in viewsets:
    from .utils.http import _err, _error_response
    return _error_response(exc, status.HTTP_403_FORBIDDEN)
"""
from __future__ import annotations

import logging
from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


def _err(exc: Exception, http_status: int = None) -> Response:
    """
    Return a DRF Response for an exception, in a consistent shape.

    This is the canonical error-response helper for all messaging views.
    Previously duplicated in views.py and views_extra.py — now centralised here.

    Part 6 audit fix: this used to always return just {"detail": str(exc)}.
    views.py separately defined its own *local* _err() that shadowed this
    imported one (despite importing it right above the shadowing
    definition - almost certainly a leftover from before centralisation
    that never got cleaned up), and that local copy additionally included
    "error_type" - meaning error responses from views.py looked different
    from every other view/viewset in the same API. MessagingError.to_dict()
    (exceptions.py) already defines the richer, intended shape
    (error_type + code + detail) for the whole 42-class exception
    hierarchy; this now uses it when available, so every error response
    across the API is consistent regardless of which file's view raised it.

    Args:
        exc:         The exception (or any object whose str() is the detail message).
        http_status: HTTP status code. If omitted, uses exc.http_status when the
                     exception declares one (all MessagingError subclasses do —
                     see exceptions.py), otherwise defaults to 400 Bad Request.

    Returns:
        DRF Response with {"error_type", "code", "detail"} for a MessagingError,
        or plain {"detail": "..."} for any other exception type.
    """
    if http_status is None:
        http_status = getattr(exc, "http_status", 400)
    to_dict = getattr(exc, "to_dict", None)
    body = to_dict() if callable(to_dict) else {"detail": str(exc)}
    return Response(body, status=http_status)


def _error_response(exc: Exception, http_status: int = None) -> Response:
    """
    Alias for _err() using DRF status constants.

    Identical behaviour to _err() but accepts DRF status.HTTP_* constants
    by default, making it more readable in viewset action methods.

    Args:
        exc:         The exception.
        http_status: DRF status constant (e.g. status.HTTP_403_FORBIDDEN). If
                     omitted, uses exc.http_status when declared, else 400.

    Returns:
        Same response shape as _err() - see its docstring.
    """
    if http_status is None:
        http_status = getattr(exc, "http_status", status.HTTP_400_BAD_REQUEST)
    return _err(exc, http_status)


def _not_found(detail: str = "Not found.") -> Response:
    """Return a standard 404 response."""
    return Response({"detail": detail}, status=status.HTTP_404_NOT_FOUND)


def _forbidden(detail: str = "Access denied.") -> Response:
    """Return a standard 403 response."""
    return Response({"detail": detail}, status=status.HTTP_403_FORBIDDEN)


def _bad_request(detail: str) -> Response:
    """Return a standard 400 response."""
    return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)


def _no_content() -> Response:
    """Return a standard 204 No Content response."""
    return Response(status=status.HTTP_204_NO_CONTENT)


class MessagingAPIView(APIView):
    """
    Base class for all messaging APIViews.

    Provides:
      - self._err(exc, http_status)        — error response helper
      - self._error_response(exc, status)  — alias with DRF status constants
      - self._not_found(detail)            — 404 shortcut
      - self._forbidden(detail)            — 403 shortcut
      - self._bad_request(detail)          — 400 shortcut
      - self._no_content()                 — 204 shortcut

    Views can inherit from this instead of APIView to get these helpers
    as instance methods, avoiding the need to import them individually.
    """

    def _err(self, exc: Exception, http_status: int = 400) -> Response:
        """Return {"detail": str(exc)} with the given HTTP status."""
        return _err(exc, http_status)

    def _error_response(self, exc: Exception, http_status: int = 400) -> Response:
        """Alias for _err()."""
        return _error_response(exc, http_status)

    def _not_found(self, detail: str = "Not found.") -> Response:
        return _not_found(detail)

    def _forbidden(self, detail: str = "Access denied.") -> Response:
        return _forbidden(detail)

    def _bad_request(self, detail: str) -> Response:
        return _bad_request(detail)

    def _no_content(self) -> Response:
        return _no_content()


def safe_receiver_error_handler(signal_name: str, exc: Exception, **context: Any) -> None:
    """
    Standardised error logger for signal receivers.

    Called by @safe_receiver when a receiver raises an unhandled exception.
    Logs the signal name, exception, and any context kwargs provided.

    Args:
        signal_name: Name of the signal (e.g. "chat_message_sent").
        exc:         The exception that was raised.
        **context:   Optional context dict (e.g. message_id, chat_id).
    """
    ctx_str = ", ".join(f"{k}={v!r}" for k, v in context.items()) if context else ""
    logger.error(
        "Signal receiver error in '%s'%s: %s",
        signal_name,
        f" ({ctx_str})" if ctx_str else "",
        exc,
        exc_info=True,
    )


def make_safe_receiver(signal_name: str):
    """
    Decorator factory that wraps a signal receiver in a try/except block.

    Prevents any unhandled exception in a receiver from propagating and
    crashing the signal dispatch chain. All errors are logged via
    safe_receiver_error_handler().

    Usage:
        @receiver(chat_message_sent)
        @make_safe_receiver("chat_message_sent")
        def on_message_sent(sender, **kwargs):
            ...  # no try/except needed here

    Args:
        signal_name: Human-readable name for log messages.

    Returns:
        Decorator that wraps the receiver function.

    Notes:
        This decorator can be adopted incrementally for new receivers.
        Existing receivers with explicit try/except blocks can be left
        as-is — both patterns produce the same outcome.
    """
    import functools

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                safe_receiver_error_handler(signal_name, exc)
        return wrapper
    return decorator
