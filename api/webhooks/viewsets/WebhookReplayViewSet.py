# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Webhook Replay ViewSet

Handles webhook replay operations including single-delivery replay,
batch creation, status tracking, and progress monitoring.

FIX APPLIED: All @action methods indented into class body (were at module level).
"""

from django.db.models import Count, Avg, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import WebhookReplay, WebhookReplayBatch, WebhookReplayItem, WebhookDeliveryLog
from ..serializers import (
    WebhookReplaySerializer,
    WebhookReplayBatchSerializer,
    WebhookDeliveryLogSerializer,
)
from ..services.core.DispatchService import DispatchService
from ..constants import ReplayStatus


class WebhookReplayViewSet(viewsets.ModelViewSet):
    """
    ViewSet for webhook replay CRUD operations.
    Provides comprehensive replay functionality with batch management.

    Endpoints:
        GET    /webhooks/replay/                       — list replays
        POST   /webhooks/replay/                       — create replay
        GET    /webhooks/replay/{id}/                  — retrieve replay
        POST   /webhooks/replay/{id}/create-batch/     — create replay batch
        POST   /webhooks/replay/{id}/start-batch/      — start batch processing
        GET    /webhooks/replay/{id}/batch-progress/   — batch progress
        GET    /webhooks/replay/{id}/batch-status/     — batch status
        POST   /webhooks/replay/{id}/cancel-batch/     — cancel batch
        GET    /webhooks/replay/replay-history/        — history
        GET    /webhooks/replay/replay-statistics/     — statistics
    """

    queryset = WebhookReplay.objects.all()
    serializer_class = WebhookReplaySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        """Return only the current user's replays."""
        return (
            WebhookReplay.objects.filter(replayed_by=self.request.user)
            .select_related("original_log", "original_log__endpoint")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create_batch":
            return WebhookReplayBatchSerializer
        return self.serializer_class

    # ── Batch Actions ─────────────────────────────────────────────────────────

    @action(detail=False, methods=["post"], url_path="create-batch")
    def create_batch(self, request):
        """Create a new replay batch from date range or event type filter."""
        event_type = request.data.get("event_type")
        date_from  = request.data.get("date_from")
        date_to    = request.data.get("date_to")

        # BUG FIX (Session 10): batch_size came straight from request.data
        # with no type check, then went directly into a queryset slice
        # (`qs[:batch_size]`). Django's queryset slicing requires a real
        # int and raises a bare TypeError ("'<' not supported between
        # instances of 'str' and 'int'") for anything else — an uncaught
        # 500 for the extremely ordinary case of a client sending
        # `"batch_size": "50"` (a valid JSON string, not an int; also what
        # any non-JSON-aware form post would send). Now validated the same
        # way the rest of this codebase guards user-supplied numeric
        # input: coerce, reject non-positive/non-numeric values with a
        # clean 400 instead of a crash.
        raw_batch_size = request.data.get("batch_size", 100)
        try:
            batch_size = int(raw_batch_size)
            if batch_size <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response(
                {"success": False, "message": _("batch_size must be a positive integer.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build queryset of failed logs to replay
        qs = WebhookDeliveryLog.objects.filter(
            endpoint__owner=request.user,
            status__in=["failed", "exhausted"],
        )
        if event_type:
            qs = qs.filter(event_type=event_type)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        qs = qs[:batch_size]

        if not qs.exists():
            return Response(
                {"success": False, "message": _("No failed deliveries found for given filters.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        batch = WebhookReplayBatch.objects.create(
            event_type=event_type or "mixed",
            created_by=request.user,
            count=qs.count(),
            date_from=date_from,
            date_to=date_to,
        )

        items = [
            WebhookReplayItem(
                batch=batch,
                original_log=log,
                status=ReplayStatus.PENDING,
            )
            for log in qs
        ]
        WebhookReplayItem.objects.bulk_create(items)

        serializer = WebhookReplayBatchSerializer(batch)
        return Response(
            {"success": True, "data": serializer.data, "batch_id": str(batch.pk)},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="start-batch")
    def start_batch(self, request, id=None):
        """Start processing a replay batch (triggers async task)."""
        batch = get_object_or_404(WebhookReplayBatch, pk=id, created_by=request.user)

        if batch.status not in ["pending", "failed"]:
            return Response(
                {"success": False, "message": _("Batch is not in a startable state.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from ..tasks import process_replay_batch
            process_replay_batch.delay(str(batch.pk))
            # BUG FIX: see ReplayService.start_batch_processing()'s
            # docstring - this action has the identical
            # delay()-then-unconditional-status-set ordering bug. Under
            # CELERY_TASK_ALWAYS_EAGER, delay() finishes the real work
            # synchronously before the old code's status="processing"
            # line ran, silently stomping a real completed/failed result
            # back to "processing" permanently. Fixed the same way: only
            # set "processing" if the batch isn't already terminal.
            batch.refresh_from_db()
            if batch.status not in (ReplayStatus.COMPLETED, ReplayStatus.FAILED):
                batch.status = "processing"
                batch.save(update_fields=["status"])

            return Response(
                {"success": True, "message": _("Batch processing started."), "batch_id": str(batch.pk)},
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            return Response(
                {"success": False, "message": _("Failed to start batch."), "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"], url_path="batch-progress")
    def batch_progress(self, request, id=None):
        """Get progress of the replay batch."""
        batch = get_object_or_404(WebhookReplayBatch, pk=id, created_by=request.user)

        items = WebhookReplayItem.objects.filter(batch=batch)
        total      = items.count()
        completed  = items.filter(status=ReplayStatus.COMPLETED).count()
        failed     = items.filter(status=ReplayStatus.FAILED).count()
        pending    = items.filter(status=ReplayStatus.PENDING).count()

        return Response({
            "success": True,
            "data": {
                "batch_id": str(batch.pk),
                "status": batch.status,
                "total": total,
                "completed": completed,
                "failed": failed,
                "pending": pending,
                "progress_pct": round((completed / total) * 100, 1) if total else 0,
            },
        })

    @action(detail=True, methods=["get"], url_path="batch-status")
    def batch_status(self, request, id=None):
        """Get detailed status breakdown of the replay batch."""
        batch = get_object_or_404(WebhookReplayBatch, pk=id, created_by=request.user)

        items  = WebhookReplayItem.objects.filter(batch=batch)
        counts = {}
        for item in items:
            counts[item.status] = counts.get(item.status, 0) + 1

        return Response({
            "success": True,
            "data": {
                "batch_id": str(batch.pk),
                "event_type": batch.event_type,
                "status": batch.status,
                "total_items": items.count(),
                "status_breakdown": counts,
                "created_at": batch.created_at,
                "updated_at": batch.updated_at,
            },
        })

    @action(detail=True, methods=["post"], url_path="cancel-batch")
    def cancel_batch(self, request, id=None):
        """Cancel a pending or processing replay batch."""
        batch = get_object_or_404(WebhookReplayBatch, pk=id, created_by=request.user)

        if batch.status == "completed":
            return Response(
                {"success": False, "message": _("Cannot cancel a completed batch.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        batch.status = "cancelled"
        batch.save(update_fields=["status"])

        # Cancel pending replay items
        WebhookReplayItem.objects.filter(batch=batch, status=ReplayStatus.PENDING).update(
            status=ReplayStatus.CANCELLED
        )

        return Response(
            {"success": True, "message": _("Batch cancelled."), "batch_id": str(batch.pk)},
            status=status.HTTP_200_OK,
        )

    # ── History & Statistics ──────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="history", url_name="history")
    def replay_history(self, request):
        """Get replay history for the authenticated user."""
        event_type = request.query_params.get("event_type")
        qs = WebhookReplay.objects.filter(replayed_by=request.user).order_by("-created_at")

        if event_type:
            qs = qs.filter(event_type=event_type)

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = WebhookReplaySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = WebhookReplaySerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="statistics", url_name="statistics")
    def replay_statistics(self, request):
        """Get replay statistics for the authenticated user."""
        qs = WebhookReplay.objects.filter(replayed_by=request.user)

        stats = qs.aggregate(
            total_replays=Count("id"),
            completed_replays=Count("id", filter=Q(status=ReplayStatus.COMPLETED)),
            failed_replays=Count("id", filter=Q(status=ReplayStatus.FAILED)),
            pending_replays=Count("id", filter=Q(status=ReplayStatus.PENDING)),
        )

        total = stats["total_replays"] or 0
        done  = stats["completed_replays"] or 0

        return Response({
            "success": True,
            "data": {
                **stats,
                "success_rate_pct": round((done / total) * 100, 1) if total else 0,
                "generated_at": timezone.now(),
            },
        })
    # ── WebhookReplayItem — individual item status (FIX: previously no API) ────

    @action(detail=True, methods=["get"], url_path="items")
    def items(self, request, id=None):
        """
        GET /webhooks/replay/{id}/items/

        List all WebhookReplayItem records linked to this replay.
        Each item represents one delivery attempt in the replay batch.
        Previously WebhookReplayItem had no API exposure.
        """
        from ..models.replay import WebhookReplayItem
        from ..serializers.WebhookRateLimitSerializer import WebhookReplayItemSerializer

        replay = self.get_object()
        try:
            items = WebhookReplayItem.objects.filter(
                original_log__endpoint__owner=request.user
            ).select_related("original_log", "new_log").order_by("-created_at")

            status_filter = request.query_params.get("status")
            if status_filter:
                items = items.filter(status=status_filter)

            page = self.paginate_queryset(items)
            if page is not None:
                serializer = WebhookReplayItemSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = WebhookReplayItemSerializer(items, many=True)
            return Response({
                "success": True,
                "count":   items.count(),
                "data":    serializer.data,
            })
        except Exception as exc:
            return Response({"success": False, "error": str(exc)}, status=500)

    @action(detail=False, methods=["get"], url_path="my-items")
    def my_items(self, request):
        """
        GET /webhooks/replay/my-items/

        All WebhookReplayItem records for the current user across all replays.
        Supports ?status= and ?days= filters.
        """
        from ..models.replay import WebhookReplayItem
        from ..serializers.WebhookRateLimitSerializer import WebhookReplayItemSerializer
        from datetime import timedelta
        from django.utils import timezone

        try:
            days   = int(request.query_params.get("days", 30))
            status = request.query_params.get("status")
            since  = timezone.now() - timedelta(days=days)

            items = WebhookReplayItem.objects.filter(
                batch__created_by=request.user,
                created_at__gte=since,
            ).select_related("original_log", "new_log").order_by("-created_at")

            if status:
                items = items.filter(status=status)

            serializer = WebhookReplayItemSerializer(items, many=True)
            return Response({
                "success": True,
                "days":    days,
                "count":   items.count(),
                "data":    serializer.data,
            })
        except ValueError as exc:
            return Response({"success": False, "error": str(exc)}, status=400)
        except Exception as exc:
            return Response({"success": False, "error": str(exc)}, status=500)

