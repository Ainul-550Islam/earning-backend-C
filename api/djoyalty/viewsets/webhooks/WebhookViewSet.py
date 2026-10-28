# api/djoyalty/viewsets/webhooks/WebhookViewSet.py
"""
WebhookViewSet -- WebhookSubscription + WebhookDeliveryLog API。
FIXED: Both models had NO API endpoints।
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from ...models.catalog import WebhookSubscription, WebhookDeliveryLog
from ...permissions import IsLoyaltyAdmin
from ...mixins import DjoyaltyBaseViewSet

logger = logging.getLogger(__name__)


class WebhookViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    permission_classes = [IsLoyaltyAdmin]

    def _tenant(self, request):
        tid = request.query_params.get('tenant_id') or request.data.get('tenant_id')
        if tid:
            from ...models.core import Tenant
            return Tenant.objects.filter(pk=tid).first()
        return None

    def list(self, request):
        qs = WebhookSubscription.objects.filter(is_active=True).order_by('-created_at')
        t = self._tenant(request)
        if t: qs = qs.filter(tenant=t)
        return Response({'count': qs.count(), 'results': [{
            'id': s.id, 'url': s.url,
            'event_types': s.event_types if isinstance(s.event_types, list) else [],
            'is_active': s.is_active, 'created_at': str(s.created_at),
        } for s in qs]})

    @action(detail=False, methods=['post'], url_path='create')
    def create_subscription(self, request):
        """FIXED: WebhookSubscription -- partners can now register webhooks via API。"""
        url         = request.data.get('url', '').strip()
        event_types = request.data.get('event_types', [])
        secret      = request.data.get('secret', '')
        if not url:
            return self.err('url required')
        if not url.startswith('https://'):
            return self.err('url must use HTTPS')
        if not event_types:
            return self.err('event_types list required')
        sub = WebhookSubscription.objects.create(
            tenant=self._tenant(request), url=url,
            event_types=event_types if isinstance(event_types, list) else [event_types],
            secret=secret, is_active=True,
        )
        return Response({'id': sub.id, 'url': sub.url, 'event_types': sub.event_types,
                         'is_active': sub.is_active}, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        get_object_or_404(WebhookSubscription, pk=pk).delete()
        return Response({'status': 'deleted', 'id': int(pk)})

    @action(detail=True, methods=['post'], url_path='test')
    def test_webhook(self, request, pk=None):
        sub = get_object_or_404(WebhookSubscription, pk=pk)
        try:
            from ...services.LoyaltyWebhookService import LoyaltyWebhookService
            LoyaltyWebhookService.send_test(subscription=sub)
            return Response({'status': 'test_sent', 'url': sub.url})
        except Exception as e:
            return Response({'error': str(e), 'status': 'test_failed'}, status=500)

    @action(detail=False, methods=['get'], url_path='delivery-log')
    def delivery_log(self, request):
        """FIXED: WebhookDeliveryLog -- delivery debug endpoint now available。"""
        qs = WebhookDeliveryLog.objects.select_related('subscription').order_by('-delivered_at')
        t = self._tenant(request)
        if t: qs = qs.filter(subscription__tenant=t)
        sf = request.query_params.get('status')
        if sf: qs = qs.filter(status=sf)
        qs = qs[:100]
        return Response({'count': qs.count(), 'results': [{
            'id': log.id, 'webhook_url': log.subscription.url if log.subscription else '',
            'event_type': log.event_type, 'status': log.status,
            'http_status': log.http_status_code, 'attempt': log.attempt_number,
            'delivered_at': str(log.delivered_at), 'response_body': (log.response_body or '')[:200],
        } for log in qs]})

    @action(detail=True, methods=['post'], url_path='retry')
    def retry_delivery(self, request, pk=None):
        log = get_object_or_404(WebhookDeliveryLog, pk=pk)
        if log.status == 'success':
            return self.err('Already delivered')
        try:
            from ...services.LoyaltyWebhookService import LoyaltyWebhookService
            LoyaltyWebhookService.retry(delivery_log=log)
            return Response({'status': 'retry_queued', 'log_id': log.id})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
