"""
viewsets/webhooks_views.py
Exposes two root-level modules over the API:
  1. WebhookViewSet         -> webhooks.py (WebhookManager, AlertWebhookManager)
  2. OutgoingWebhookViewSet -> hooks.py    (OutgoingWebhookManager, WebhookEventLogger)

Security model
  * Every management endpoint (list / register / unregister / get / send / test /
    stats / info and the whole OutgoingWebhookViewSet) is admin-only.
  * Secrets and credential-like headers are never returned (masked).
  * ``incoming`` needs an authenticated caller AND a registered ``webhook_id`` whose
    HMAC-SHA256 signature over the raw request body matches (``X-Signature``).
  * Registered webhooks live in the WebhookManager of the current process
    (in-memory). For durable, multi-worker webhooks configure
    AlertChannel(channel_type='webhook') instead.
"""
import hashlib
import hmac
import logging
import re

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .mixins import PASSTHROUGH_EXCEPTIONS  # re-raise 404/403/400 instead of 500

logger = logging.getLogger(__name__)

_MASK = '********'
_SENSITIVE_HEADER = re.compile(r'authorization|token|secret|api[-_]?key|password|cookie', re.I)
_WEBHOOK_ID = re.compile(r'^[A-Za-z0-9_.:\-]{1,100}$')
_SERVER_ERROR = {'error': 'Internal server error'}


def _data(request):
    """Request body as a dict (JSON arrays / scalars become an empty dict)."""
    data = request.data
    return data if hasattr(data, 'get') else {}


def _public_webhook(webhook):
    """Copy of a registered webhook that is safe to return to API clients."""
    data = webhook.to_dict() if hasattr(webhook, 'to_dict') else webhook
    if not isinstance(data, dict):
        return {}
    safe = dict(data)
    safe['has_secret'] = bool(safe.get('secret'))
    if safe.get('secret'):
        safe['secret'] = _MASK
    headers = safe.get('headers')
    if isinstance(headers, dict):
        safe['headers'] = {
            key: (_MASK if _SENSITIVE_HEADER.search(str(key)) else value)
            for key, value in headers.items()
        }
    return safe


def _signature_matches(raw_body, signature, secret):
    """Constant-time HMAC-SHA256 check over the raw body (accepts an ``sha256=`` prefix)."""
    if not secret or not isinstance(signature, str):
        return False
    if signature.lower().startswith('sha256='):
        signature = signature.split('=', 1)[1]
    expected = hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


class WebhookViewSet(viewsets.ViewSet):
    """
    Exposes webhooks.py -> WebhookManager.
    Endpoints: list, register, unregister, get, send, test, stats, incoming, info
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_permissions(self):
        if getattr(self, 'action', None) == 'incoming':
            # Authorization for inbound events comes from the HMAC signature.
            return [IsAuthenticated()]
        return super().get_permissions()

    def _get_manager(self):
        from api.alerts.webhooks import get_webhook_manager
        return get_webhook_manager()

    def list(self, request):
        """List all registered webhooks (secrets masked)"""
        try:
            mgr = self._get_manager()
            webhooks = mgr.get_all_webhooks() if hasattr(mgr, 'get_all_webhooks') else {}
            result = {key: _public_webhook(value) for key, value in webhooks.items()}
            return Response({'webhooks': result, 'count': len(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception:
            logger.exception("WebhookViewSet.list error")
            return Response(_SERVER_ERROR, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register a new webhook endpoint"""
        try:
            data = _data(request)
            webhook_id = data.get('webhook_id')
            url = data.get('url')
            secret = data.get('secret', '')
            events = data.get('events', ['alert_triggered'])
            if not webhook_id or not url:
                return Response({'error': 'webhook_id and url required'}, status=status.HTTP_400_BAD_REQUEST)
            if not isinstance(webhook_id, str) or not _WEBHOOK_ID.match(webhook_id):
                return Response({'error': 'webhook_id must be 1-100 chars of letters, digits, _ . : -'},
                                status=status.HTTP_400_BAD_REQUEST)
            if not isinstance(secret, str):
                return Response({'error': 'secret must be a string'}, status=status.HTTP_400_BAD_REQUEST)
            if not isinstance(events, list) or not all(isinstance(e, str) for e in events):
                return Response({'error': 'events must be a list of strings'}, status=status.HTTP_400_BAD_REQUEST)
            from api.alerts.validators import validate_webhook_url
            url_check = validate_webhook_url(url)
            if not url_check.get('valid', False):
                return Response({'error': 'Invalid webhook URL', 'details': url_check.get('errors', [])},
                                status=status.HTTP_400_BAD_REQUEST)
            self._get_manager().register_webhook(
                webhook_id=webhook_id,
                config={'url': url, 'secret': secret, 'events': events},
            )
            return Response({'success': True, 'webhook_id': webhook_id, 'url': url})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception:
            logger.exception("WebhookViewSet.register error")
            return Response(_SERVER_ERROR, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def unregister(self, request):
        """Unregister a webhook"""
        try:
            webhook_id = _data(request).get('webhook_id')
            if not webhook_id:
                return Response({'error': 'webhook_id required'}, status=status.HTTP_400_BAD_REQUEST)
            self._get_manager().unregister_webhook(webhook_id)
            return Response({'success': True, 'unregistered': webhook_id})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception:
            logger.exception("WebhookViewSet.unregister error")
            return Response(_SERVER_ERROR, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def get_webhook(self, request):
        """Get a specific webhook by ID (secret masked)"""
        try:
            webhook_id = request.query_params.get('webhook_id')
            if not webhook_id:
                return Response({'error': 'webhook_id required'}, status=status.HTTP_400_BAD_REQUEST)
            webhook = self._get_manager().get_webhook(webhook_id)
            if webhook is None:
                return Response({'error': 'Webhook not found'}, status=status.HTTP_404_NOT_FOUND)
            return Response({'webhook_id': webhook_id, 'webhook': _public_webhook(webhook)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception:
            logger.exception("WebhookViewSet.get_webhook error")
            return Response(_SERVER_ERROR, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def send(self, request):
        """Deliver an event to a registered webhook"""
        try:
            data = _data(request)
            webhook_id = data.get('webhook_id')
            payload = data.get('payload', {})
            event = data.get('event', 'manual')
            if not webhook_id:
                return Response({'error': 'webhook_id required'}, status=status.HTTP_400_BAD_REQUEST)
            mgr = self._get_manager()
            if mgr.get_webhook(webhook_id) is None:
                return Response({'error': 'Webhook not found'}, status=status.HTTP_404_NOT_FOUND)
            delivered = mgr.deliver_webhook(webhook_id=webhook_id, event_type=event, data=payload)
            return Response({'success': bool(delivered), 'webhook_id': webhook_id})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception:
            logger.exception("WebhookViewSet.send error")
            return Response(_SERVER_ERROR, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def test_webhook(self, request):
        """Send a test payload to a registered webhook"""
        try:
            from django.utils import timezone as dj_timezone
            webhook_id = _data(request).get('webhook_id')
            if not webhook_id:
                return Response({'error': 'webhook_id required'}, status=status.HTTP_400_BAD_REQUEST)
            mgr = self._get_manager()
            if mgr.get_webhook(webhook_id) is None:
                return Response({'error': 'Webhook not found'}, status=status.HTTP_404_NOT_FOUND)
            test_payload = {'test': True, 'message': 'Webhook test from Alerts system',
                            'timestamp': dj_timezone.now().isoformat()}
            # '*' subscribers and webhooks that list "test" receive it; others are skipped (not a failure)
            delivered = mgr.deliver_webhook(webhook_id=webhook_id, event_type='test', data=test_payload)
            return Response({'success': bool(delivered), 'webhook_id': webhook_id, 'test_sent': True})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception:
            logger.exception("WebhookViewSet.test_webhook error")
            return Response(_SERVER_ERROR, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def webhook_stats(self, request):
        """Webhook delivery statistics"""
        try:
            mgr = self._get_manager()
            stats = {}
            for webhook_id in mgr.get_all_webhooks():
                webhook_stats = mgr.get_webhook_stats(webhook_id)
                if webhook_stats is not None:
                    stats[webhook_id] = webhook_stats
            return Response(stats)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception:
            logger.exception("WebhookViewSet.webhook_stats error")
            return Response(_SERVER_ERROR, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def incoming(self, request):
        """
        Receive a signed inbound webhook event.

        Requires ``webhook_id`` (query string or X-Webhook-ID header) of a registered
        webhook that has a secret, and ``X-Signature`` = HMAC-SHA256(secret, raw body).
        """
        try:
            # Read the raw body BEFORE anything touches request.data (the stream can only be read once).
            raw_body = request.body
            webhook_id = request.query_params.get('webhook_id') or request.headers.get('X-Webhook-ID', '')
            if not webhook_id:
                return Response({'error': 'webhook_id required'}, status=status.HTTP_400_BAD_REQUEST)
            webhook = self._get_manager().get_webhook(webhook_id)
            if webhook is None:
                return Response({'error': 'Webhook not found'}, status=status.HTTP_404_NOT_FOUND)
            secret = webhook.get('secret') if isinstance(webhook, dict) else getattr(webhook, 'secret', '')
            if not secret:
                return Response({'error': 'Webhook has no signing secret configured'},
                                status=status.HTTP_403_FORBIDDEN)
            if not _signature_matches(raw_body, request.headers.get('X-Signature', ''), secret):
                return Response({'error': 'Invalid signature'}, status=status.HTTP_401_UNAUTHORIZED)

            data = _data(request)
            event = str(data.get('event') or request.headers.get('X-Event-Type') or 'unknown')
            event_data = data.get('data', {})
            if not isinstance(event_data, dict):
                return Response({'error': 'data must be an object'}, status=status.HTTP_400_BAD_REQUEST)

            from api.alerts.webhooks import process_alert_webhook_event, process_system_health_webhook_event
            normalized = event.replace('_', '.').lower()
            processed = True
            if normalized == 'alert.triggered':
                process_alert_webhook_event(event_data)
            elif normalized == 'system.health':
                process_system_health_webhook_event(event_data)
            else:
                processed = False
                logger.warning("Ignoring unknown inbound webhook event type: %s", event)
            return Response({'received': True, 'event': event, 'processed': processed})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception:
            logger.exception("WebhookViewSet.incoming error")
            return Response(_SERVER_ERROR, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def webhook_info(self, request):
        """Webhook system overview (secrets masked)"""
        try:
            all_webhooks = self._get_manager().get_all_webhooks()
            return Response({
                'total_webhooks': len(all_webhooks),
                'webhooks': {key: _public_webhook(value) for key, value in all_webhooks.items()},
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception:
            logger.exception("WebhookViewSet.webhook_info error")
            return Response(_SERVER_ERROR, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OutgoingWebhookViewSet(viewsets.ViewSet):
    """
    Exposes hooks.py -> OutgoingWebhookManager, WebhookEventLogger.
    Endpoints: list, trigger_outgoing, event_log, verify_signature, delivery_status
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get_outgoing_manager(self):
        from api.alerts.hooks import OutgoingWebhookManager
        return OutgoingWebhookManager()

    def _get_event_logger(self):
        from api.alerts.hooks import WebhookEventLogger
        return WebhookEventLogger()

    def list(self, request):
        """List outgoing webhook configurations (secrets masked)"""
        try:
            mgr = self._get_outgoing_manager()
            webhooks = mgr.get_all_webhooks() if hasattr(mgr, 'get_all_webhooks') else {}
            result = {key: _public_webhook(value) for key, value in webhooks.items()}
            return Response({'outgoing_webhooks': result, 'count': len(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception:
            logger.exception("OutgoingWebhookViewSet.list error")
            return Response(_SERVER_ERROR, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def trigger_outgoing(self, request):
        """
        Deliver an event to one registered webhook (``webhook_id``) or, when omitted,
        to every active registered webhook subscribed to ``event_type``.
        """
        try:
            from api.alerts.webhooks import get_webhook_manager
            data = _data(request)
            event_type = data.get('event_type', 'alert_triggered')
            payload = data.get('payload', {})
            webhook_id = data.get('webhook_id')
            mgr = get_webhook_manager()
            registered = mgr.get_all_webhooks()
            if webhook_id:
                if webhook_id not in registered:
                    return Response({'error': 'Webhook not found'}, status=status.HTTP_404_NOT_FOUND)
                targets = [webhook_id]
            else:
                targets = [wid for wid, hook in registered.items() if hook.get('active', True)]
            delivered = sum(1 for wid in targets if mgr.deliver_webhook(wid, event_type, payload))
            return Response({'success': True, 'event_type': event_type,
                             'attempted': len(targets), 'delivered': delivered})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception:
            logger.exception("OutgoingWebhookViewSet.trigger_outgoing error")
            return Response(_SERVER_ERROR, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def event_log(self, request):
        """Webhook event delivery log"""
        try:
            event_logger = self._get_event_logger()
            logs = event_logger.get_logs() if hasattr(event_logger, 'get_logs') else []
            result = [entry.to_dict() if hasattr(entry, 'to_dict') else str(entry) for entry in logs]
            return Response({'event_log': result, 'count': len(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception:
            logger.exception("OutgoingWebhookViewSet.event_log error")
            return Response(_SERVER_ERROR, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def verify_signature(self, request):
        """Verify a webhook HMAC signature against a registered webhook's secret"""
        try:
            from api.alerts.hooks import WebhookManager
            from api.alerts.webhooks import get_webhook_manager
            data = _data(request)
            payload = data.get('payload', '')
            signature = data.get('signature', '')
            webhook_id = data.get('webhook_id', '')
            if not all([payload, signature, webhook_id]):
                return Response({'error': 'payload, signature and webhook_id required'},
                                status=status.HTTP_400_BAD_REQUEST)
            if not isinstance(payload, str) or not isinstance(signature, str):
                return Response({'error': 'payload and signature must be strings'},
                                status=status.HTTP_400_BAD_REQUEST)
            webhook = get_webhook_manager().get_webhook(webhook_id)
            if not webhook:
                return Response({'error': 'Webhook not found'}, status=status.HTTP_404_NOT_FOUND)
            result = WebhookManager.verify_signature(
                payload=payload, signature=signature, secret=webhook.get('secret', ''))
            return Response({'valid': bool(result), 'webhook_id': webhook_id})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception:
            logger.exception("OutgoingWebhookViewSet.verify_signature error")
            return Response(_SERVER_ERROR, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def delivery_status(self, request):
        """Get webhook delivery status"""
        try:
            mgr = self._get_outgoing_manager()
            webhook_id = request.query_params.get('webhook_id')
            stats = mgr.get_delivery_stats(webhook_id) if hasattr(mgr, 'get_delivery_stats') else {}
            return Response({'delivery_status': stats})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception:
            logger.exception("OutgoingWebhookViewSet.delivery_status error")
            return Response(_SERVER_ERROR, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
