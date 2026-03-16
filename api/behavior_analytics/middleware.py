# =============================================================================
# behavior_analytics/middleware.py
# =============================================================================
"""
Tracking middleware for the behavior_analytics application.

Responsibilities:
  1. Intercept every incoming request.
  2. Skip excluded paths (health checks, static files, etc.).
  3. Extract / generate a session ID and device type from request headers.
  4. Record a navigation node to the user's active UserPath *asynchronously*
     (enqueues a Celery task; never blocks the response).
  5. Attach analytics context to request for downstream use.

Design rules:
  - The middleware must NEVER raise an unhandled exception and crash the request.
  - All DB / Celery calls are wrapped in broad except blocks with logging.
  - Only authenticated users are tracked (anonymous users are skipped).
  - IP address extraction respects X-Forwarded-For with a configurable trust flag.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from .constants import (
    TRACKING_EXCLUDED_PATHS,
    TRACKING_HEADER_DEVICE,
    TRACKING_HEADER_SESSION,
)

logger = logging.getLogger(__name__)

# How many requests to buffer before flushing as a Celery batch.
_CLICK_BUFFER_SIZE: int = getattr(settings, "ANALYTICS_CLICK_BUFFER_SIZE", 20)

# Trust X-Forwarded-For header (True in production behind a load-balancer).
_TRUST_X_FORWARDED_FOR: bool = getattr(settings, "ANALYTICS_TRUST_X_FORWARDED_FOR", False)


def _is_excluded(path: str) -> bool:
    """Return True if `path` should NOT be tracked."""
    return any(path.startswith(exc) for exc in TRACKING_EXCLUDED_PATHS)


def _extract_ip(request: HttpRequest) -> str | None:
    """
    Extract the real client IP address.

    When _TRUST_X_FORWARDED_FOR is True (load-balanced environments),
    we take the leftmost IP from the X-Forwarded-For header.
    Otherwise we fall back to REMOTE_ADDR.
    """
    if _TRUST_X_FORWARDED_FOR:
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or None


def _get_or_generate_session_id(request: HttpRequest) -> str:
    """
    Return the session ID from the custom header; generate a UUID if absent.
    """
    raw = request.META.get(f"HTTP_{TRACKING_HEADER_SESSION.upper().replace('-', '_')}", "")
    if raw and len(raw) <= 128:
        return raw.strip()
    return str(uuid.uuid4())


def _get_device_type(request: HttpRequest) -> str:
    """
    Return the device type from the custom header; default to 'unknown'.
    """
    from .choices import DeviceType
    raw = request.META.get(
        f"HTTP_{TRACKING_HEADER_DEVICE.upper().replace('-', '_')}", ""
    ).strip().lower()
    if raw in DeviceType.values:
        return raw
    return DeviceType.UNKNOWN


class BehaviorTrackingMiddleware:
    """
    WSGI-compatible middleware that records navigation events.

    Installation (settings.py):
        MIDDLEWARE = [
            ...
            "api.behavior_analytics.middleware.BehaviorTrackingMiddleware",
            ...
        ]
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # ----------------------------------------------------------------
        # 1. Fast-path: skip excluded routes and anonymous users
        # ----------------------------------------------------------------
        if _is_excluded(request.path_info):
            return self.get_response(request)

        start_ts = time.monotonic()
        response = self.get_response(request)
        duration_ms = int((time.monotonic() - start_ts) * 1_000)

        # Do not track after response has been produced if user is anon
        if not (
            hasattr(request, "user")
            and request.user is not None
            and request.user.is_authenticated
        ):
            return response

        # ----------------------------------------------------------------
        # 2. Extract context
        # ----------------------------------------------------------------
        session_id  = _get_or_generate_session_id(request)
        device_type = _get_device_type(request)
        ip_address  = _extract_ip(request)
        user_agent  = request.META.get("HTTP_USER_AGENT", "")[:512]
        page_url    = request.build_absolute_uri(request.path_info)[:2048]

        # Attach to request for potential downstream use
        request.analytics_session_id = session_id    # type: ignore[attr-defined]
        request.analytics_device_type = device_type  # type: ignore[attr-defined]

        # ----------------------------------------------------------------
        # 3. Async: ensure/upsert the UserPath and append a node
        # ----------------------------------------------------------------
        try:
            self._track_navigation(
                user=request.user,
                session_id=session_id,
                device_type=device_type,
                ip_address=ip_address,
                user_agent=user_agent,
                page_url=page_url,
                http_method=request.method,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
        except Exception:
            # Tracking failures must NEVER affect the HTTP response.
            logger.exception(
                "tracking_middleware.error user_id=%s path=%s",
                request.user.pk, request.path_info,
            )

        return response

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _track_navigation(
        *,
        user,
        session_id: str,
        device_type: str,
        ip_address: str | None,
        user_agent: str,
        page_url: str,
        http_method: str,
        status_code: int,
        duration_ms: int,
    ) -> None:
        """
        Upsert the UserPath and enqueue a node-append task.

        We intentionally do NOT perform synchronous DB writes here to
        keep the middleware latency near-zero.  Instead we push a task.
        If Celery is unavailable we fall back to a fire-and-forget
        thread (acceptable data loss risk on degraded deployments).
        """
        from .tasks import process_click_batch  # local import to avoid circular

        node = {
            "url":         page_url,
            "type":        "navigation",
            "method":      http_method,
            "status":      status_code,
            "duration_ms": duration_ms,
            "ts":          int(time.time()),
        }

        # Enqueue node to a dedicated low-priority queue
        try:
            _enqueue_node.delay(
                user_id=str(user.pk),
                session_id=session_id,
                device_type=device_type,
                ip_address=ip_address or "",
                user_agent=user_agent,
                entry_url=page_url,
                node=node,
            )
        except Exception:
            logger.warning(
                "tracking_middleware.celery_unavailable user_id=%s; dropping node",
                user.pk,
            )


# ---------------------------------------------------------------------------
# Celery task used internally by the middleware
# ---------------------------------------------------------------------------

from celery import shared_task  # noqa: E402  (imported after class definition intentionally)


@shared_task(
    name="behavior_analytics.middleware._enqueue_node",
    max_retries=3,
    default_retry_delay=15,
    acks_late=True,
    ignore_result=True,
)
def _enqueue_node(
    *,
    user_id: str,
    session_id: str,
    device_type: str,
    ip_address: str,
    user_agent: str,
    entry_url: str,
    node: dict,
) -> None:
    """
    Upsert the UserPath for (user, session_id) and append `node`.
    Runs in the Celery worker, not in the web process.
    """
    from django.contrib.auth import get_user_model
    from .models import UserPath
    from .services import UserPathService
    from .choices import SessionStatus
    from .exceptions import DuplicateSessionError

    _User = get_user_model()
    try:
        user = _User.objects.get(pk=user_id)
    except _User.DoesNotExist:
        logger.warning("_enqueue_node.user_not_found user_id=%s", user_id)
        return

    # Ensure the path exists
    try:
        path = UserPath.objects.get(user=user, session_id=session_id)
    except UserPath.DoesNotExist:
        try:
            path = UserPathService.create_path(
                user=user,
                session_id=session_id,
                device_type=device_type,
                entry_url=entry_url,
                ip_address=ip_address or None,
                user_agent=user_agent,
                nodes=[],
            )
        except DuplicateSessionError:
            # Race condition — another worker beat us to it; re-fetch
            path = UserPath.objects.get(user=user, session_id=session_id)

    # Append node
    try:
        UserPathService.append_nodes(path=path, new_nodes=[node])
    except Exception:
        logger.exception(
            "_enqueue_node.append_failed user_id=%s session_id=%s",
            user_id, session_id,
        )
