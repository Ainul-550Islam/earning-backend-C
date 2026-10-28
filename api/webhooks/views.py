# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Dispatch System
views.py: DRF Class-Based API Views.

ViewSets / Views:
    WebhookEndpointViewSet     — CRUD for endpoint registration.
    WebhookSubscriptionViewSet — Subscribe/unsubscribe event types per endpoint.
    WebhookDeliveryLogViewSet  — Read-only delivery log + manual retry.
    WebhookEmitAPIView         — Internal emit trigger (staff/system only).
    EventTypeListAPIView       — List all subscribable event types.

FIXES APPLIED:
  - DispatchService is now instantiated (was wrongly called as classmethod).
  - _dispatch() no longer called directly from views (internal method).
  - retry_delivery() called on instance, returns updated log correctly.
  - EndpointStatus imported from constants (not choices).
  - All field names use canonical names (target_url, custom_headers, etc.).
"""

from datetime import timedelta
import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from .constants import DeliveryStatus, EndpointStatus, EventType
from .choices import WebhookStatus
from .filters import WebhookEndpointFilter, WebhookDeliveryLogFilter
from .models import WebhookDeliveryLog, WebhookEndpoint, WebhookSubscription
from .validators import validate_event_type
from .serializers import (
    WebhookEmitPreviewSerializer,
    WebhookEmitPreviewResultSerializer,
    WebhookEmitValidateSerializer,
    WebhookEmitValidateResultSerializer,
    WebhookEventTypeValidateSerializer,
    WebhookEventTypeValidateResultSerializer,
    WebhookEventTypeTrendSerializer,
    WebhookEventTypeDetailSerializer,
)
from .serializers import (
    SecretRotateSerializer,
    WebhookDeliveryLogSerializer,
    WebhookEmitSerializer,
    WebhookEndpointDetailSerializer,
    WebhookEndpointSerializer,
    WebhookSubscriptionSerializer,
    WebhookTestSerializer,
    EventTypeListAPIViewSerializer,
)
from .services.core.DispatchService import DispatchService
from .services.core.SecretRotationService import SecretRotationService

logger = logging.getLogger("ainul.webhooks")


# ─────────────────────────────────────────────────────────────────────────────
#  ENDPOINT VIEWSET
# ─────────────────────────────────────────────────────────────────────────────

class WebhookEndpointViewSet(viewsets.ModelViewSet):
    """
    Ainul Enterprise Engine — Webhook Endpoint CRUD.

    Endpoints:
        GET    /webhooks/endpoints/                      — list owner's endpoints
        POST   /webhooks/endpoints/                      — register new endpoint
        GET    /webhooks/endpoints/{id}/                 — retrieve detail + subscriptions
        PATCH  /webhooks/endpoints/{id}/                 — update endpoint
        DELETE /webhooks/endpoints/{id}/                 — delete endpoint
        POST   /webhooks/endpoints/{id}/rotate-secret/  — rotate signing key
        POST   /webhooks/endpoints/{id}/test/            — send test ping
        PATCH  /webhooks/endpoints/{id}/pause/           — pause endpoint
        PATCH  /webhooks/endpoints/{id}/resume/          — resume endpoint
    """

    permission_classes = [permissions.IsAuthenticated]
    http_method_names  = ["get", "post", "patch", "delete", "head", "options"]
    filter_backends    = [DjangoFilterBackend]
    filterset_class    = WebhookEndpointFilter

    def get_queryset(self):
        return (
            WebhookEndpoint.objects.filter(owner=self.request.user)
            .prefetch_related("subscriptions")
            .order_by("-created_at")
        )

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
        logger.info("Endpoint deleted: pk=%s owner=%s", instance.pk, instance.owner_id)
        instance.delete()

    # ── Custom Actions ────────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="rotate-secret", url_name="rotate-secret")
    def rotate_secret(self, request, pk=None):
        """
        Ainul Enterprise Engine — Rotate the HMAC signing secret.
        Requires explicit confirm=true in the request body.

        Delegates to SecretRotationService (the same service every other
        rotation call site uses) rather than the endpoint's own model method,
        so this gets select_for_update() race protection and grace-period
        archiving of the old secret for free.
        """
        endpoint   = self.get_object()
        serializer = SecretRotateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_secret = SecretRotationService().rotate_secret(endpoint)

        return Response(
            {
                "success": True,
                "message": "Secret rotated successfully. Update your consumer immediately.",
                "new_secret": new_secret,
                "endpoint_id": str(endpoint.pk),
                "rotated_at": timezone.now().isoformat(),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="test", url_name="test")
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
            "event":        EventType.WEBHOOK_TEST,
            "message":      serializer.validated_data["message"],
            "triggered_by": request.user.email,
            "timestamp":    timezone.now().isoformat(),
        }

        # FIX: instantiate DispatchService; use emit() which creates its own log
        svc = DispatchService()
        svc.emit(endpoint=endpoint, event_type=EventType.WEBHOOK_TEST, payload=payload)

        # Return the latest log for this endpoint/event combination
        log = (
            WebhookDeliveryLog.objects.filter(
                endpoint=endpoint, event_type=EventType.WEBHOOK_TEST
            )
            .order_by("-created_at")
            .first()
        )

        data = WebhookDeliveryLogSerializer(log).data if log else {"status": "dispatched"}
        data["success"] = True
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="pause", url_name="pause")
    def pause(self, request, pk=None):
        """Ainul Enterprise Engine — Pause an active endpoint."""
        endpoint = self.get_object()
        if endpoint.status == EndpointStatus.PAUSED:
            return Response({"detail": "Endpoint is already paused."}, status=400)
        endpoint.status = EndpointStatus.PAUSED
        endpoint.save(update_fields=["status", "updated_at"])
        return Response({"success": True, "status": endpoint.status, "endpoint_id": str(endpoint.pk)})

    @action(detail=True, methods=["post"], url_path="resume", url_name="resume")
    def resume(self, request, pk=None):
        """Ainul Enterprise Engine — Resume a paused or suspended endpoint."""
        endpoint = self.get_object()
        endpoint.status = EndpointStatus.ACTIVE
        endpoint.save(update_fields=["status", "updated_at"])
        return Response({"success": True, "status": endpoint.status, "endpoint_id": str(endpoint.pk)})

    @action(detail=True, methods=["post"], url_path="health-check", url_name="health-check")
    def health_check(self, request, pk=None):
        """
        Ainul Enterprise Engine — Actively ping this endpoint right now.
        POST /webhooks/endpoints/{pk}/health-check/
        """
        from .services.core.EndpointHealthService import EndpointHealthService

        endpoint = self.get_object()
        result = EndpointHealthService().ping_endpoint(endpoint)
        return Response({"success": True, **result}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="analytics", url_name="analytics")
    def analytics(self, request, pk=None):
        """
        Ainul Enterprise Engine — Live delivery analytics for this endpoint.
        GET /webhooks/endpoints/{pk}/analytics/?days=30
        """
        from .services.analytics.WebhookAnalyticsService import WebhookAnalyticsService

        endpoint = self.get_object()
        days = int(request.query_params.get("days", 30))
        date_to = timezone.now()
        date_from = date_to - timedelta(days=days)
        data = WebhookAnalyticsService().calculate_endpoint_analytics(
            endpoint=endpoint, date_from=date_from, date_to=date_to
        )
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="health-status", url_name="health-status")
    def health_status(self, request, pk=None):
        """
        Ainul Enterprise Engine — Rolling health summary for this endpoint.
        GET /webhooks/endpoints/{pk}/health-status/
        """
        from .services.analytics.HealthMonitorService import HealthMonitorService

        endpoint = self.get_object()
        summary = HealthMonitorService().get_endpoint_health_summary(endpoint)
        return Response({"success": True, "data": summary}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="delivery-logs", url_name="delivery-logs")
    def delivery_logs(self, request, pk=None):
        """
        Ainul Enterprise Engine — Delivery logs for this endpoint (paginated).
        GET /webhooks/endpoints/{pk}/delivery-logs/
        """
        endpoint = self.get_object()
        queryset = WebhookDeliveryLog.objects.filter(endpoint=endpoint).order_by("-created_at")
        page = self.paginate_queryset(queryset)
        serializer = WebhookDeliveryLogSerializer(page if page is not None else queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response({"success": True, "results": serializer.data})


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
            return WebhookEndpoint.objects.get(pk=endpoint_pk, owner=self.request.user)
        except WebhookEndpoint.DoesNotExist:
            raise NotFound("Endpoint not found or access denied.")

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
        GET  /webhooks/logs/            — list user's delivery logs
        GET  /webhooks/logs/{id}/       — log detail
        POST /webhooks/logs/{id}/retry/ — manually trigger retry
    """

    serializer_class   = WebhookDeliveryLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends    = [DjangoFilterBackend]
    filterset_class    = WebhookDeliveryLogFilter

    def get_queryset(self):
        qs = (
            WebhookDeliveryLog.objects.filter(endpoint__owner=self.request.user)
            .select_related("endpoint")
            .order_by("-created_at")
        )

        event_type  = self.request.query_params.get("event_type")
        status_f    = self.request.query_params.get("status")
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

        # is_retryable is a @property on WebhookDeliveryLog (models/core.py)
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

        # FIX: instantiate DispatchService; retry_delivery is an instance method
        svc = DispatchService()
        svc.retry_delivery(log)

        # Reload the log to reflect updated status from retry_delivery
        log.refresh_from_db()
        return Response(
            WebhookDeliveryLogSerializer(log).data,
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────────────────────────────────────
#  EMIT API VIEW  (Internal / Staff)
# ─────────────────────────────────────────────────────────────────────────────

class WebhookEmitAPIView(APIView):
    """
    Ainul Enterprise Engine — Internal event emit endpoint.

    Used by other platform modules (payout, wallet, fraud) to trigger
    webhook dispatches programmatically. Requires staff or system token.

    POST /webhooks/emit/
    """

    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = WebhookEmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data        = serializer.validated_data
        endpoint    = WebhookEndpoint.objects.get(id=data["endpoint_id"])
        event_type  = data["event_type"]
        payload     = data["payload"]
        async_emit  = data.get("async_emit", False)

        svc = DispatchService()

        if async_emit:
            from .tasks import dispatch_event
            task = dispatch_event.delay(
                endpoint_id=str(endpoint.id),
                event_type=event_type,
                payload=payload,
            )
            return Response(
                {
                    "status":      "queued",
                    "task_id":     task.id,
                    "endpoint_id": str(endpoint.id),
                    "event_type":  event_type,
                },
                status=status.HTTP_202_ACCEPTED,
            )
        else:
            success = svc.emit(endpoint=endpoint, event_type=event_type, payload=payload)
            # NOTE (Session 10): `success=False` here is the ordinary,
            # expected outcome whenever the *target* endpoint itself
            # rejects/times out the delivery (that's precisely what the
            # retry system exists to handle — test_complete_webhook_flow_
            # with_retry, _with_replay, _error_handling, and
            # test_webhook_system_error_recovery all deliberately exercise
            # this path and assert 200), so this intentionally stays 200
            # regardless of `success`. See create_batch's batch_size fix in
            # WebhookReplayViewSet for the same-session fix to the
            # different case this isn't: a raised, uncaught error.
            return Response(
                {
                    "status":      "dispatched" if success else "failed",
                    "success":     success,
                    "endpoint_id": str(endpoint.id),
                    "event_type":  event_type,
                },
                status=status.HTTP_200_OK,
            )


class WebhookEmitPreviewAPIView(APIView):
    """
    Ainul Enterprise Engine — Preview what an emit would send, without sending it.

    Builds the exact headers/signature/payload that DispatchService would use
    for a real dispatch, using the same code path, but never makes the HTTP
    request and never creates a persisted WebhookDeliveryLog row.

    POST /webhooks/emit/preview/
    """

    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = WebhookEmitPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        endpoint = WebhookEndpoint.objects.get(id=data["endpoint_id"])

        # Unsaved instance only — never persisted. Its UUID pk is already
        # populated (WebhookDeliveryLog.id has default=uuid.uuid4), which is
        # enough for DispatchService's header-building code to run unchanged.
        preview_log = WebhookDeliveryLog(
            endpoint=endpoint,
            event_type=data["event_type"],
            payload=data["payload"],
            attempt_number=1,
        )

        svc = DispatchService()
        headers = svc._prepare_headers(endpoint, preview_log)
        body    = svc._prepare_payload(endpoint, data["payload"])

        result = WebhookEmitPreviewResultSerializer({
            "endpoint_id":     endpoint.id,
            "endpoint_url":    endpoint.target_url,
            "event_type":      data["event_type"],
            "payload":         data["payload"],
            "headers":         headers,
            "signature":       headers.get("X-Webhook-Signature", ""),
            "estimated_size":  len(body.encode("utf-8")),
            "estimated_time":  0.0,  # no request made — nothing to time
        })
        return Response(result.data, status=status.HTTP_200_OK)


class WebhookEmitValidateAPIView(APIView):
    """
    Ainul Enterprise Engine — Validate emit inputs without dispatching.

    Stricter than preview: also confirms the endpoint is ACTIVE. Never sends
    a request and never touches WebhookDeliveryLog.

    POST /webhooks/emit/validate/
    """

    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = WebhookEmitValidateSerializer(data=request.data)

        if not serializer.is_valid():
            errors = [
                f"{field}: {'; '.join(str(m) for m in msgs)}"
                for field, msgs in serializer.errors.items()
            ]
            result = WebhookEmitValidateResultSerializer({
                "valid":        False,
                "endpoint_id":  request.data.get("endpoint_id"),
                "event_type":   request.data.get("event_type", ""),
                "payload_size": 0,
                "warnings":     [],
                "errors":       errors,
            })
            return Response(result.data, status=status.HTTP_200_OK)

        data = serializer.validated_data
        import json
        payload_size = len(json.dumps(data["payload"]).encode("utf-8"))

        warnings = []
        if payload_size > 100_000:
            warnings.append("Payload exceeds 100KB — some receivers may reject large bodies.")

        result = WebhookEmitValidateResultSerializer({
            "valid":        True,
            "endpoint_id":  data["endpoint_id"],
            "event_type":   data["event_type"],
            "payload_size": payload_size,
            "warnings":     warnings,
            "errors":       [],
        })
        return Response(result.data, status=status.HTTP_200_OK)


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
        search = request.query_params.get("search", "")
        values = [
            choice[0] for choice in EventType.choices
            if not search or search.lower() in choice[0].lower()
        ]
        serializer = EventTypeListAPIViewSerializer(values, many=True)
        return Response({"count": len(values), "results": serializer.data})


class EventTypeValidateAPIView(APIView):
    """
    Ainul Enterprise Engine — Validate an event type string's format.

    Reuses the same validators.validate_event_type() used by
    WebhookSubscription / WebhookEmitSerializer, so "valid" here means
    exactly what "valid" means everywhere else this string is accepted.

    POST /webhooks/event-types/validate/   body: {"event_type": "user.created"}
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = WebhookEventTypeValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event_type = serializer.validated_data["event_type"]

        errors = []
        try:
            validate_event_type(event_type)
            valid = True
        except DjangoValidationError as exc:
            valid = False
            errors = [str(m) for m in exc.messages]

        domain, _, event = event_type.partition(".")
        warnings = []
        if valid and event_type not in {c[0] for c in EventType.choices}:
            warnings.append(
                "Format is valid but this event type is not in the predefined "
                "EventType list — it will still work for custom/internal events."
            )

        result = WebhookEventTypeValidateResultSerializer({
            "valid":      valid,
            "event_type": event_type,
            "domain":     domain,
            "event":      event,
            "warnings":   warnings,
            "errors":     errors,
        })
        return Response(result.data, status=status.HTTP_200_OK)


class EventTypeTrendAPIView(APIView):
    """
    Ainul Enterprise Engine — Daily emit trend for one or all event types.

    Aggregated straight from WebhookDeliveryLog — no forecasting or scoring,
    just per-day counts/success-rate/avg-response-time. Query params:
        event_type  (optional) — restrict to one event type
        days        (optional, default 7, max 90)

    GET /webhooks/event-types/trends/
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        event_type = request.query_params.get("event_type")
        try:
            days = min(int(request.query_params.get("days", 7)), 90)
        except ValueError:
            days = 7

        since = timezone.now() - timedelta(days=days)
        qs = WebhookDeliveryLog.objects.filter(
            endpoint__owner=request.user,
            created_at__gte=since,
        )
        if event_type:
            qs = qs.filter(event_type=event_type)

        rows = (
            qs.annotate(date=TruncDate("created_at"))
            .values("event_type", "date")
            .annotate(
                emit_count=Count("id"),
                success_count=Count("id", filter=Q(status=DeliveryStatus.SUCCESS)),
                avg_response_time=Avg("response_time_ms"),
            )
            .order_by("-date", "event_type")
        )

        results = [
            WebhookEventTypeTrendSerializer({
                "event_type":        row["event_type"],
                "date":              row["date"],
                "emit_count":        row["emit_count"],
                "success_count":     row["success_count"],
                "success_rate":      (row["success_count"] / row["emit_count"] * 100) if row["emit_count"] else 0.0,
                "avg_response_time": row["avg_response_time"] or 0.0,
            }).data
            for row in rows
        ]
        return Response({"count": len(results), "days": days, "results": results})


class EventTypeDetailAPIView(APIView):
    """
    Ainul Enterprise Engine — Detail for a single event type.

    Scoped to the requesting user's own endpoints/subscriptions, same as
    EventTypeTrendAPIView above — this is account-level usage detail, not
    a global admin view.

    GET /webhooks/event-types/<event_type>/details/
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, event_type):
        subs_qs = WebhookSubscription.objects.filter(
            event_type=event_type, endpoint__owner=request.user
        )
        subscription_count = subs_qs.count()
        endpoint_count = subs_qs.values("endpoint").distinct().count()

        last_log = (
            WebhookDeliveryLog.objects.filter(
                event_type=event_type, endpoint__owner=request.user
            )
            .order_by("-created_at")
            .first()
        )

        known_labels = dict(EventType.choices)
        description = str(known_labels[event_type]) if event_type in known_labels else ""

        result = WebhookEventTypeDetailSerializer({
            "event_type":         event_type,
            "description":        description,
            "subscription_count": subscription_count,
            "endpoint_count":     endpoint_count,
            "last_emitted":       last_log.created_at if last_log else None,
        })
        return Response(result.data)
