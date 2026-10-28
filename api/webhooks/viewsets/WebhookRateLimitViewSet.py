# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
WebhookRateLimitViewSet & WebhookRetryAnalysisViewSet
NEW FILE — WebhookRateLimit and WebhookRetryAnalysis had zero API exposure.

Routes registered in urls.py:
    GET  /webhooks/rate-limits/                   — list
    GET  /webhooks/rate-limits/{id}/              — detail
    GET  /webhooks/rate-limits/endpoint-summary/  — per-endpoint summary
    GET  /webhooks/rate-limits/top-consumers/     — top 10 by volume
    GET  /webhooks/retry-analysis/                — list
    GET  /webhooks/retry-analysis/worst-offenders/
    GET  /webhooks/retry-analysis/daily-trend/
"""
import logging

from django.db.models import Avg, Sum, Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from ..models import WebhookRateLimit, WebhookRetryAnalysis
from ..serializers.WebhookAnalyticsSerializer import (
    WebhookRateLimitSerializer, WebhookRetryAnalysisSerializer
)
from ..permissions import IsOwnerOrReadOnly

logger = logging.getLogger("ainul.webhooks.ratelimit")


class WebhookRateLimitViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API for rate limit statistics per endpoint.

    These records are written by RateLimiterService automatically;
    the API exposes them for dashboards and alerting.
    """
    serializer_class   = WebhookRateLimitSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['endpoint']
    ordering_fields    = ['reset_at', 'updated_at', 'current_count', 'max_requests']
    ordering           = ['-updated_at']

    def get_queryset(self):
        return (
            WebhookRateLimit.objects
            .filter(endpoint__owner=self.request.user)
            .select_related('endpoint')
        )

    @action(detail=False, methods=['get'], url_path='endpoint-summary')
    def endpoint_summary(self, request):
        """
        GET /webhooks/rate-limits/endpoint-summary/

        Current rate-limit usage per endpoint.

        BUG FIX: previously aggregated over a `date` field and total_sent/
        success_count/failed_count/avg_latency_ms fields that don't exist on
        WebhookRateLimit (it's a current-state counter per endpoint - see
        current_count/max_requests/window_seconds/reset_at - not a
        historical per-day log), so this always raised FieldError. Rewritten
        against the real fields.
        """
        try:
            qs = (
                self.get_queryset()
                .values('endpoint__id', 'endpoint__label', 'endpoint__target_url')
                .annotate(
                    current_count = Sum('current_count'),
                    max_requests  = Sum('max_requests'),
                    window_count  = Count('id'),
                )
                .order_by('-current_count')
            )
            data = list(qs)
            for row in data:
                row['usage_pct'] = (
                    round(row['current_count'] / row['max_requests'] * 100, 2)
                    if row['max_requests'] else 0.0
                )
            return Response({'success': True, 'data': data})
        except Exception as exc:
            logger.exception("endpoint_summary: unexpected error")
            return Response({'success': False, 'error': str(exc)}, status=500)

    @action(detail=False, methods=['get'], url_path='top-consumers')
    def top_consumers(self, request):
        """
        GET /webhooks/rate-limits/top-consumers/

        Top 10 endpoints by current rate-limit usage.

        BUG FIX: was `.filter(date=today).order_by('-total_sent')` - neither
        field exists on WebhookRateLimit (a current-state counter, not a
        dated log). Fixed to order by current_count.
        """
        try:
            qs = (
                self.get_queryset()
                .order_by('-current_count')[:10]
            )
            return Response({
                'success': True,
                'data': WebhookRateLimitSerializer(qs, many=True).data,
            })
        except Exception as exc:
            logger.exception("top_consumers: unexpected error")
            return Response({'success': False, 'error': str(exc)}, status=500)

    @action(detail=False, methods=['get'], url_path='near-limit')
    def near_limit(self, request):
        """
        GET /webhooks/rate-limits/near-limit/

        Endpoints currently using >= threshold% of their rate limit.

        BUG FIX: was `.filter(date=today)` (no such field -> FieldError on
        every call) and computed usage via r.total_sent (doesn't exist) and
        getattr(r.endpoint, 'rate_limit', None) (WebhookEndpoint has no
        rate_limit attribute either, so this was always None - the results
        would have been silently empty even if the date filter hadn't
        crashed first). Fixed to use the row's own current_count/max_requests.
        """
        try:
            threshold = float(request.query_params.get('threshold', 80))
            qs = self.get_queryset()
            near = []
            for r in qs:
                try:
                    if r.max_requests and (r.current_count / r.max_requests * 100) >= threshold:
                        near.append(WebhookRateLimitSerializer(r).data)
                except (ZeroDivisionError, TypeError):
                    pass
            return Response({
                'success':       True,
                'threshold_pct': threshold,
                'count':         len(near),
                'endpoints':     near,
            })
        except ValueError as exc:
            return Response({'success': False, 'error': str(exc)}, status=400)
        except Exception as exc:
            logger.exception("near_limit: unexpected error")
            return Response({'success': False, 'error': str(exc)}, status=500)


class WebhookRetryAnalysisViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API for retry analysis per endpoint.
    Surfaced from WebhookRetryAnalysis records written by DispatchService.
    """
    serializer_class   = WebhookRetryAnalysisSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['endpoint']
    ordering_fields    = ['period', 'exhausted_count', 'success_rate', 'updated_at']
    ordering           = ['-updated_at']

    def get_queryset(self):
        return (
            WebhookRetryAnalysis.objects
            .filter(endpoint__owner=self.request.user)
            .select_related('endpoint')
        )

    @action(detail=False, methods=['get'], url_path='worst-offenders')
    def worst_offenders(self, request):
        """
        GET /webhooks/retry-analysis/worst-offenders/

        Endpoints with the highest exhausted-retry count in the last 7 days.

        BUG FIX: was `.filter(date__gte=since)` and
        `Sum('failed_count')`/`Sum('total_sent')` - none of those fields
        exist on WebhookRetryAnalysis (real fields: exhausted_count,
        success_rate, avg_attempts_before_success, created_at, period) - so
        this always raised FieldError. Rewritten against the real fields.
        """
        try:
            since = timezone.now() - timedelta(days=7)
            qs = (
                self.get_queryset()
                .filter(created_at__gte=since)
                .values('endpoint__id', 'endpoint__label')
                .annotate(
                    total_exhausted  = Sum('exhausted_count'),
                    avg_success_rate = Avg('success_rate'),
                )
                .order_by('-total_exhausted')[:10]
            )
            return Response({'success': True, 'data': list(qs)})
        except Exception as exc:
            logger.exception("worst_offenders: unexpected error")
            return Response({'success': False, 'error': str(exc)}, status=500)

    @action(detail=False, methods=['get'], url_path='daily-trend')
    def daily_trend(self, request):
        """
        GET /webhooks/retry-analysis/daily-trend/?days=14

        Daily exhausted-retry / success-rate trend across all user endpoints.

        BUG FIX: was `.filter(date__gte=since).values('date').annotate(
        total=Sum('total_sent'), success=Sum('success_count'),
        failed=Sum('failed_count'))` - none of those fields exist on
        WebhookRetryAnalysis, and this had no try/except, so it surfaced as
        an unhandled 500 rather than even a clean error response. Rewritten
        to group by the real created_at timestamp (via TruncDate) using
        exhausted_count/success_rate, which do exist.
        """
        try:
            days  = int(request.query_params.get('days', 14))
            since = timezone.now() - timedelta(days=days)
            qs = (
                self.get_queryset()
                .filter(created_at__gte=since)
                .annotate(day=TruncDate('created_at'))
                .values('day')
                .annotate(
                    total_exhausted  = Sum('exhausted_count'),
                    avg_success_rate = Avg('success_rate'),
                )
                .order_by('day')
            )
            return Response({'success': True, 'days': days, 'trend': list(qs)})
        except Exception as exc:
            logger.exception("daily_trend: unexpected error")
            return Response({'success': False, 'error': str(exc)}, status=500)

    # BUG FIX: this class previously had a get_serializer_class() override
    # here that unconditionally returned WebhookRateLimitSerializer (the
    # *other* viewset's serializer, built for a different model's fields),
    # shadowing the correct `serializer_class = WebhookRetryAnalysisSerializer`
    # already declared above. Removed - the class attribute alone is correct.
