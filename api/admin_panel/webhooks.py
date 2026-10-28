# api/admin_panel/webhooks.py
"""
Admin Panel Outbound Webhooks.
Calls api.webhooks — admin_panel never manages webhook logic itself.
Provides admin interface to: manage endpoints, view delivery logs, retry.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class AdminWebhookViewSet(viewsets.ViewSet):
    """Admin control for webhook endpoints and delivery logs."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def endpoints(self, request):
        """List all registered webhook endpoints."""
        try:
            from api.webhooks.models import WebhookEndpoint
            endpoints = list(WebhookEndpoint.objects.values(
                'id', 'url', 'events', 'is_active',
                'secret_set', 'total_deliveries', 'failure_count', 'created_at'
            ).order_by('-is_active', '-total_deliveries'))
            return Response({'success': True, 'data': endpoints})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def delivery_logs(self, request):
        """Recent webhook delivery logs."""
        try:
            from api.webhooks.models import WebhookDelivery
            hours = int(request.query_params.get('hours', 24))
            cutoff = timezone.now() - timedelta(hours=hours)
            logs = list(WebhookDelivery.objects.filter(
                created_at__gte=cutoff
            ).values(
                'id', 'endpoint__url', 'event_type', 'status_code',
                'success', 'attempt', 'created_at'
            ).order_by('-created_at')[:200])
            summary = {
                'total': len(logs),
                'success': sum(1 for l in logs if l.get('success')),
                'failed': sum(1 for l in logs if not l.get('success')),
            }
            return Response({'success': True, 'data': logs, 'summary': summary})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def retry_failed(self, request):
        """Retry all failed webhook deliveries."""
        try:
            from celery import current_app
            hours = int(request.data.get('hours', 6))
            current_app.send_task('api.webhooks.tasks.retry_failed_deliveries', args=[hours])
            return Response({'success': True, 'queued': True, 'hours': hours})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def toggle_endpoint(self, request):
        """Enable/disable a webhook endpoint."""
        try:
            from api.webhooks.models import WebhookEndpoint
            endpoint_id = request.data.get('endpoint_id')
            ep = WebhookEndpoint.objects.get(pk=endpoint_id)
            ep.is_active = not ep.is_active
            ep.save(update_fields=['is_active'])
            return Response({'success': True, 'endpoint_id': endpoint_id, 'is_active': ep.is_active})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def test_endpoint(self, request):
        """Send a test event to a webhook endpoint."""
        try:
            endpoint_id = request.data.get('endpoint_id')
            from api.webhooks.models import WebhookEndpoint
            ep = WebhookEndpoint.objects.get(pk=endpoint_id)
            from api.admin_panel.INTEGRATION_SYSTEM.webhooks_integration import WebhookDelivery
            result = WebhookDelivery.deliver(
                url=ep.url,
                payload={'event': 'ping', 'test': True, 'timestamp': timezone.now().isoformat()},
                secret=ep.secret if hasattr(ep, 'secret') else '',
                event_type='ping',
                webhook_id=str(endpoint_id),
            )
            return Response({'success': result.get('success', False), 'result': result})
        except Exception as e:
            return Response({'error': str(e)}, status=400)