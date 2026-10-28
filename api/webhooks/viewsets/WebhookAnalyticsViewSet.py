# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Webhook Analytics ViewSet

Handles webhook analytics CRUD operations including statistics,
performance metrics, health monitoring, and EventRouter analytics.

FIX APPLIED:
  - Added IsAuthenticated + IsOwnerOrReadOnly permission_classes
  - Added try/except error handling to all action methods
  - Import path corrected (was ..., should be ..)
"""

import csv
import logging
from datetime import timedelta
from io import StringIO

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import WebhookAnalytics, WebhookEndpoint, WebhookEventStat
from ..permissions import IsOwnerOrReadOnly
from ..serializers import WebhookAnalyticsSerializer, WebhookEventStatSerializer
from ..services.analytics import HealthMonitorService

logger = logging.getLogger("ainul.webhooks.analytics")


class WebhookAnalyticsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for webhook analytics CRUD operations.
    Provides comprehensive analytics and performance monitoring.

    Endpoints:
        GET  /webhooks/analytics/                              — list
        GET  /webhooks/analytics/{id}/                         — detail
        GET  /webhooks/analytics/health-summary/                — health summary (all active endpoints)
        GET  /webhooks/analytics/{id}/performance-report/      — performance
        GET  /webhooks/analytics/{id}/event-stats/             — event stats
        POST /webhooks/analytics/{id}/export-csv/              — CSV export
        GET  /webhooks/analytics/routing-statistics/           — routing stats
        GET  /webhooks/analytics/orphaned-subscriptions/       — orphaned subs
        POST /webhooks/analytics/validate-routing/             — validate routing
    """

    serializer_class   = WebhookAnalyticsSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    lookup_field       = "id"

    def get_queryset(self):
        """Return analytics scoped to the authenticated user's endpoints."""
        return WebhookAnalytics.objects.filter(
            endpoint__owner=self.request.user
        ).select_related("endpoint").order_by("-date")

    # ── Health Summary ────────────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="health-summary")
    def health_summary(self, request):
        """GET /webhooks/analytics/health-summary/ — health summary for all active endpoints."""
        try:
            health_service = HealthMonitorService()
            active_endpoints = WebhookEndpoint.objects.filter(
                owner=request.user, status="active"
            )
            summaries = []
            for endpoint in active_endpoints:
                try:
                    summary = health_service.get_endpoint_health_summary(endpoint, hours=24)
                    if summary:
                        summaries.append(summary)
                except Exception as e:
                    logger.warning("health_summary: endpoint %s skipped: %s", endpoint.pk, e)

            return Response({
                "success": True,
                "data": {
                    "total_endpoints": active_endpoints.count(),
                    "health_summaries": summaries,
                    "generated_at": timezone.now(),
                },
            }, status=status.HTTP_200_OK)

        except Exception as exc:
            logger.exception("health_summary: unexpected error")
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ── Performance Report ────────────────────────────────────────────────────

    @action(detail=True, methods=["get"], url_path="performance-report")
    def performance_report(self, request, id=None):
        """GET /webhooks/analytics/{id}/performance-report/ — aggregated performance for N days."""
        try:
            days  = int(request.query_params.get("days", 30))
            since = timezone.now() - timedelta(days=days)

            analytics_data = WebhookAnalytics.objects.filter(
                endpoint__owner=request.user,
                date__gte=since.date(),
            ).select_related("endpoint").order_by("date", "endpoint")

            total_sent    = sum(d.total_sent for d in analytics_data)
            total_success = sum(d.success_count for d in analytics_data)
            total_failed  = sum(d.failed_count for d in analytics_data)
            avg_latency   = (
                sum(d.avg_latency_ms for d in analytics_data) / len(analytics_data)
                if analytics_data else 0
            )

            endpoint_performance: dict = {}
            for d in analytics_data:
                eid = str(d.endpoint.pk)
                if eid not in endpoint_performance:
                    endpoint_performance[eid] = {
                        "endpoint_id":  eid,
                        "endpoint_url": d.endpoint.target_url,
                        "total_sent":   0,
                        "success_count": 0,
                        "failed_count":  0,
                        "avg_latency":   0.0,
                    }
                ep = endpoint_performance[eid]
                ep["total_sent"]    += d.total_sent
                ep["success_count"] += d.success_count
                ep["failed_count"]  += d.failed_count
                ep["avg_latency"]    = (ep["avg_latency"] + d.avg_latency_ms) / 2

            return Response({
                "success": True,
                "data": {
                    "period_days":         days,
                    "total_sent":          total_sent,
                    "total_success":       total_success,
                    "total_failed":        total_failed,
                    "avg_latency_ms":      round(avg_latency, 2),
                    "overall_success_rate": round(
                        (total_success / total_sent) * 100, 2
                    ) if total_sent > 0 else 0,
                    "endpoint_performance": list(endpoint_performance.values()),
                    "generated_at":        timezone.now(),
                },
            }, status=status.HTTP_200_OK)

        except ValueError as exc:
            return Response(
                {"success": False, "error": f"Invalid parameter: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception("performance_report: unexpected error")
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ── Event Statistics ──────────────────────────────────────────────────────

    @action(detail=True, methods=["get"], url_path="event-stats", url_name="event-stats")
    def event_statistics(self, request, id=None):
        """GET /webhooks/analytics/{id}/event-stats/ — event type statistics."""
        try:
            days       = int(request.query_params.get("days", 30))
            event_type = request.query_params.get("event_type")
            since      = timezone.now() - timedelta(days=days)

            # WebhookEventStat has no endpoint field (confirmed via
            # introspection) - it's a global, platform-wide per-day/
            # per-event-type aggregate with no per-owner scoping, so there's
            # no endpoint__owner to filter on. The old filter raised
            # FieldError on every real call.
            qs = WebhookEventStat.objects.filter(
                date__gte=since.date(),
            )
            if event_type:
                qs = qs.filter(event_type=event_type)

            qs = qs.order_by("-date")
            serializer = WebhookEventStatSerializer(qs, many=True)

            return Response({
                "success": True,
                "data":    serializer.data,
            }, status=status.HTTP_200_OK)

        except ValueError as exc:
            return Response(
                {"success": False, "error": f"Invalid parameter: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception("event_statistics: unexpected error")
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ── CSV Export ────────────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="export-csv")
    def export_csv(self, request, id=None):
        """POST /webhooks/analytics/{id}/export-csv/ — download analytics as CSV."""
        try:
            days  = int(request.query_params.get("days", 30))
            since = timezone.now() - timedelta(days=days)

            analytics_data = WebhookAnalytics.objects.filter(
                endpoint__owner=request.user,
                date__gte=since.date(),
            ).select_related("endpoint").order_by("date", "endpoint")

            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = (
                f'attachment; filename="webhook_analytics_{timezone.now().strftime("%Y%m%d")}.csv"'
            )

            writer = csv.writer(response)
            writer.writerow([
                "Date", "Endpoint", "Total Sent", "Success Count",
                "Failed Count", "Success Rate (%)", "Avg Latency (ms)",
            ])

            for d in analytics_data:
                sr = round((d.success_count / d.total_sent) * 100, 2) if d.total_sent else 0
                writer.writerow([
                    d.date.strftime("%Y-%m-%d"),
                    d.endpoint.target_url,
                    d.total_sent,
                    d.success_count,
                    d.failed_count,
                    sr,
                    round(d.avg_latency_ms, 2),
                ])

            return response

        except Exception as exc:
            logger.exception("export_csv: unexpected error")
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ── EventRouter analytics (wired — previously floating) ──────────────────

    @action(detail=False, methods=["get"], url_path="routing-statistics")
    def routing_statistics(self, request):
        """
        GET /webhooks/analytics/routing-statistics/

        Routing hit/miss counts per event type.
        Uses EventRouter.get_routing_statistics().
        """
        try:
            event_type = request.query_params.get("event_type")
            days       = int(request.query_params.get("days", 7))
            from ..services.filtering.EventRouter import EventRouter
            stats = EventRouter().get_routing_statistics(event_type=event_type, days=days)
            return Response({"success": True, "data": stats})
        except ValueError as exc:
            return Response({"success": False, "error": str(exc)}, status=400)
        except Exception as exc:
            logger.exception("routing_statistics: unexpected error")
            return Response({"success": False, "error": str(exc)}, status=500)

    @action(detail=False, methods=["get"], url_path="orphaned-subscriptions")
    def orphaned_subscriptions(self, request):
        """
        GET /webhooks/analytics/orphaned-subscriptions/

        Subscriptions that never receive events (wrong event_type, deleted endpoint).
        Uses EventRouter.find_orphaned_subscriptions().
        """
        try:
            from ..services.filtering.EventRouter import EventRouter
            orphans = EventRouter().find_orphaned_subscriptions()
            return Response({"success": True, "orphaned": orphans, "count": len(orphans)})
        except Exception as exc:
            logger.exception("orphaned_subscriptions: unexpected error")
            return Response({"success": False, "error": str(exc)}, status=500)

    @action(detail=False, methods=["post"], url_path="validate-routing")
    def validate_routing(self, request):
        """
        POST /webhooks/analytics/validate-routing/

        Validate that an event_type + payload combination routes correctly.
        Uses EventRouter.validate_routing_configuration().
        """
        try:
            event_type = request.data.get("event_type")
            payload    = request.data.get("payload", {})
            if not event_type:
                return Response({"error": "event_type is required"}, status=400)
            from ..services.filtering.EventRouter import EventRouter
            result = EventRouter().validate_routing_configuration(event_type, payload)
            return Response({"success": True, "validation": result})
        except Exception as exc:
            logger.exception("validate_routing: unexpected error")
            return Response({"success": False, "error": str(exc)}, status=500)

    def get_serializer_class(self):
        """Get appropriate serializer class."""
        return WebhookAnalyticsSerializer
