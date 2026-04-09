# api/djoyalty/webhooks/webhook_registry.py
"""
WebhookRegistry — outbound webhook endpoint registration।
In-memory registry; production এ database-backed implementation ব্যবহার করুন।
"""
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class WebhookRegistry:
    """
    Webhook endpoint registry।
    Stores URL, events, and secret for each endpoint।
    Thread-safe নয় — production এ DB-backed ব্যবহার করুন।
    """
    _endpoints: List[dict] = []

    @classmethod
    def register(cls, url: str, events: List[str], secret: Optional[str] = None, name: str = '') -> dict:
        """
        Webhook endpoint register করো।
        Args:
            url: Webhook destination URL (must be HTTPS)
            events: List of event types to subscribe to
            secret: HMAC signing secret (optional)
            name: Human-readable name for this endpoint
        Returns:
            Registered endpoint dict
        """
        if not url.startswith('https://'):
            logger.warning('WebhookRegistry: Non-HTTPS URL registered: %s', url)

        endpoint = {
            'url': url,
            'events': events,
            'secret': secret,
            'name': name or url,
            'is_active': True,
        }
        cls._endpoints.append(endpoint)
        logger.info('WebhookRegistry: Registered endpoint %s for events %s', url, events)
        return endpoint

    @classmethod
    def deregister(cls, url: str) -> bool:
        """URL দিয়ে endpoint remove করো।"""
        original_count = len(cls._endpoints)
        cls._endpoints = [ep for ep in cls._endpoints if ep['url'] != url]
        removed = original_count - len(cls._endpoints)
        if removed:
            logger.info('WebhookRegistry: Deregistered endpoint %s', url)
        return removed > 0

    @classmethod
    def get_endpoints_for_event(cls, event_type: str) -> List[dict]:
        """
        নির্দিষ্ট event type এর জন্য registered active endpoints।
        """
        return [
            ep for ep in cls._endpoints
            if ep.get('is_active', True) and event_type in ep.get('events', [])
        ]

    @classmethod
    def get_all_endpoints(cls) -> List[dict]:
        """সব registered endpoints।"""
        return list(cls._endpoints)

    @classmethod
    def clear(cls) -> None:
        """সব endpoints clear করো — testing এর জন্য।"""
        cls._endpoints = []
        logger.debug('WebhookRegistry: All endpoints cleared')

    @classmethod
    def disable(cls, url: str) -> bool:
        """Endpoint temporarily disable করো।"""
        for ep in cls._endpoints:
            if ep['url'] == url:
                ep['is_active'] = False
                return True
        return False

    @classmethod
    def enable(cls, url: str) -> bool:
        """Disabled endpoint re-enable করো।"""
        for ep in cls._endpoints:
            if ep['url'] == url:
                ep['is_active'] = True
                return True
        return False
