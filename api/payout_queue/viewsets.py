"""
Payout Queue ViewSets — HTTP layer only, all logic delegates to services.
"""

from __future__ import annotations

import logging
from typing import Any

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from .exceptions import (
    PayoutQueueError, PayoutBatchNotFoundError, PayoutBatchStateError,
    PayoutBatchLockedError, PayoutBatchLimitError, PayoutItemNotFoundError,
    PayoutItemStateError, InvalidPayoutAmountError, UserNotFoundError,
)
from .filters import PayoutBatchFilter, PayoutItemFilter, BulkProcessLogFilter
from .models import PayoutBatch, PayoutItem, WithdrawalPriority, BulkProcessLog
from .serializers import (
    PayoutBatchSerializer, CreatePayoutBatchSerializer,
    PayoutItemSerializer, PayoutItemInputSerializer,
    WithdrawalPrioritySerializer, BulkProcessLogSerializer,
)
from . import services

logger = logging.getLogger(__name__)


def _err(exc: Exception, http_status: int = status.HTTP_400_BAD_REQUEST) -> Response:
    return Response(
        {"detail": str(exc), "error_type": type(exc).__name__},
        status=http_status,
    )


class PayoutBatchViewSet(viewsets.ModelViewSet):
    serializer_class = PayoutBatchSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_class = PayoutBatchFilter

    def get_queryset(self):
        return PayoutBatch.objects.all().prefetch_related("process_logs").order_by(
            "-priority", "-created_at"
        )

    def create(self, request: Request) -> Response:
        serializer = CreatePayoutBatchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            batch = services.create_payout_batch(
                name=data["name"],
                gateway=data["gateway"],
                priority=data.get("priority"),
                scheduled_at=data.get("scheduled_at"),
                created_by_id=request.user.pk,
                note=data.get("note", ""),
                metadata=data.get("metadata", {}),
            )
            # Add items if provided inline
            if data.get("items"):
                services.add_payout_items(
                    batch_id=batch.pk,
                    items=data["items"],
                )
        except (PayoutQueueError, UserNotFoundError) as exc:
            return _err(exc)
        return Response(
            PayoutBatchSerializer(batch).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="add-items")
    def add_items(self, request: Request, pk: Any = None) -> Response:
        items_data = request.data.get("items", [])
        if not isinstance(items_data, list) or not items_data:
            return Response(
                {"detail": "items must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            created = services.add_payout_items(batch_id=pk, items=items_data)
        except PayoutBatchNotFoundError as exc:
            return _err(exc, status.HTTP_404_NOT_FOUND)
        except (PayoutBatchStateError, InvalidPayoutAmountError, PayoutQueueError) as exc:
            return _err(exc)
        return Response(
            {"added": len(created), "item_ids": [str(i.id) for i in created]},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="process")
    def process(self, request: Request, pk: Any = None) -> Response:
        """Synchronously process batch (use process-async for production)."""
        import uuid as _uuid
        worker_id = f"api-{str(_uuid.uuid4())[:8]}"
        try:
            result = services.process_batch(
                batch_id=pk,
                worker_id=worker_id,
                actor_id=request.user.pk,
            )
        except PayoutBatchNotFoundError as exc:
            return _err(exc, status.HTTP_404_NOT_FOUND)
        except (PayoutBatchLockedError, PayoutBatchLimitError, PayoutBatchStateError) as exc:
            return _err(exc, status.HTTP_409_CONFLICT)
        except PayoutQueueError as exc:
            return _err(exc)
        return Response(result)

    @action(detail=True, methods=["post"], url_path="process-async")
    def process_async(self, request: Request, pk: Any = None) -> Response:
        try:
            from .tasks import process_batch_async
            task = process_batch_async.delay(str(pk), actor_id=str(request.user.pk))
        except Exception as exc:
            return _err(PayoutQueueError(str(exc)))
        return Response({"task_id": task.id, "batch_id": str(pk)})

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request: Request, pk: Any = None) -> Response:
        try:
            batch = PayoutBatch.objects.get(pk=pk)
            batch.transition_to("CANCELLED", actor=request.user, note=request.data.get("note", ""))
        except PayoutBatch.DoesNotExist:
            return _err(PayoutBatchNotFoundError(f"Batch {pk} not found."), status.HTTP_404_NOT_FOUND)
        except PayoutBatchStateError as exc:
            return _err(exc)
        return Response(PayoutBatchSerializer(batch).data)

    @action(detail=True, methods=["get"], url_path="statistics")
    def statistics(self, request: Request, pk: Any = None) -> Response:
        try:
            stats = services.get_batch_statistics(pk)
        except PayoutBatchNotFoundError as exc:
            return _err(exc, status.HTTP_404_NOT_FOUND)
        return Response(stats)


class PayoutItemViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PayoutItemSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_class = PayoutItemFilter

    def get_queryset(self):
        return PayoutItem.objects.select_related("user", "batch").order_by("-created_at")

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request: Request, pk: Any = None) -> Response:
        reason = request.data.get("reason", "")
        try:
            item = services.cancel_payout_item(
                item_id=pk,
                reason=reason,
                actor_id=request.user.pk,
            )
        except PayoutItemNotFoundError as exc:
            return _err(exc, status.HTTP_404_NOT_FOUND)
        except PayoutItemStateError as exc:
            return _err(exc)
        return Response(PayoutItemSerializer(item).data)


class BulkProcessLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BulkProcessLogSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_class = BulkProcessLogFilter

    def get_queryset(self):
        return BulkProcessLog.objects.select_related("batch", "triggered_by").order_by("-created_at")


class WithdrawalPriorityViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WithdrawalPrioritySerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return WithdrawalPriority.objects.select_related("user", "assigned_by").order_by("-created_at")
