"""
api/tasks/webhooks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Webhook management views and utilities.
Handles advertiser webhook registration, testing, and incoming postbacks.
"""

import logging
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.request import Request

from api.tasks.permissions import HasValidPostbackSignature
from api.tasks.throttling import PostbackThrottle, AnonPostbackThrottle
from api.tasks.dependencies import extract_postback_data, get_client_ip

logger = logging.getLogger(__name__)


class WebhookEndpointViewSet(viewsets.ViewSet):
    """
    ViewSet for managing advertiser webhook/postback endpoints.
    POST /webhooks/            — Register a new webhook
    GET  /webhooks/            — List registered webhooks
    POST /webhooks/{id}/test/  — Test a webhook endpoint
    DELETE /webhooks/{id}/     — Delete a webhook
    """

    def get_permissions(self):
        if self.action in ('incoming_postback', 'cpalead_postback'):
            return [AllowAny()]
        return [IsAuthenticated()]

    def list(self, request):
        try:
            from webhooks.models import WebhookEndpoint
            endpoints = WebhookEndpoint.objects.filter(
                user=request.user
            ).values('id', 'url', 'event_types', 'is_active', 'created_at')
            return Response({'results': list(endpoints)})
        except ImportError:
            return Response({'results': []})

    def create(self, request):
        url         = request.data.get('url', '')
        event_types = request.data.get('event_types', ['conversion'])
        if not url:
            return Response({'error': 'URL is required.'}, status=400)
        try:
            from webhooks.models import WebhookEndpoint
            ep = WebhookEndpoint.objects.create(
                user=request.user, url=url, event_types=event_types,
                is_active=True, created_at=timezone.now()
            )
            return Response({'id': ep.pk, 'url': url, 'status': 'created'}, status=201)
        except ImportError:
            return Response({'status': 'created', 'url': url}, status=201)

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Fire a test ping to the webhook URL."""
        from api.tasks.webhook_tasks import test_webhook_endpoint
        result = test_webhook_endpoint.apply(kwargs={'endpoint_id': pk, 'url': request.data.get('url', '')}).get()
        return Response(result)


# ── Postback / S2S Endpoints ───────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def incoming_postback(request: Request):
    """
    Universal S2S postback endpoint.
    Accepts: GET or POST with click_id, offer_id, payout, status
    URL: /tasks/postback/
    """
    throttle = AnonPostbackThrottle()
    if not throttle.allow_request(request, None):
        return Response({'status': 'rate_limited'}, status=429)

    try:
        data = extract_postback_data(request)
    except Exception as e:
        return Response({'status': 'invalid', 'error': str(e)}, status=400)

    try:
        from api.tasks.cpalead_tasks import cpalead_process_postback
        result = cpalead_process_postback.apply_async(
            kwargs={'postback_data': data},
            queue='high',
        )
        return Response({'status': 'received', 'task_id': result.id})
    except Exception as e:
        logger.error(f"[POSTBACK] Error queuing: {e}")
        return Response({'status': 'error'}, status=500)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cpalead_postback(request: Request):
    """
    CPAlead-compatible postback endpoint.
    URL: /tasks/cpalead/postback/
    Params: click_id, offer_id, payout, status, pub_id
    """
    return incoming_postback(request)


@api_view(['GET'])
@permission_classes([AllowAny])
def mmp_postback(request: Request, mmp: str = 'appsflyer'):
    """
    MMP (AppsFlyer, Adjust, Kochava) install postback.
    URL: /tasks/mmp/{mmp}/postback/
    """
    try:
        from api.tasks.cpi_tasks import process_app_install_event
        params   = dict(request.query_params)
        flat     = {k: (v[0] if isinstance(v, list) else v) for k, v in params.items()}
        result   = process_app_install_event.apply_async(kwargs={
            'click_id':     flat.get('click_id', flat.get('aff_sub', '')),
            'app_id':       flat.get('app_id', ''),
            'bundle_id':    flat.get('bundle_id', flat.get('app_bundle_id', '')),
            'platform':     flat.get('platform', 'android'),
            'device_id':    flat.get('device_id', flat.get('idfa', flat.get('gaid', ''))),
            'install_time': flat.get('install_time', ''),
            'publisher_id': int(flat.get('publisher_id', flat.get('pid', 0)) or 0),
            'mmp_name':     mmp,
        }, queue='high')
        return Response({'status': 'received', 'task_id': result.id})
    except Exception as e:
        logger.error(f"[MMP POSTBACK] {mmp}: {e}")
        return Response({'status': 'error'}, status=500)


__all__ = [
    'WebhookEndpointViewSet', 'incoming_postback',
    'cpalead_postback', 'mmp_postback',
]
