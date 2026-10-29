"""
Unauthenticated liveness / readiness probe endpoint.

WHY THIS EXISTS:
  The Dockerfile HEALTHCHECK pings an HTTP endpoint to decide whether the
  container is healthy.  All other telemetry endpoints require authentication,
  so a plain `curl` from the Docker daemon would get HTTP 401 and mark the
  container permanently unhealthy.

  This view requires NO authentication and NO permissions.  It returns HTTP 200
  as long as Django can handle a request (i.e. the process is alive and the DB
  connection pool is responding).

URL (added in urls.py):
  GET /ping/         → liveness probe  (no DB hit)
  GET /readiness/    → readiness probe (DB + cache hit)

Usage in Dockerfile:
  HEALTHCHECK CMD curl -f http://localhost:8000/ping/ || exit 1

Usage in Kubernetes:
  livenessProbe:
    httpGet: { path: /ping/, port: 8000 }
  readinessProbe:
    httpGet: { path: /readiness/, port: 8000 }
"""
import logging

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class PingView(APIView):
    """
    GET /ping/

    Liveness probe — returns 200 immediately.  No DB, no cache.
    Confirms the Django process is alive and can handle HTTP.
    """
    authentication_classes = []   # no auth attempted
    permission_classes     = [AllowAny]
    throttle_classes       = []   # don't count probe traffic against rate limits

    def get(self, request: Request, *args, **kwargs) -> Response:
        return Response({
            'status':  'ok',
            'version': getattr(settings, 'APP_VERSION', 'unknown'),
        })


class ReadinessView(APIView):
    """
    GET /readiness/

    Readiness probe — checks DB + cache connectivity.
    Returns 200 when both are healthy; 503 if either is unreachable.
    Use this for Kubernetes readinessProbe so traffic is only routed
    once the app can actually serve requests.
    """
    authentication_classes = []
    permission_classes     = [AllowAny]
    throttle_classes       = []

    def get(self, request: Request, *args, **kwargs) -> Response:
        checks: dict[str, str] = {}
        status_code = 200

        # ── Database ──────────────────────────────────────────────────────────
        try:
            connection.ensure_connection()
            checks['database'] = 'ok'
        except Exception as exc:
            logger.error('Readiness: database check failed: %s', exc)
            checks['database'] = 'error'
            status_code = 503

        # ── Cache ─────────────────────────────────────────────────────────────
        try:
            probe_key = 'readiness_probe'
            cache.set(probe_key, '1', timeout=5)
            assert cache.get(probe_key) == '1', 'Cache read-back mismatch'
            cache.delete(probe_key)
            checks['cache'] = 'ok'
        except Exception as exc:
            logger.error('Readiness: cache check failed: %s', exc)
            checks['cache'] = 'error'
            status_code = 503

        # ── Internet connectivity (last known result from HealthStatus) ────────
        # We read the *last stored* result from the DB rather than running a
        # live probe on every readiness request.  Live probes add 50–500 ms of
        # external latency to every k8s probe tick; the Celery task (runs every
        # 60 s) keeps HealthStatus fresh enough for a readiness decision.
        try:
            from ..models.health_status import HealthStatus
            inet = HealthStatus.objects.filter(
                service_name='internet', component_name='connectivity'
            ).first()
            if inet is None:
                checks['internet'] = 'unknown'   # task hasn't run yet
            elif inet.status == 'healthy':
                checks['internet'] = 'ok'
            else:
                checks['internet'] = inet.status  # 'degraded' | 'unhealthy'
                # Degraded internet is a warning, not a hard failure —
                # the app can still serve internal traffic.  Only mark
                # the pod unready if internet is fully unhealthy.
                if inet.status == 'unhealthy':
                    status_code = 503
        except Exception as exc:
            logger.error('Readiness: internet check lookup failed: %s', exc)
            checks['internet'] = 'unknown'

        return Response(
            {
                'status': 'ok' if status_code == 200 else 'degraded',
                'checks': checks,
                'version': getattr(settings, 'APP_VERSION', 'unknown'),
            },
            status=status_code,
        )
