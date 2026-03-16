# =============================================================================
# version_control/middleware.py
# =============================================================================
"""
Version-check and maintenance-mode middleware.

Responsibilities:
  1. Read X-App-Version and X-App-Platform headers from every request.
  2. If a maintenance window is active, return 503 (unless the request
     carries a valid bypass token or the user is staff).
  3. Attach version/platform context to request for downstream use.
  4. Optionally add X-App-Update-Available response header so clients
     can prompt users proactively without a dedicated check call.

Design rules:
  - Never raises unhandled exceptions.
  - 503 response contains a JSON body with maintenance details.
  - Cache is used for all maintenance checks to keep overhead < 1 ms.
"""

from __future__ import annotations

import json
import logging
from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

from .constants import (
    MAINTENANCE_BYPASS_HEADER,
    MAINTENANCE_RESPONSE_STATUS,
    VERSION_HEADER_CLIENT,
    VERSION_HEADER_PLATFORM,
)
from .services import MaintenanceService

logger = logging.getLogger(__name__)

# Paths that are always allowed through (health checks, etc.)
_BYPASS_PATHS: tuple[str, ...] = getattr(
    settings,
    "VERSION_CONTROL_BYPASS_PATHS",
    ("/health/", "/metrics/", "/admin/"),
)


class VersionCheckMiddleware:
    """
    WSGI middleware for version context and maintenance mode enforcement.

    Add to settings.MIDDLEWARE *after* AuthenticationMiddleware so that
    request.user is available for staff bypass checks.

    Installation::

        MIDDLEWARE = [
            ...
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "api.version_control.middleware.VersionCheckMiddleware",
            ...
        ]
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # ----------------------------------------------------------------
        # Fast-path: always-allowed paths
        # ----------------------------------------------------------------
        if any(request.path_info.startswith(p) for p in _BYPASS_PATHS):
            return self.get_response(request)

        # ----------------------------------------------------------------
        # Extract version context from headers
        # ----------------------------------------------------------------
        client_version = _header(request, VERSION_HEADER_CLIENT, default="")
        platform       = _header(request, VERSION_HEADER_PLATFORM, default="").lower()

        # Attach to request for downstream views / viewsets
        request.app_version = client_version    # type: ignore[attr-defined]
        request.app_platform = platform         # type: ignore[attr-defined]

        # ----------------------------------------------------------------
        # Maintenance mode check
        # ----------------------------------------------------------------
        try:
            maintenance_response = self._check_maintenance(
                request=request, platform=platform or "web"
            )
            if maintenance_response is not None:
                return maintenance_response
        except Exception:
            logger.exception(
                "version_middleware.maintenance_check_error path=%s",
                request.path_info,
            )
            # On error, let the request through (fail open for maintenance checks)

        # ----------------------------------------------------------------
        # Process request normally
        # ----------------------------------------------------------------
        response: HttpResponse = self.get_response(request)

        # ----------------------------------------------------------------
        # Optionally add update-available header
        # ----------------------------------------------------------------
        if client_version and platform:
            self._maybe_add_update_header(response, platform, client_version)

        return response

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_maintenance(
        request: HttpRequest,
        platform: str,
    ) -> HttpResponse | None:
        """
        If maintenance is active and the request is not bypassed,
        return a 503 JsonResponse; otherwise return None.
        """
        # Staff users bypass maintenance mode
        user = getattr(request, "user", None)
        if user and getattr(user, "is_staff", False):
            return None

        # Explicit bypass token (for internal tools / staging checks)
        bypass_token = _header(request, MAINTENANCE_BYPASS_HEADER)
        if bypass_token:
            from .models import MaintenanceSchedule
            valid = MaintenanceSchedule.objects.currently_active().filter(
                bypass_token=bypass_token
            ).exists()
            if valid:
                return None

        if not MaintenanceService.is_active_for_platform(platform):
            return None

        # Build a descriptive 503 response
        from .models import MaintenanceSchedule
        schedule = (
            MaintenanceSchedule.objects.currently_active()
            .order_by("scheduled_end")
            .first()
        )
        body: dict = {
            "error":   "maintenance_mode",
            "message": "The service is currently undergoing maintenance.",
        }
        if schedule:
            body["title"]          = schedule.title
            body["description"]    = schedule.description
            body["scheduled_end"]  = schedule.scheduled_end.isoformat()

        logger.info(
            "maintenance.request_blocked path=%s platform=%s",
            request.path_info, platform,
        )
        return JsonResponse(body, status=MAINTENANCE_RESPONSE_STATUS)

    @staticmethod
    def _maybe_add_update_header(
        response: HttpResponse,
        platform: str,
        client_version: str,
    ) -> None:
        """
        Add X-App-Update-Available: true/false to the response so clients
        can show an update prompt without a dedicated API call.
        """
        try:
            from .services import VersionCheckService
            result = VersionCheckService.check(
                platform=platform, client_version=client_version
            )
            response["X-App-Update-Available"] = str(result["update_required"]).lower()
            if result.get("target_version"):
                response["X-App-Target-Version"] = result["target_version"]
        except Exception:
            pass   # header is best-effort; never break the response


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _header(request: HttpRequest, name: str, default: str = "") -> str:
    """
    Read a request header by its HTTP_ META key.
    e.g. "X-App-Version" → META["HTTP_X_APP_VERSION"]
    """
    key = "HTTP_" + name.upper().replace("-", "_")
    return request.META.get(key, default)
