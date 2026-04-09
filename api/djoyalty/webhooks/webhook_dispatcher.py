# api/djoyalty/webhooks/webhook_dispatcher.py
import json
import logging
from .webhook_payloads import build_payload
from .webhook_registry import WebhookRegistry
from .webhook_security import sign_payload
from .webhook_retry import deliver_with_retry

logger = logging.getLogger(__name__)

class WebhookDispatcher:
    @staticmethod
    def dispatch(event):
        endpoints = WebhookRegistry.get_endpoints_for_event(event.event_type)
        payload = build_payload(event)
        payload_bytes = json.dumps(payload).encode('utf-8')
        for endpoint in endpoints:
            try:
                headers = {}
                if endpoint.get('secret'):
                    headers['X-Loyalty-Signature'] = sign_payload(payload_bytes, endpoint['secret'])
                deliver_with_retry(endpoint['url'], payload, headers=headers)
            except Exception as e:
                logger.error('Webhook dispatch error for %s: %s', endpoint['url'], e)
