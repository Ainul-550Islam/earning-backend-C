# api/offer_inventory/targeting/browser_targeting.py
"""
Browser Targeting Engine.
Filter and route offers based on user's browser type and version.
Supports: Chrome, Firefox, Safari, Edge, Opera, Samsung Internet.
"""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

SUPPORTED_BROWSERS = [
    'Chrome', 'Firefox', 'Safari', 'Edge',
    'Opera', 'Samsung Internet', 'UCBrowser',
    'Brave', 'Vivaldi',
]

BROWSER_RISK = {
    'Unknown': 30.0,
    'bot'     : 100.0,
}


class BrowserTargetingEngine:
    """Target offers based on browser type and version."""

    @staticmethod
    def detect_browser(user_agent: str) -> dict:
        """Detect browser from User-Agent string."""
        cache_key = f'browser_detect:{hash(user_agent)}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        result = {'browser': 'Unknown', 'version': '', 'is_supported': False}
        try:
            from user_agents import parse as ua_parse
            ua = ua_parse(user_agent)
            result = {
                'browser'     : ua.browser.family,
                'version'     : ua.browser.version_string,
                'is_supported': ua.browser.family in SUPPORTED_BROWSERS,
                'is_bot'      : ua.is_bot,
                'is_mobile'   : ua.is_mobile,
            }
        except ImportError:
            import re
            ua_lower = user_agent.lower()
            if 'chrome' in ua_lower:
                result = {'browser': 'Chrome', 'version': '', 'is_supported': True, 'is_bot': False, 'is_mobile': False}
            elif 'firefox' in ua_lower:
                result = {'browser': 'Firefox', 'version': '', 'is_supported': True, 'is_bot': False, 'is_mobile': False}
            elif 'safari' in ua_lower:
                result = {'browser': 'Safari', 'version': '', 'is_supported': True, 'is_bot': False, 'is_mobile': False}

        cache.set(cache_key, result, 3600)
        return result

    @staticmethod
    def filter_offers(offers: list, browser: str) -> list:
        """Filter offers by browser targeting rules."""
        result = []
        for offer in offers:
            try:
                rules = offer.visibility_rules.filter(
                    rule_type='browser', is_active=True
                )
                excluded = False
                for rule in rules:
                    vals = [v.lower() for v in (rule.values or [])]
                    b    = browser.lower() if browser else ''
                    if rule.operator == 'include' and b not in vals and vals:
                        excluded = True
                        break
                    if rule.operator == 'exclude' and b in vals:
                        excluded = True
                        break
                if not excluded:
                    result.append(offer)
            except Exception:
                result.append(offer)
        return result

    @staticmethod
    def is_supported_browser(browser: str) -> bool:
        """Check if browser is officially supported."""
        return any(b.lower() in browser.lower() for b in SUPPORTED_BROWSERS)

    @staticmethod
    def get_risk_score(browser: str) -> float:
        """Risk score based on browser type."""
        return BROWSER_RISK.get(browser, 0.0)

    @staticmethod
    def get_browser_breakdown(days: int = 7) -> list:
        """Click breakdown by browser type."""
        from api.offer_inventory.models import Click
        from django.db.models import Count
        from datetime import timedelta
        from django.utils import timezone

        since = timezone.now() - timedelta(days=days)
        return list(
            Click.objects.filter(created_at__gte=since, is_fraud=False)
            .exclude(browser='')
            .values('browser')
            .annotate(clicks=Count('id'))
            .order_by('-clicks')[:15]
        )
