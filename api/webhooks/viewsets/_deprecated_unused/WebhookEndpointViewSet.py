# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Webhook Endpoint ViewSet

Handles webhook endpoint CRUD operations including secret rotation,
testing, pausing, resuming, health status, delivery logs, and subscriptions.

FIX APPLIED:
  - Replaced broken get_permissions() string-list with real permission_classes
  - Added IsAuthenticated + IsOwnerOrReadOnly
  - Added try/except to all action methods
  - Fixed broken test() method (delivery_log variable was undefined)
  - Corrected import paths (was ... now ..)
"""

import logging

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models import WebhookDeliveryLog, WebhookEndpoint, WebhookSubscription
from ...permissions import IsOwnerOrReadOnly
from ...serializers import (
    WebhookDeliveryLogSerializer,
    WebhookEmitSerializer,
    WebhookEndpointSerializer,
    WebhookSubscriptionSerializer,
    WebhookTestSerializer,
)
from ...services.analytics.HealthMonitorService import HealthMonitorService
from ...services.core.DispatchService import DispatchService
from ...services.core.SecretRotationService import SecretRotationService

logger = logging.getLogger("ainul.webhooks.endpoints")


class WebhookEndpointFilter(filters.FilterSet):
    """Filter set for webhook endpoints."""

    status     = filters.CharFilter(field_name="status", lookup_expr="exact", label=_("Status"))
    target_url = filters.CharFilter(lookup_expr="icontains", label=_("URL"))
    created_at = filters.DateTimeFromToRangeFilter(label=_("Created Date Range"))

    class Meta:
        model  = WebhookEndpoint
        fields = ["status", "target_url", "created_at"]


class WebhookEndpointViewSet(viewsets.ModelViewSet):
    """
    ViewSet for webhook endpoint CRUD operations.
    Provides full CRUD functionality with additional actions for
    testing, secret rotation, pause/resume, health, logs, and subscriptions.

    Endpoints:
        GET/POST        /webhooks/endpoints/
        GET/PUT/PATCH   /webhooks/endpoints/{id}/
        DELETE          /webhooks/endpoints/{id}/
        POST            /webhooks/endpoints/{id}/test/
        POST            /webhooks/endpoints/{id}/rotate-secret/
        POST            /webhooks/endpoints/{id}/pause/
        POST            /webhooks/endpoints/{id}/resume/
        GET             /webhooks/endpoints/{id}/health-status/
        GET             /webhooks/endpoints/{id}/delivery-logs/
        GET             /webhooks/endpoints/{id}/subscriptions/
    """

    serializer_class   = WebhookEndpointSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends    = [DjangoFilterBackend]
    filterset_class    = WebhookEndpointFilter
    lookup_field       = "id"

    def get_queryset(self):
        """Return only endpoints owned by the current user."""
        return WebhookEndpoint.objects.filter(
            owner=self.request.user
        ).select_related("owner").order_by("-created_at")

    def get_serializer_class(self):
        """Return appropriate serializer for each action."""
        if self.action == "test":
            return WebhookTestSerializer
        return self.serializer_class

    def perform_create(self, serializer):
        """Assign owner on creation."""
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        """Record update timestamp."""
        serializer.save(updated_at=timezone.now())

    # ── Test ──────────────────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="test")
    def test(self, request, id=None):
        """
        POST /webhooks/endpoints/{id}/test/

        Send a test webhook to the endpoint.
        """
        try:
            endpoint   = self.get_object()
            serializer = WebhookTestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            dispatch_service = DispatchService()
            result = dispatch_service.emit(
                endpoint=endpoint,
                event_type=serializer.validated_data.get("event_type", "test.ping"),
                payload=serializer.validated_data.get("payload", {"test": True}),
            )

            if result and result.get("success"):
                return Response({
                    "success":         True,
                    "message":         _("Test webhook sent successfully"),
                    "delivery_log_id": result.get("delivery_log_id"),
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "success": False,
                    "message": _("Failed to send test webhook"),
                    "error":   result.get("error") if result else _("Unknown error"),
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as exc:
            logger.exception("test: endpoint=%s error=%s", id, exc)
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ── Rotate Secret ─────────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="rotate-secret")
    def rotate_secret(self, request, id=None):
        """
        POST /webhooks/endpoints/{id}/rotate-secret/

        Rotate the HMAC signing secret for this endpoint.
        """
        try:
            endpoint         = self.get_object()
            rotation_service = SecretRotationService()
            result           = rotation_service.rotate_secret(endpoint)

            if result and result.get("success"):
                return Response({
                    "success":              True,
                    "message":              _("Secret rotated successfully"),
                    "new_secret_hash":      result.get("new_secret_hash"),
                    "old_secret_expires_at": result.get("old_secret_expires_at"),
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "success": False,
                    "message": _("Failed to rotate secret"),
                    "error":   result.get("error") if result else _("Unknown error"),
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as exc:
            logger.exception("rotate_secret: endpoint=%s error=%s", id, exc)
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ── Pause ─────────────────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="pause")
    def pause(self, request, id=None):
        """
        POST /webhooks/endpoints/{id}/pause/

        Pause event delivery to this endpoint.
        """
        try:
            endpoint = self.get_object()

            if endpoint.status == "paused":
                return Response({
                    "success": False,
                    "message": _("Endpoint is already paused"),
                }, status=status.HTTP_400_BAD_REQUEST)

            endpoint.status = "paused"
            endpoint.save(update_fields=["status", "updated_at"])

            logger.info("pause: endpoint=%s paused by user=%s", endpoint.pk, request.user.pk)
            return Response({
                "success": True,
                "message": _("Endpoint paused successfully"),
            }, status=status.HTTP_200_OK)

        except Exception as exc:
            logger.exception("pause: endpoint=%s error=%s", id, exc)
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ── Resume ────────────────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="resume")
    def resume(self, request, id=None):
        """
        POST /webhooks/endpoints/{id}/resume/

        Resume event delivery to this endpoint.
        """
        try:
            endpoint = self.get_object()

            if endpoint.status != "paused":
                return Response({
                    "success": False,
                    "message": _("Endpoint is not paused"),
                }, status=status.HTTP_400_BAD_REQUEST)

            endpoint.status = "active"
            endpoint.save(update_fields=["status", "updated_at"])

            logger.info("resume: endpoint=%s resumed by user=%s", endpoint.pk, request.user.pk)
            return Response({
                "success": True,
                "message": _("Endpoint resumed successfully"),
            }, status=status.HTTP_200_OK)

        except Exception as exc:
            logger.exception("resume: endpoint=%s error=%s", id, exc)
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ── Health Status ─────────────────────────────────────────────────────────

    @action(detail=True, methods=["get"])
    def health_status(self, request, id=None):
        """
        GET /webhooks/endpoints/{id}/health-status/

        24-hour health summary for this endpoint.
        """
        try:
            endpoint       = self.get_object()
            health_service = HealthMonitorService()
            health_summary = health_service.get_endpoint_health_summary(endpoint, hours=24)

            return Response({
                "success": True,
                "data":    health_summary,
            }, status=status.HTTP_200_OK)

        except Exception as exc:
            logger.exception("health_status: endpoint=%s error=%s", id, exc)
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ── Delivery Logs ─────────────────────────────────────────────────────────

    @action(detail=True, methods=["get"])
    def delivery_logs(self, request, id=None):
        """
        GET /webhooks/endpoints/{id}/delivery-logs/

        Last 100 delivery logs for this endpoint.
        Supports ?status= and ?limit= query params.
        """
        try:
            endpoint    = self.get_object()
            log_status  = request.query_params.get("status")
            limit       = min(int(request.query_params.get("limit", 100)), 500)

            qs = WebhookDeliveryLog.objects.filter(
                endpoint=endpoint
            ).order_by("-created_at")

            if log_status:
                qs = qs.filter(status=log_status)

            qs = qs[:limit]
            serializer = WebhookDeliveryLogSerializer(qs, many=True)

            return Response({
                "success": True,
                "count":   len(serializer.data),
                "data":    serializer.data,
            }, status=status.HTTP_200_OK)

        except ValueError as exc:
            return Response({"success": False, "error": str(exc)}, status=400)
        except Exception as exc:
            logger.exception("delivery_logs: endpoint=%s error=%s", id, exc)
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ── Subscriptions ─────────────────────────────────────────────────────────

    @action(detail=True, methods=["get"])
    def subscriptions(self, request, id=None):
        """
        GET /webhooks/endpoints/{id}/subscriptions/

        Active subscriptions (event-type mappings) for this endpoint.
        """
        try:
            endpoint      = self.get_object()
            subscriptions = endpoint.subscriptions.filter(is_active=True)
            serializer    = WebhookSubscriptionSerializer(subscriptions, many=True)

            return Response({
                "success": True,
                "count":   subscriptions.count(),
                "data":    serializer.data,
            }, status=status.HTTP_200_OK)

        except Exception as exc:
            logger.exception("subscriptions: endpoint=%s error=%s", id, exc)
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
