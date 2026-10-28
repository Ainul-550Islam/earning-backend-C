"""
NEW FILE — Operational health check endpoint.

Implements part of Missing Component (Operations): previously there was
no way for a load balancer / orchestrator (k8s liveness probe, etc.) to
ask "is this service actually working" — DB and cache connectivity were
unverified until something else failed downstream.
"""
from django.db import connection
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers


def _is_database_alive() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return True
    except Exception:
        return False


def _is_cache_alive() -> bool:
    try:
        cache.set('__health_check__', '1', 5)
        return cache.get('__health_check__') == '1'
    except Exception:
        return False


@extend_schema(
    responses=inline_serializer(
        name='HealthCheckResponse',
        fields={
            'status': serializers.ChoiceField(choices=['healthy', 'unhealthy']),
            'checks': inline_serializer(
                name='HealthCheckChecks',
                fields={
                    'database': serializers.BooleanField(),
                    'cache': serializers.BooleanField(),
                },
            ),
        },
    )
)
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Unauthenticated health endpoint for load balancers / orchestrators."""
    checks = {
        'database': _is_database_alive(),
        'cache': _is_cache_alive(),
    }
    healthy = all(checks.values())
    return Response(
        {'status': 'healthy' if healthy else 'unhealthy', 'checks': checks},
        status=200 if healthy else 503,
    )
