# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook System Middleware
middleware.py

Components:
    WebhookRequestLoggingMiddleware  — Structured request/response audit trail.
    WebhookSecurityHeadersMiddleware — Enforce security headers on all responses.
    WebhookTenantMiddleware          — Attach tenant_id from JWT/header to request.
"""

import logging
import time
import uuid

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("ainul.webhooks.middleware")


# ─────────────────────────────────────────────────────────────────────────────
#  1.  REQUEST LOGGING
# ─────────────────────────────────────────────────────────────────────────────

class WebhookRequestLoggingMiddleware(MiddlewareMixin):
    """
    Structured request/response logging for every /webhooks/* endpoint.

    Logs:
        - request_id   (UUID per request, attached to request object)
        - method, path, status_code
        - authenticated user (or 'anonymous')
        - response time in ms

    Usage (settings.py):
        MIDDLEWARE += ['api.webhooks.middleware.WebhookRequestLoggingMiddleware']
    """

    WEBHOOK_PREFIX = "/webhooks"

    def process_request(self, request):
        # Attach a unique request ID for log correlation
        request.webhook_request_id = str(uuid.uuid4())
        request.webhook_start_time = time.monotonic()

    def process_response(self, request, response):
        # Only log webhook paths
        if not request.path.startswith(self.WEBHOOK_PREFIX):
            return response

        elapsed_ms = round(
            (time.monotonic() - getattr(request, "webhook_start_time", time.monotonic())) * 1000,
            2,
        )
        user = getattr(request, "user", None)
        user_id = str(user.pk) if user and user.is_authenticated else "anonymous"

        logger.info(
            "webhook_request "
            "request_id=%s method=%s path=%s status=%s user=%s duration_ms=%s",
            getattr(request, "webhook_request_id", "-"),
            request.method,
            request.path,
            response.status_code,
            user_id,
            elapsed_ms,
        )
        # Forward request ID in response so clients can correlate
        response["X-Request-ID"] = getattr(request, "webhook_request_id", "-")
        return response

    def process_exception(self, request, exception):
        if not request.path.startswith(self.WEBHOOK_PREFIX):
            return None
        logger.exception(
            "webhook_unhandled_exception request_id=%s path=%s exc=%s",
            getattr(request, "webhook_request_id", "-"),
            request.path,
            exception,
        )
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  2.  SECURITY HEADERS
# ─────────────────────────────────────────────────────────────────────────────

class WebhookSecurityHeadersMiddleware(MiddlewareMixin):
    """
    Attach hardened security headers to every webhook API response.

    Usage (settings.py):
        MIDDLEWARE += ['api.webhooks.middleware.WebhookSecurityHeadersMiddleware']
    """

    def process_response(self, request, response):
        if not request.path.startswith("/webhooks"):
            return response
        response["X-Content-Type-Options"]  = "nosniff"
        response["X-Frame-Options"]         = "DENY"
        response["Referrer-Policy"]         = "strict-origin-when-cross-origin"
        response["Cache-Control"]           = "no-store, no-cache, must-revalidate"
        response["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


# ─────────────────────────────────────────────────────────────────────────────
#  3.  TENANT RESOLUTION
# ─────────────────────────────────────────────────────────────────────────────

class WebhookTenantMiddleware(MiddlewareMixin):
    """
    Resolve tenant_id from:
        1. X-Tenant-ID header (service-to-service)
        2. JWT 'tenant_id' claim  (when SimpleJWT is used)
        3. request.user.profile.tenant_id (fallback, if profile exists)

    Attaches ``request.tenant_id`` (str | None) for use by views/services.

    Usage (settings.py):
        MIDDLEWARE += ['api.webhooks.middleware.WebhookTenantMiddleware']
    """

    def process_request(self, request):
        tenant_id = None

        # 1. Explicit header (service calls)
        header = request.META.get("HTTP_X_TENANT_ID")
        if header:
            tenant_id = header.strip()

        # 2. JWT claim (SimpleJWT sets request.auth as validated token payload)
        if not tenant_id:
            token_payload = getattr(request, "auth", None)
            if isinstance(token_payload, dict):
                tenant_id = token_payload.get("tenant_id")

        # 3. User profile fallback
        if not tenant_id:
            user = getattr(request, "user", None)
            if user and user.is_authenticated:
                profile = getattr(user, "profile", None)
                tenant_id = getattr(profile, "tenant_id", None)

        request.tenant_id = tenant_id
