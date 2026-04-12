# api/offer_inventory/device_targeting.py
"""
Device Targeting Engine.
Routes offers based on device type, OS, browser, screen size.
"""
import re
import logging
from typing import Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)

# OS version mappings
ANDROID_MIN_VERSION = '5.0'
IOS_MIN_VERSION     = '12.0'


class DeviceTargetingEngine:
    """Device-based offer filtering and routing."""

    @staticmethod
    def detect(user_agent: str) -> dict:
        """
        Detect full device profile from User-Agent string.
        Returns dict with device_type, os, os_version, browser,
        browser_version, is_mobile, is_tablet, screen_class.
        """
        cache_key = f'device_ua:{hash(user_agent)}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        try:
            from user_agents import parse as ua_parse
            ua = ua_parse(user_agent)
            result = {
                'device_type'    : ('mobile'  if ua.is_mobile  else
                                    'tablet'  if ua.is_tablet  else
                                    'bot'     if ua.is_bot     else 'desktop'),
                'os'             : ua.os.family,
                'os_version'     : ua.os.version_string,
                'browser'        : ua.browser.family,
                'browser_version': ua.browser.version_string,
                'is_mobile'      : ua.is_mobile,
                'is_tablet'      : ua.is_tablet,
                'is_bot'         : ua.is_bot,
                'screen_class'   : DeviceTargetingEngine._screen_class(ua.is_mobile, ua.is_tablet),
            }
        except ImportError:
            result = DeviceTargetingEngine._regex_detect(user_agent)

        cache.set(cache_key, result, 3600)
        return result

    @staticmethod
    def _regex_detect(ua: str) -> dict:
        """Fallback regex-based detection."""
        ua_lower = ua.lower()
        is_bot    = bool(re.search(r'bot|crawl|spider|headless', ua_lower))
        is_tablet = bool(re.search(r'ipad|android.*tablet', ua_lower))
        is_mobile = not is_tablet and bool(re.search(r'android|iphone|ipod|blackberry|windows phone', ua_lower))

        os_name = 'Unknown'
        if 'android' in ua_lower:
            m = re.search(r'android ([\d.]+)', ua_lower)
            os_name = 'Android'
        elif 'iphone' in ua_lower or 'ipad' in ua_lower:
            os_name = 'iOS'
        elif 'windows' in ua_lower:
            os_name = 'Windows'
        elif 'mac os' in ua_lower:
            os_name = 'macOS'

        return {
            'device_type'    : 'bot' if is_bot else ('tablet' if is_tablet else ('mobile' if is_mobile else 'desktop')),
            'os'             : os_name,
            'os_version'     : '',
            'browser'        : 'Unknown',
            'browser_version': '',
            'is_mobile'      : is_mobile,
            'is_tablet'      : is_tablet,
            'is_bot'         : is_bot,
            'screen_class'   : 'small' if is_mobile else ('medium' if is_tablet else 'large'),
        }

    @staticmethod
    def _screen_class(is_mobile: bool, is_tablet: bool) -> str:
        if is_mobile:  return 'small'
        if is_tablet:  return 'medium'
        return 'large'

    # ── Offer filtering ────────────────────────────────────────────

    @staticmethod
    def filter_offers_for_device(offers: list, device_type: str,
                                  os: str = '', os_version: str = '') -> list:
        """Filter offers based on device targeting rules."""
        result = []
        for offer in offers:
            if DeviceTargetingEngine.offer_allowed_for(offer, device_type, os):
                result.append(offer)
        return result

    @staticmethod
    def offer_allowed_for(offer, device_type: str, os: str = '') -> bool:
        """Check device visibility rules for an offer."""
        try:
            rules = offer.visibility_rules.filter(rule_type='device', is_active=True)
            for rule in rules:
                vals = [v.lower() for v in (rule.values or [])]
                dt   = device_type.lower()
                if rule.operator == 'include' and dt not in vals:
                    return False
                if rule.operator == 'exclude' and dt in vals:
                    return False

            # OS rules
            os_rules = offer.visibility_rules.filter(rule_type='os', is_active=True)
            for rule in os_rules:
                vals = [v.lower() for v in (rule.values or [])]
                if rule.operator == 'include' and os.lower() not in vals:
                    return False
                if rule.operator == 'exclude' and os.lower() in vals:
                    return False
        except Exception:
            pass
        return True

    # ── Analytics ──────────────────────────────────────────────────

    @staticmethod
    def get_device_breakdown(days: int = 7) -> list:
        """Click/conversion breakdown by device type."""
        from api.offer_inventory.models import Click
        from django.db.models import Count
        from datetime import timedelta
        from django.utils import timezone

        since = timezone.now() - timedelta(days=days)
        return list(
            Click.objects.filter(created_at__gte=since, is_fraud=False)
            .values('device_type')
            .annotate(
                clicks     =Count('id'),
                conversions=Count('conversion'),
            )
            .order_by('-clicks')
        )

    @staticmethod
    def get_os_breakdown(days: int = 7) -> list:
        """Click breakdown by OS."""
        from api.offer_inventory.models import Click
        from django.db.models import Count
        from datetime import timedelta
        from django.utils import timezone

        since = timezone.now() - timedelta(days=days)
        return list(
            Click.objects.filter(created_at__gte=since, is_fraud=False)
            .exclude(os='')
            .values('os')
            .annotate(clicks=Count('id'))
            .order_by('-clicks')[:15]
        )
