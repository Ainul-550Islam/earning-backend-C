# api/offer_inventory/compliance_legal/cookie_policy.py
"""Cookie Policy Manager — Cookie consent management (GDPR/ePrivacy)."""
import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

COOKIE_CATEGORIES = ['necessary', 'analytics', 'marketing', 'preferences']
COOKIE_TTL        = 86400 * 365   # 1 year


class CookiePolicyManager:
    """Manage cookie consent choices."""

    @staticmethod
    def record_consent(identifier: str, categories: list, ip: str = ''):
        """Record cookie consent for a user or session ID."""
        data = {
            'categories': [c for c in categories if c in COOKIE_CATEGORIES],
            'timestamp' : timezone.now().isoformat(),
            'ip'        : ip,
        }
        cache.set(f'cookie_consent:{identifier}', data, COOKIE_TTL)

    @staticmethod
    def get_consent(identifier: str) -> dict:
        """Get stored cookie consent."""
        return cache.get(f'cookie_consent:{identifier}', {'categories': ['necessary']})

    @staticmethod
    def has_analytics_consent(identifier: str) -> bool:
        """Check if analytics cookies are consented."""
        return 'analytics' in CookiePolicyManager.get_consent(identifier).get('categories', [])

    @staticmethod
    def has_marketing_consent(identifier: str) -> bool:
        """Check if marketing cookies are consented."""
        return 'marketing' in CookiePolicyManager.get_consent(identifier).get('categories', [])

    @staticmethod
    def get_all_categories() -> list:
        """Return all cookie categories with descriptions."""
        return [
            {'name': 'necessary',   'required': True,  'description': 'Essential for the site to function.'},
            {'name': 'analytics',   'required': False, 'description': 'Help us understand usage patterns.'},
            {'name': 'marketing',   'required': False, 'description': 'Personalized offers and promotions.'},
            {'name': 'preferences', 'required': False, 'description': 'Remember your preferences.'},
        ]
