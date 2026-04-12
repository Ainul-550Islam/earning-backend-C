# api/offer_inventory/security_fraud/honeypot.py
"""
Honeypot System.
Invisible traps that only bots/scrapers trigger.
Real users never access these URLs.
"""
import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# URLs that should NEVER be accessed by real users
HONEYPOT_URLS = [
    '/api/offer-inventory/.env',
    '/api/offer-inventory/.git/',
    '/api/offer-inventory/debug/',
    '/api/offer-inventory/config/',
    '/api/offer-inventory/wp-admin/',
    '/api/offer-inventory/phpmyadmin/',
    '/api/offer-inventory/admin/setup/',
    '/api/offer-inventory/test-hidden/',
    '/api/offer-inventory/secret-offers/',
    '/api/offer-inventory/admin-login/',
]

# Hidden form field name (in HTML forms)
HONEYPOT_FIELD = 'website_url'   # Humans leave this blank; bots fill it


class HoneypotManager:
    """Honeypot trap management."""

    @staticmethod
    def is_trap_url(path: str) -> bool:
        """Check if path is a honeypot trap."""
        return any(path.startswith(trap) for trap in HONEYPOT_URLS)

    @staticmethod
    def trigger(request) -> str:
        """
        Process a honeypot trigger.
        Logs, blocks IP, returns threat category.
        """
        ip         = HoneypotManager._get_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        path       = request.path

        # Log honeypot trigger
        try:
            from api.offer_inventory.models import HoneypotLog
            HoneypotLog.objects.create(
                ip_address=ip,
                user_agent=user_agent[:500],
                trap_url  =path,
                payload   =str(dict(request.GET))[:500],
                is_bot    =True,
                blocked   =True,
            )
        except Exception as e:
            logger.error(f'HoneypotLog save error: {e}')

        # Auto-block IP for 72 hours
        from .ip_blacklist import IPBlacklistManager
        IPBlacklistManager.block(
            ip=ip, reason=f'honeypot_triggered:{path}',
            hours=72, source='honeypot'
        )

        # Increment threat score
        threat_key   = f'honeypot_hits:{ip}'
        hits         = cache.get(threat_key, 0) + 1
        cache.set(threat_key, hits, 86400)

        logger.warning(
            f'HONEYPOT TRIGGERED | ip={ip} | path={path} | '
            f'ua={user_agent[:60]} | hits={hits}'
        )

        category = 'scraper' if '.env' in path or '.git' in path else 'scanner'
        return category

    @staticmethod
    def check_form_honeypot(post_data: dict) -> bool:
        """
        Check if the invisible form field was filled.
        Returns True if bot (field not empty).
        """
        value = post_data.get(HONEYPOT_FIELD, '').strip()
        if value:
            logger.warning(f'Form honeypot triggered: field={HONEYPOT_FIELD} value={value[:50]}')
            return True
        return False

    @staticmethod
    def get_trap_urls() -> list:
        return HONEYPOT_URLS

    @staticmethod
    def _get_ip(request) -> str:
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')
