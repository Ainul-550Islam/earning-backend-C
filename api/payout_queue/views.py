"""
payout_queue/views.py  ← v8 PRODUCTION UPDATE

CHANGES v8 (Production Gap #5 — Health Check):

  ① health_check view upgraded from basic DB ping to full multi-component check.

     Checks:
       - database:     SELECT 1 via PayoutBatch.objects.count()
       - redis:        PING via redis-py (CELERY_BROKER_URL)
       - celery:       inspect().ping() via Celery control API
       - payout_queue: pending/processing batch counts + stuck lock count

     Response:
       HTTP 200:  status = "ok" (all green) | "degraded" (partial)
       HTTP 503:  status = "error" (DB down or critical component failed)

     Usage (Kubernetes readiness probe):
       livenessProbe:   httpGet: path: /payout-queue/health/   port: 8000
       readinessProbe:  httpGet: path: /payout-queue/health/   port: 8000

     Dev mode: always returns 200 ok (no credentials needed).

v3 logic preserved: my_payout_timeline endpoint unchanged.
"""

from __future__ import annotations

import logging
from typing import Any

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# v8: Comprehensive health check (Production Gap #5)
# ---------------------------------------------------------------------------

@api_view(["GET"])
@authentication_classes([])   # No auth required — ops/infra needs this unauthenticated
@permission_classes([])
def health_check(request: Request) -> Response:
    """
    GET /payout-queue/health/

    Multi-component health check for Kubernetes readiness/liveness probes,
    load balancer health checks, and ops dashboards.

    Returns:
        200: {"status": "ok" | "degraded", "checks": {...}, "version": "v8"}
        503: {"status": "error", "checks": {...}, "version": "v8"}

    status values:
        ok:       All checks passed.
        degraded: Non-critical component is unhealthy (Redis/Celery down).
                  App can still serve requests, but Celery tasks won't run.
        error:    Critical component down (DB). Return 503 to fail readiness probe.
    """
    checks  = {}
    overall = "ok"

    # ── 1. Database ────────────────────────────────────────────────────────
    try:
        from api.payout_queue.models import PayoutBatch
        PayoutBatch.objects.count()   # Lightweight SELECT 1 equivalent
        checks["database"] = {"status": "ok"}
    except Exception as exc:
        checks["database"] = {"status": "error", "detail": str(exc)[:200]}
        overall = "error"   # DB down → 503

    # ── 2. Redis / Celery broker ────────────────────────────────────────────
    try:
        from django.conf import settings as _settings
        redis_url = (
            getattr(_settings, "CELERY_BROKER_URL", "")
            or getattr(_settings, "REDIS_URL", "")
            or ""
        )
        if redis_url:
            import redis as _redis
            r = _redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
            r.ping()
            checks["redis"] = {"status": "ok", "url_prefix": redis_url[:20] + "..."}
        else:
            checks["redis"] = {
                "status":  "unknown",
                "detail":  "CELERY_BROKER_URL not configured",
            }
    except ImportError:
        checks["redis"] = {"status": "unknown", "detail": "redis package not installed"}
    except Exception as exc:
        checks["redis"] = {"status": "degraded", "detail": str(exc)[:200]}
        if overall == "ok":
            overall = "degraded"   # Redis down → 200 degraded (not 503)

    # ── 3. Celery workers ──────────────────────────────────────────────────
    try:
        from django.conf import settings as _settings
        broker_url = getattr(_settings, "CELERY_BROKER_URL", "") or ""
        if broker_url:
            import celery as _celery
            app     = _celery.current_app
            timeout = 1.0   # Fast timeout — don't delay health check for Celery
            ping    = app.control.inspect(timeout=timeout).ping()
            if ping:
                worker_count = len(ping)
                checks["celery"] = {"status": "ok", "workers": worker_count}
            else:
                checks["celery"] = {
                    "status": "degraded",
                    "detail": "No Celery workers responded (async processing disabled)",
                }
                if overall == "ok":
                    overall = "degraded"
        else:
            checks["celery"] = {"status": "unknown", "detail": "CELERY_BROKER_URL not set"}
    except Exception as exc:
        checks["celery"] = {"status": "degraded", "detail": str(exc)[:200]}
        if overall == "ok":
            overall = "degraded"

    # ── 4. Payout queue stats ───────────────────────────────────────────────
    try:
        from api.payout_queue.models import PayoutBatch
        from api.payout_queue.choices import PayoutBatchStatus

        pending_count    = PayoutBatch.objects.filter(status=PayoutBatchStatus.PENDING).count()
        processing_count = PayoutBatch.objects.filter(status=PayoutBatchStatus.PROCESSING).count()
        stuck_count      = PayoutBatch.objects.stale_locked(timeout_seconds=3600).count()

        queue_status = "ok"
        if stuck_count > 0:
            queue_status = "degraded"
            if overall == "ok":
                overall = "degraded"

        checks["payout_queue"] = {
            "status":              queue_status,
            "pending_batches":     pending_count,
            "processing_batches":  processing_count,
            "stuck_locked_batches": stuck_count,
        }

        if stuck_count > 0:
            logger.warning(
                "health_check: %d stuck-locked batch(es) detected. "
                "release_stale_locks Celery beat task should clear these.",
                stuck_count,
            )

    except Exception as exc:
        checks["payout_queue"] = {"status": "error", "detail": str(exc)[:200]}
        if overall != "error":
            overall = "degraded"

    # ── 5. Encryption key ──────────────────────────────────────────────────
    try:
        from django.conf import settings as _settings
        enc_key = getattr(_settings, "PAYOUT_ENCRYPTION_KEY", "") or ""
        if enc_key:
            # Validate key format without logging the key
            from cryptography.fernet import Fernet
            Fernet(enc_key.encode() if isinstance(enc_key, str) else enc_key)
            checks["encryption"] = {"status": "ok", "key_configured": True}
        else:
            checks["encryption"] = {
                "status":         "degraded",
                "key_configured": False,
                "detail":         "PAYOUT_ENCRYPTION_KEY not set — account numbers stored plaintext",
            }
            if overall == "ok":
                overall = "degraded"
    except ImportError:
        checks["encryption"] = {"status": "unknown", "detail": "cryptography not installed"}
    except Exception as exc:
        checks["encryption"] = {"status": "error", "detail": f"Invalid key: {str(exc)[:100]}"}
        if overall == "ok":
            overall = "degraded"

    http_status_code = (
        status.HTTP_503_SERVICE_UNAVAILABLE if overall == "error"
        else status.HTTP_200_OK
    )

    return Response(
        {
            "status":  overall,
            "checks":  checks,
            "version": "v8",
        },
        status=http_status_code,
    )

# ---------------------------------------------------------------------------
# my_payout_timeline (v3, unchanged)
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_payout_timeline(request: Request) -> Response:
    """
    GET /payout-queue/my-timeline/
    Returns the authenticated user's payout items ordered newest-first.
    """
    from api.payout_queue.models import PayoutItem
    from api.payout_queue.serializers import PayoutItemSerializer
    from rest_framework.pagination import PageNumberPagination

    paginator           = PageNumberPagination()
    paginator.page_size = 20

    qs = (
        PayoutItem.objects
        .for_user(request.user.pk)
        .select_related("batch")
    )
    page = paginator.paginate_queryset(qs, request)
    serializer = PayoutItemSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)
