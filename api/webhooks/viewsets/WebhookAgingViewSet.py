# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Aging API ViewSet

Endpoints:
    GET    /webhooks/aging/endpoints/              — list endpoint aging records
    GET    /webhooks/aging/endpoints/{id}/         — endpoint aging detail
    POST   /webhooks/aging/endpoints/{id}/evaluate/ — re-evaluate one endpoint now
    GET    /webhooks/aging/logs/                   — list delivery log aging records
    GET    /webhooks/aging/events/                 — aging audit trail
    GET    /webhooks/aging/summary/                — dashboard tier distribution
    GET    /webhooks/aging/policy/                 — retrieve my policy
    PUT    /webhooks/aging/policy/                 — create / update my policy
    POST   /webhooks/aging/archive/               — trigger archive run (staff)
    POST   /webhooks/aging/purge/                 — trigger purge run (staff, dry_run default)
"""

import logging

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models.aging import (
    WebhookAgingEvent,
    WebhookAgingPolicy,
    WebhookDeliveryAging,
    WebhookEndpointAging,
)
from ..models.core import WebhookEndpoint
from ..serializers.WebhookAgingSerializer import (
    AgingPurgeConfirmSerializer,
    WebhookAgingEventSerializer,
    WebhookAgingPolicySerializer,
    WebhookDeliveryAgingSerializer,
    WebhookEndpointAgingSerializer,
)
from ..services.analytics.AgingService import AgingService

logger = logging.getLogger("ainul.webhooks.aging")


# ─────────────────────────────────────────────────────────────────────────────
#  ENDPOINT AGING VIEWSET
# ─────────────────────────────────────────────────────────────────────────────

class WebhookEndpointAgingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Ainul Enterprise Engine — Endpoint aging records (read-only + evaluate action).
    """

    serializer_class   = WebhookEndpointAgingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            WebhookEndpointAging.objects.filter(endpoint__owner=self.request.user)
            .select_related("endpoint")
            .order_by("-days_inactive")
        )

    @action(detail=True, methods=["post"], url_path="evaluate")
    def evaluate(self, request, pk=None):
        """
        Ainul Enterprise Engine — Re-evaluate the aging tier for this endpoint immediately.
        Useful after an endpoint resumes delivering successfully.
        """
        aging = self.get_object()
        svc   = AgingService()
        result = svc.evaluate_endpoint(aging.endpoint)
        aging.refresh_from_db()
        return Response(
            {
                "result":     result,
                "aging":      WebhookEndpointAgingSerializer(aging).data,
            },
            status=status.HTTP_200_OK,
        )

    def list(self, request, *args, **kwargs):
        tier = request.query_params.get("tier")
        qs   = self.get_queryset()
        if tier:
            qs = qs.filter(tier=tier)

        is_archived = request.query_params.get("is_archived")
        if is_archived is not None:
            qs = qs.filter(is_archived=is_archived.lower() == "true")

        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(
                WebhookEndpointAgingSerializer(page, many=True).data
            )
        return Response(WebhookEndpointAgingSerializer(qs, many=True).data)


# ─────────────────────────────────────────────────────────────────────────────
#  DELIVERY LOG AGING VIEWSET
# ─────────────────────────────────────────────────────────────────────────────

class WebhookDeliveryAgingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Ainul Enterprise Engine — Delivery log aging records (read-only).
    """

    serializer_class   = WebhookDeliveryAgingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = (
            WebhookDeliveryAging.objects.filter(
                delivery_log__endpoint__owner=self.request.user
            )
            .select_related("delivery_log", "delivery_log__endpoint")
            .order_by("-age_days")
        )
        bucket = self.request.query_params.get("bucket")
        if bucket:
            qs = qs.filter(bucket=bucket)
        return qs


# ─────────────────────────────────────────────────────────────────────────────
#  AGING EVENT VIEWSET
# ─────────────────────────────────────────────────────────────────────────────

class WebhookAgingEventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Ainul Enterprise Engine — Aging audit trail (read-only).
    """

    serializer_class   = WebhookAgingEventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            WebhookAgingEvent.objects.filter(
                endpoint_aging__endpoint__owner=self.request.user
            )
            .order_by("-occurred_at")
        )


# ─────────────────────────────────────────────────────────────────────────────
#  AGING SUMMARY VIEW
# ─────────────────────────────────────────────────────────────────────────────

class WebhookAgingSummaryAPIView(APIView):
    """
    Ainul Enterprise Engine — Tier distribution summary for the dashboard.
    GET /webhooks/aging/summary/
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        svc     = AgingService()
        summary = svc.get_aging_summary(owner=request.user)
        return Response(summary)


# ─────────────────────────────────────────────────────────────────────────────
#  AGING POLICY VIEW
# ─────────────────────────────────────────────────────────────────────────────

class WebhookAgingPolicyAPIView(APIView):
    """
    Ainul Enterprise Engine — Get or set the authenticated user's aging policy.
    GET  /webhooks/aging/policy/
    PUT  /webhooks/aging/policy/
    """

    permission_classes = [permissions.IsAuthenticated]

    def _get_or_create_policy(self, user):
        try:
            return WebhookAgingPolicy.objects.get(owner=user)
        except WebhookAgingPolicy.DoesNotExist:
            # Clone global defaults into user-owned policy
            global_policy = WebhookAgingPolicy.objects.filter(owner__isnull=True).first()
            if global_policy:
                global_policy.pk    = None
                global_policy.owner = user
                global_policy.save()
                return global_policy
            return WebhookAgingPolicy.objects.create(owner=user)

    def get(self, request):
        policy = self._get_or_create_policy(request.user)
        return Response(WebhookAgingPolicySerializer(policy).data)

    def put(self, request):
        policy     = self._get_or_create_policy(request.user)
        serializer = WebhookAgingPolicySerializer(policy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
#  ARCHIVE + PURGE VIEWS  (staff only)
# ─────────────────────────────────────────────────────────────────────────────

class WebhookAgingArchiveAPIView(APIView):
    """
    Ainul Enterprise Engine — Trigger an archive run for all due records.
    POST /webhooks/aging/archive/
    Staff only.
    """

    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        svc    = AgingService()
        result = svc.archive_due_records()
        return Response(result, status=status.HTTP_200_OK)


class WebhookAgingPurgeAPIView(APIView):
    """
    Ainul Enterprise Engine — Trigger a purge run.
    POST /webhooks/aging/purge/
    Body: { "confirm": true, "dry_run": false }
    Staff only. dry_run=true by default.
    """

    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = AgingPurgeConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dry_run = serializer.validated_data.get("dry_run", True)
        svc     = AgingService()
        result  = svc.purge_due_records(dry_run=dry_run)
        http_status = status.HTTP_200_OK if dry_run else status.HTTP_200_OK
        return Response(result, status=http_status)

    def get_serializer_class(self):
        """Get appropriate serializer class."""
        return AgingPurgeConfirmSerializer
