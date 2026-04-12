# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Dispatch System
views.py: DRF Class-Based API Views.

ViewSets / Views:
    WebhookEndpointViewSet     — CRUD for endpoint registration.
    WebhookSubscriptionViewSet — Subscribe/unsubscribe event types per endpoint.
    WebhookDeliveryLogViewSet  — Read-only delivery log + manual retry.
    WebhookEmitAPIView         — Internal emit trigger (staff/system only).
"""

import logging

from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .constants import DeliveryStatus, EndpointStatus, EventType
from .models import WebhookDeliveryLog, WebhookEndpoint, WebhookSubscription
from .serializers import (
    SecretRotateSerializer,
    WebhookDeliveryLogSerializer,
    WebhookEmitSerializer,
    WebhookEndpointDetailSerializer,
    WebhookEndpointSerializer,
    WebhookSubscriptionSerializer,
    WebhookTestSerializer,
)
from .services import DispatchService

logger = logging.getLogger("ainul.webhooks")


# ─────────────────────────────────────────────────────────────────────────────
#  ENDPOINT VIEWSET
# ─────────────────────────────────────────────────────────────────────────────

class WebhookEndpointViewSet(viewsets.ModelViewSet):
    """
    Ainul Enterprise Engine — Webhook Endpoint CRUD.

    Endpoints:
        GET    /webhooks/endpoints/          — list owner's endpoints
        POST   /webhooks/endpoints/          — register new endpoint
        GET    /webhooks/endpoints/{id}/     — retrieve detail + subscriptions
        PATCH  /webhooks/endpoints/{id}/     — update endpoint
        DELETE /webhooks/endpoints/{id}/     — delete endpoint
        POST   /webhooks/endpoints/{id}/rotate-secret/  — rotate signing key
        POST   /webhooks/endpoints/{id}/test/           — send test ping
        PATCH  /webhooks/endpoints/{id}/pause/          — pause endpoint
        PATCH  /webhooks/endpoints/{id}/resume/         — resume endpoint
    """

    permission_classes = [permissions.IsAuthenticated]
    http_method_names  = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return WebhookEndpoint.objects.filter(
            owner=self.request.user
        ).prefetch_related("subscriptions").order_by("-created_at")

    def get_serializer_class(self):
        if self.action in ("retrieve", "create"):
            return WebhookEndpointDetailSerializer
        return WebhookEndpointSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
        logger.info(
            "Endpoint created: user=%s url=%s",
            self.request.user.pk,
            serializer.validated_data.get("target_url"),
        )

    def perform_destroy(self, instance):
        logger.info(
            "Endpoint deleted: pk=%s owner=%s", instance.pk, instance.owner_id
        )
        instance.delete()

    # ── Custom Actions ────────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="rotate-secret")
    def rotate_secret(self, request, pk=None):
        """
        Ainul Enterprise Engine — Rotate the HMAC signing secret.
        Requires explicit confirm=true in the request body.
        """
        endpoint = self.get_object()
        serializer = SecretRotateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_secret = endpoint.rotate_secret()
        endpoint.save(update_fields=["secret_key", "updated_at"])

        return Response(
            {
                "message": "Secret rotated successfully. Update your consumer immediately.",
                "new_secret": new_secret,
                "endpoint_id": str(endpoint.pk),
                "rotated_at": timezone.now().isoformat(),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="test")
    def send_test(self, request, pk=None):
        """
        Ainul Enterprise Engine — Send a webhook.test ping to this endpoint.
        Useful for verifying endpoint connectivity and signature handling.
        """
        endpoint = self.get_object()

        if endpoint.status != EndpointStatus.ACTIVE:
            return Response(
                {"error": f"Endpoint is {endpoint.status}. Only ACTIVE endpoints can receive tests."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = WebhookTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payload = {
            "event": EventType.WEBHOOK_TEST,
            "message": serializer.validated_data["message"],
            "triggered_by": request.user.email,
            "timestamp": timezone.now().isoformat(),
        }

        log = DispatchService._dispatch(
            endpoint=endpoint,
            event_type=EventType.WEBHOOK_TEST,
            payload=payload,
            attempt_number=1,
        )

        return Response(
            WebhookDeliveryLogSerializer(log).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["patch"], url_path="pause")
    def pause(self, request, pk=None):
        """Ainul Enterprise Engine — Pause an active endpoint."""
        endpoint = self.get_object()
        if endpoint.status == EndpointStatus.PAUSED:
            return Response({"detail": "Endpoint is already paused."}, status=400)
        endpoint.status = EndpointStatus.PAUSED
        endpoint.save(update_fields=["status", "updated_at"])
        return Response({"status": endpoint.status, "endpoint_id": str(endpoint.pk)})

    @action(detail=True, methods=["patch"], url_path="resume")
    def resume(self, request, pk=None):
        """Ainul Enterprise Engine — Resume a paused or suspended endpoint."""
        endpoint = self.get_object()
        endpoint.status = EndpointStatus.ACTIVE
        endpoint.save(update_fields=["status", "updated_at"])
        return Response({"status": endpoint.status, "endpoint_id": str(endpoint.pk)})


# ─────────────────────────────────────────────────────────────────────────────
#  SUBSCRIPTION VIEWSET
# ─────────────────────────────────────────────────────────────────────────────

class WebhookSubscriptionViewSet(viewsets.ModelViewSet):
    """
    Ainul Enterprise Engine — Event Subscription manager.

    All subscriptions are scoped to a specific endpoint (nested route).

    Endpoints:
        GET    /webhooks/endpoints/{endpoint_pk}/subscriptions/
        POST   /webhooks/endpoints/{endpoint_pk}/subscriptions/
        PATCH  /webhooks/endpoints/{endpoint_pk}/subscriptions/{id}/
        DELETE /webhooks/endpoints/{endpoint_pk}/subscriptions/{id}/
    """

    serializer_class   = WebhookSubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names  = ["get", "post", "patch", "delete", "head", "options"]

    def _get_endpoint(self) -> WebhookEndpoint:
        endpoint_pk = self.kwargs.get("endpoint_pk")
        try:
            endpoint = WebhookEndpoint.objects.get(
                pk=endpoint_pk, owner=self.request.user
            )
        except WebhookEndpoint.DoesNotExist:
            raise NotFound("Endpoint not found or access denied.")
        return endpoint

    def get_queryset(self):
        endpoint = self._get_endpoint()
        return WebhookSubscription.objects.filter(endpoint=endpoint)

    def perform_create(self, serializer):
        endpoint = self._get_endpoint()
        serializer.save(endpoint=endpoint)
        logger.info(
            "Subscription created: endpoint=%s event=%s",
            endpoint.pk,
            serializer.validated_data.get("event_type"),
        )


# ─────────────────────────────────────────────────────────────────────────────
#  DELIVERY LOG VIEWSET
# ─────────────────────────────────────────────────────────────────────────────

class WebhookDeliveryLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Ainul Enterprise Engine — Delivery Log viewer with manual retry.

    Endpoints:
        GET  /webhooks/logs/           — list user's delivery logs
        GET  /webhooks/logs/{id}/      — log detail
        POST /webhooks/logs/{id}/retry/ — manually trigger retry
    """

    serializer_class   = WebhookDeliveryLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = WebhookDeliveryLog.objects.filter(
            endpoint__owner=self.request.user
        ).select_related("endpoint").order_by("-created_at")

        # Optional filters via query params
        event_type = self.request.query_params.get("event_type")
        status_f   = self.request.query_params.get("status")
        endpoint_id = self.request.query_params.get("endpoint_id")

        if event_type:
            qs = qs.filter(event_type=event_type)
        if status_f:
            qs = qs.filter(status=status_f)
        if endpoint_id:
            qs = qs.filter(endpoint_id=endpoint_id)

        return qs

    @action(detail=True, methods=["post"], url_path="retry")
    def retry(self, request, pk=None):
        """
        Ainul Enterprise Engine — Manually retry a failed delivery log.
        Only allowed for FAILED or RETRYING status logs.
        """
        log = self.get_object()

        if not log.is_retryable:
            return Response(
                {
                    "error": (
                        f"Log is not retryable. "
                        f"Current status: {log.status}, "
                        f"attempt: {log.attempt_number}/{log.max_attempts}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_log = DispatchService.retry_delivery(log)
        return Response(
            WebhookDeliveryLogSerializer(updated_log).data,
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────────────────────────────────────
#  EMIT API VIEW  (Internal / Staff)
# ─────────────────────────────────────────────────────────────────────────────

class WebhookEmitAPIView(APIView):
    """
    Ainul Enterprise Engine — Internal event emit endpoint.

    Used by other platform modules (payout, wallet, fraud) to trigger
    webhook dispatches programmatically.  Requires staff or system token.

    POST /webhooks/emit/
    """

    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = WebhookEmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        event_type    = data["event_type"]
        payload       = data["payload"]
        tenant_id     = data.get("tenant_id")
        async_dispatch = data.get("async_dispatch", True)

        if async_dispatch:
            from .tasks import dispatch_event
            task = dispatch_event.delay(
                event_type=event_type,
                payload=payload,
                tenant_id=tenant_id,
            )
            return Response(
                {
                    "status": "queued",
                    "task_id": task.id,
                    "event_type": event_type,
                },
                status=status.HTTP_202_ACCEPTED,
            )
        else:
            logs = DispatchService.emit(
                event_type=event_type,
                payload=payload,
                tenant_id=tenant_id,
            )
            return Response(
                {
                    "status": "dispatched",
                    "event_type": event_type,
                    "dispatched_count": len(logs),
                    "logs": WebhookDeliveryLogSerializer(logs, many=True).data,
                },
                status=status.HTTP_200_OK,
            )


# ─────────────────────────────────────────────────────────────────────────────
#  EVENT TYPES LIST VIEW
# ─────────────────────────────────────────────────────────────────────────────

class EventTypeListAPIView(APIView):
    """
    Ainul Enterprise Engine — List all subscribable event types.

    GET /webhooks/event-types/
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        event_types = [
            {"value": choice[0], "label": str(choice[1])}
            for choice in EventType.choices
        ]
        return Response({"count": len(event_types), "results": event_types})
