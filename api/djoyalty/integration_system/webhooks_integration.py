# api/djoyalty/integration_system/webhooks_integration.py
"""
Webhooks Integration Manager।
Manages outbound webhook delivery, retry, verification।
Bridges integration_system ↔ djoyalty.webhooks।
"""
import hashlib
import hmac
import json
import logging
import time
from typing import Optional
import requests
from django.utils import timezone
from .integ_constants import WEBHOOK_MAX_RETRIES, WEBHOOK_RETRY_DELAYS, WEBHOOK_TIMEOUT
from .integ_exceptions import WebhookDeliveryError, WebhookMaxRetriesError

logger = logging.getLogger(__name__)


class WebhookIntegrationManager:
    """
    Outbound webhook manager।
    Handles: delivery, retry, signature, logging।

    Integrates with existing djoyalty.webhooks system।
    """

    @staticmethod
    def deliver(url: str, payload: dict, secret: str = '',
                 event_type: str = '', attempt: int = 1) -> bool:
        """
        Deliver webhook to URL।
        Returns True on success, raises WebhookDeliveryError on failure।
        """
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Djoyalty-Webhook/1.0',
            'X-Djoyalty-Event': event_type,
            'X-Djoyalty-Attempt': str(attempt),
            'X-Djoyalty-Timestamp': str(int(time.time())),
        }

        # Add HMAC signature
        body = json.dumps(payload, separators=(',', ':'))
        if secret:
            sig = hmac.new(
                secret.encode(), body.encode(), hashlib.sha256
            ).hexdigest()
            headers['X-Djoyalty-Signature'] = f'sha256={sig}'

        try:
            resp = requests.post(
                url, data=body, headers=headers, timeout=WEBHOOK_TIMEOUT,
            )
            if resp.status_code < 400:
                logger.debug('WebhookManager: delivered to %s (HTTP %d)', url, resp.status_code)
                return True
            raise WebhookDeliveryError(url, status_code=resp.status_code, attempt=attempt)
        except requests.exceptions.Timeout:
            raise WebhookDeliveryError(url, status_code=None, attempt=attempt)
        except requests.exceptions.ConnectionError:
            raise WebhookDeliveryError(url, status_code=None, attempt=attempt)

    @staticmethod
    def deliver_with_retry(url: str, payload: dict, secret: str = '',
                            event_type: str = '', max_retries: int = WEBHOOK_MAX_RETRIES) -> bool:
        """Deliver webhook with automatic retry (exponential backoff)।"""
        for attempt in range(1, max_retries + 1):
            try:
                return WebhookIntegrationManager.deliver(
                    url, payload, secret, event_type, attempt
                )
            except WebhookDeliveryError as e:
                logger.warning('WebhookManager: attempt %d/%d failed for %s: %s',
                               attempt, max_retries, url, e)
                if attempt < max_retries:
                    delay = WEBHOOK_RETRY_DELAYS[min(attempt - 1, len(WEBHOOK_RETRY_DELAYS) - 1)]
                    time.sleep(delay)
                else:
                    raise WebhookMaxRetriesError(url=url, status_code=e.status_code, attempt=attempt)
        return False

    @staticmethod
    def verify_incoming(body: bytes, signature: str, secret: str) -> bool:
        """Verify incoming webhook signature।"""
        if not secret or not signature:
            return not bool(secret)  # True if no secret required

        try:
            if signature.startswith('sha256='):
                signature = signature[7:]
            expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception as e:
            logger.error('WebhookIntegrationManager.verify_incoming error: %s', e)
            return False

    @staticmethod
    def build_loyalty_payload(event_type: str, customer, data: dict) -> dict:
        """Build standard loyalty webhook payload।"""
        from ..models.points import LoyaltyPoints
        try:
            lp = customer.loyalty_points.first()
            balance = str(lp.balance) if lp else '0'
        except Exception:
            balance = '0'

        return {
            'event': event_type,
            'customer': {
                'id': customer.id,
                'code': customer.code,
                'email': customer.email or '',
                'phone': customer.phone or '',
                'loyalty_number': customer.loyalty_number or customer.code,
            },
            'data': data,
            'balance': balance,
            'timestamp': timezone.now().isoformat(),
        }

    @staticmethod
    def dispatch_to_all_subscribers(event_type: str, customer, data: dict):
        """
        Dispatch webhook to all registered subscribers for this event।
        Delegates to existing webhook_registry।
        """
        try:
            from ..webhooks.webhook_registry import WebhookRegistry
            from ..webhooks.webhook_dispatcher import WebhookDispatcher
            payload = WebhookIntegrationManager.build_loyalty_payload(
                event_type, customer, data
            )
            WebhookDispatcher.dispatch(event_type, customer, data)
        except Exception as e:
            logger.debug('WebhookIntegrationManager.dispatch_to_all_subscribers error: %s', e)
