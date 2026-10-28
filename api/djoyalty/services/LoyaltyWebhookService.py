# api/djoyalty/services/LoyaltyWebhookService.py
"""
LoyaltyWebhookService -- outbound webhook management।
Register, dispatch, retry webhooks।
"""
import logging
from typing import List

logger = logging.getLogger(__name__)


class LoyaltyWebhookService:

    @staticmethod
    def register_endpoint(url: str, events: List[str], secret: str = None, name: str = '') -> dict:
        """Webhook endpoint register করো।"""
        from ..webhooks.webhook_registry import WebhookRegistry
        from ..validators import validate_https_url
        try:
            validate_https_url(url)
        except Exception as e:
            raise ValueError(f'Invalid webhook URL: {e}')
        endpoint = WebhookRegistry.register(url=url, events=events, secret=secret, name=name)
        logger.info('LoyaltyWebhookService: registered endpoint %s for %s', url, events)
        return endpoint

    @staticmethod
    def deregister_endpoint(url: str) -> bool:
        """Webhook endpoint remove করো।"""
        from ..webhooks.webhook_registry import WebhookRegistry
        result = WebhookRegistry.deregister(url)
        if result:
            logger.info('LoyaltyWebhookService: deregistered %s', url)
        return result

    @staticmethod
    def dispatch_event(event_type: str, customer=None, data: dict = None, tenant=None):
        """Loyalty event dispatch করো সব registered endpoints এ।"""
        from ..events.event_dispatcher import EventDispatcher
        return EventDispatcher.dispatch(event_type, customer=customer, data=data, tenant=tenant)

    @staticmethod
    def test_endpoint(url: str) -> dict:
        """Webhook endpoint test করো।"""
        from ..webhooks.webhook_retry import deliver_with_retry
        test_payload = {
            'event': 'webhook.test',
            'message': 'This is a test webhook from Djoyalty.',
            'timestamp': __import__('django.utils.timezone', fromlist=['timezone']).timezone.now().isoformat(),
        }
        success = deliver_with_retry(url, test_payload)
        return {'url': url, 'success': success, 'payload': test_payload}

    @staticmethod
    def get_all_endpoints() -> List[dict]:
        """সব registered webhook endpoints।"""
        from ..webhooks.webhook_registry import WebhookRegistry
        return WebhookRegistry.get_all_endpoints()

    @staticmethod
    def generate_webhook_secret() -> str:
        """New webhook signing secret generate করো।"""
        from ..webhooks.webhook_security import generate_secret
        return generate_secret()

    @staticmethod
    def verify_incoming_webhook(payload: bytes, signature: str, secret: str) -> bool:
        """Incoming webhook signature verify করো।"""
        from ..webhooks.webhook_security import verify_signature
        return verify_signature(payload, signature, secret)

    @staticmethod
    def get_supported_events() -> List[str]:
        """সব supported webhook event types।"""
        from ..webhooks.webhook_payloads import WEBHOOK_EVENTS
        return WEBHOOK_EVENTS
