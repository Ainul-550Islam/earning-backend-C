"""
Non-viewset views for Real-time Dashboard Backend.
Currently: health check endpoint only.

FIX: Added HealthCheckThrottle via @throttle_classes so the health
check endpoint (which is publicly accessible via AllowAny) cannot be
used as a denial-of-service amplifier. Without throttling, an attacker
can hammer /api/health/ to generate database and channel-layer load at
no authentication cost.

HealthCheckThrottle is defined in throttling.py and applies a low rate
limit appropriate for a monitoring probe (not an interactive endpoint).
"""
from django.db import connection, OperationalError
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiExample
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .throttling import HealthCheckThrottle


@extend_schema(
    tags=['health'],
    summary='Liveness / readiness probe',
    description=(
        'Checks the database connection and the WebSocket channel layer '
        '(Redis). Returns 200 when both are reachable, 503 otherwise. '
        'Unauthenticated — safe for load balancers and Kubernetes probes.'
    ),
    responses={
        200: inline_serializer(
            name='HealthCheckOK',
            fields={
                'status': serializers.ChoiceField(choices=['healthy']),
                'database': serializers.CharField(),
                'channel_layer': serializers.CharField(),
                'timestamp': serializers.DateTimeField(),
            },
        ),
        503: inline_serializer(
            name='HealthCheckUnhealthy',
            fields={
                'status': serializers.ChoiceField(choices=['unhealthy']),
                'database': serializers.CharField(),
                'channel_layer': serializers.CharField(),
                'timestamp': serializers.DateTimeField(),
            },
        ),
    },
    examples=[
        OpenApiExample(
            'Healthy',
            value={
                'status': 'healthy', 'database': 'ok', 'channel_layer': 'ok',
                'timestamp': '2026-07-09T10:15:30.123456+00:00',
            },
            response_only=True,
            status_codes=['200'],
        ),
    ],
)
@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([HealthCheckThrottle])
def health_check(request):
    """
    Liveness / readiness probe for load balancers, Kubernetes, and monitoring.

    GET /api/health/

    Checks:
    1. Database — runs SELECT 1 to confirm the DB connection pool is alive.
    2. Channel layer — calls channel_layer.group_send() to a throwaway group
       to confirm Redis (or the in-memory layer) is reachable.

    FIXED: previously only checked the database. A healthy DB with a broken
    Redis/channel-layer means WebSocket broadcasts are silently failing —
    real-time features are down — but the health endpoint would still return
    200, so the load balancer would route traffic and monitoring would show
    green. The channel layer check makes the probe an accurate readiness
    signal for the full application stack.

    Returns 200 when healthy, 503 when any dependency is unreachable.
    """
    db_status = 'ok'
    channel_status = 'ok'
    http_status = 200

    # ── 1. Database ──────────────────────────────────────────────────────────
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except OperationalError as exc:
        db_status = f'error: {exc}'
        http_status = 503

    # ── 2. Channel layer ─────────────────────────────────────────────────────
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if channel_layer is None:
            channel_status = 'not configured'
            http_status = 503
        else:
            # group_send to a throwaway group is a lightweight round-trip
            # that confirms the channel layer (Redis) is reachable.
            # It does NOT deliver to any consumer because nothing joins
            # 'health_check_probe'.
            async_to_sync(channel_layer.group_send)(
                'health_check_probe',
                {'type': 'health.check', 'data': 'ping'},
            )
    except Exception as exc:
        channel_status = f'error: {exc}'
        http_status = 503

    return Response(
        {
            'status': 'healthy' if http_status == 200 else 'unhealthy',
            'database': db_status,
            'channel_layer': channel_status,
            'timestamp': timezone.now().isoformat(),
        },
        status=http_status,
    )
