# publisher_tools/views_webhooks.py
# ============================================================
# NEW FILE — PublisherWebhookViewSet
# Exposes CRUD + management actions for publisher webhooks.
# Add to urls.py: router.register(r'webhooks', PublisherWebhookViewSet, basename='webhook')
# (Already done in file_05_urls_fixed.py)
# ============================================================
import json
import uuid
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin

from core.views import BaseViewSet
from .models import PublisherWebhook, WebhookDeliveryLog
from .permissions import IsPublisher, IsPublisherOwner
from .serializers_webhooks import (
    PublisherWebhookSerializer,
    PublisherWebhookCreateSerializer,
    WebhookDeliveryLogSerializer,
    WebhookTestSerializer,
)


class PublisherWebhookViewSet(BaseViewSet):
    """
    Publisher Webhook Management।
    Publisher-এর event notification endpoints manage করে।

    Actions:
      list        — publisher-এর সব webhooks
      create      — নতুন webhook register
      retrieve    — webhook detail
      update/patch — webhook update
      destroy     — webhook delete
      test        — test event পাঠাও
      deliveries  — delivery logs
      pause       — pause webhook
      resume      — resume webhook
    """
    serializer_class   = PublisherWebhookSerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            qs = PublisherWebhook.objects.select_related('publisher').all()
        else:
            try:
                publisher = user.publisher_profile
                qs = PublisherWebhook.objects.filter(publisher=publisher)
            except Exception:
                return PublisherWebhook.objects.none()

        # Filters
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs.order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return PublisherWebhookCreateSerializer
        return PublisherWebhookSerializer

    def perform_create(self, serializer):
        try:
            publisher = self.request.user.publisher_profile
        except Exception:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No active publisher profile found.')
        serializer.save(publisher=publisher)

    def _check_ownership(self, webhook):
        """Publisher can only manage their own webhooks."""
        user = self.request.user
        if user.is_staff:
            return
        try:
            publisher = user.publisher_profile
            if webhook.publisher != publisher:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied('You do not own this webhook.')
        except AttributeError:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No publisher profile.')

    # ── TEST ─────────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='test')
    def test(self, request, pk=None):
        """
        Test event পাঠায় webhook endpoint-এ।
        POST /webhooks/{id}/test/
        Body: {"event_type": "publisher.approved"}  (optional)
        """
        webhook = self.get_object()
        self._check_ownership(webhook)

        serializer = WebhookTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event_type = serializer.validated_data.get('event_type', 'test.ping')

        test_payload = {
            'event_type': event_type,
            'event_id':   uuid.uuid4().hex,
            'timestamp':  timezone.now().isoformat(),
            'test':       True,
            'data': {
                'publisher_id': webhook.publisher.publisher_id,
                'message':      'This is a test webhook delivery from Publisher Tools.',
            },
        }

        # Attempt delivery
        try:
            from .webhooks.webhook_manager import send_webhook_event
            logs = send_webhook_event(webhook.publisher, event_type, test_payload)
            delivered = any(
                log.status == 'success'
                for log in logs
                if hasattr(log, 'status')
            )
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Webhook delivery failed: {str(e)}',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'success': True,
            'delivered': delivered,
            'event_type': event_type,
            'endpoint_url': webhook.endpoint_url,
        })

    # ── DELIVERIES ────────────────────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='deliveries')
    def deliveries(self, request, pk=None):
        """
        Webhook delivery logs।
        GET /webhooks/{id}/deliveries/?status=failed&limit=50
        """
        webhook = self.get_object()
        self._check_ownership(webhook)

        logs_qs = WebhookDeliveryLog.objects.filter(webhook=webhook).order_by('-created_at')

        # Filters
        status_filter = request.query_params.get('status')
        if status_filter:
            logs_qs = logs_qs.filter(status=status_filter)

        limit = int(request.query_params.get('limit', 50))
        logs  = logs_qs[:limit]

        serializer = WebhookDeliveryLogSerializer(logs, many=True)
        return Response({
            'success': True,
            'data': {
                'webhook_id':       str(webhook.pk),
                'total_deliveries': webhook.total_deliveries,
                'success_rate':     webhook.success_rate,
                'logs':             serializer.data,
            },
        })

    # ── PAUSE ─────────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='pause')
    def pause(self, request, pk=None):
        """
        Webhook pause করে।
        POST /webhooks/{id}/pause/
        """
        webhook = self.get_object()
        self._check_ownership(webhook)

        if webhook.status == 'paused':
            return Response({'success': True, 'message': 'Webhook is already paused.'})

        webhook.status    = 'paused'
        webhook.is_active = False
        webhook.save(update_fields=['status', 'is_active', 'updated_at'])

        return Response({
            'success': True,
            'message': 'Webhook paused.',
            'data':    PublisherWebhookSerializer(webhook).data,
        })

    # ── RESUME ────────────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='resume')
    def resume(self, request, pk=None):
        """
        Paused webhook resume করে।
        POST /webhooks/{id}/resume/
        """
        webhook = self.get_object()
        self._check_ownership(webhook)

        if webhook.status == 'active':
            return Response({'success': True, 'message': 'Webhook is already active.'})

        # Don't resume permanently disabled webhooks
        if webhook.status == 'disabled':
            return Response({
                'success': False,
                'message': 'Disabled webhook cannot be resumed. Please contact support.',
            }, status=status.HTTP_400_BAD_REQUEST)

        webhook.status              = 'active'
        webhook.is_active           = True
        webhook.consecutive_failures = 0
        webhook.save(update_fields=['status', 'is_active', 'consecutive_failures', 'updated_at'])

        return Response({
            'success': True,
            'message': 'Webhook resumed.',
            'data':    PublisherWebhookSerializer(webhook).data,
        })
