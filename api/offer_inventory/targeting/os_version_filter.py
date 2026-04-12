# api/offer_inventory/targeting/os_version_filter.py
"""OS version-based offer filtering."""
import logging
from packaging import version as pkg_version

logger = logging.getLogger(__name__)


class OSVersionFilter:
    """Filter offers based on user's OS version."""

    # Minimum OS versions for offers (can be overridden per offer)
    MIN_VERSIONS = {
        'Android': '6.0',
        'iOS'    : '12.0',
        'Windows': '10',
        'macOS'  : '10.14',
    }

    @staticmethod
    def meets_requirement(user_os: str, user_version: str,
                           required_min: str = None,
                           required_max: str = None) -> bool:
        """Check if user's OS version meets offer requirements."""
        if not user_os or not user_version:
            return True  # Unknown OS — allow by default

        try:
            user_ver = pkg_version.parse(user_version)

            # Global minimum
            global_min = OSVersionFilter.MIN_VERSIONS.get(user_os)
            if global_min:
                if user_ver < pkg_version.parse(global_min):
                    return False

            # Offer-specific minimum
            if required_min:
                if user_ver < pkg_version.parse(required_min):
                    return False

            # Offer-specific maximum
            if required_max:
                if user_ver > pkg_version.parse(required_max):
                    return False

        except Exception:
            return True  # Parse error — allow

        return True

    @staticmethod
    def filter_offers(offers: list, user_os: str, user_os_version: str) -> list:
        """Filter offer list by OS version rules."""
        result = []
        for offer in offers:
            try:
                rules = offer.visibility_rules.filter(
                    rule_type='os_version', is_active=True
                )
                allowed = True
                for rule in rules:
                    vals = rule.values or []
                    # vals format: ["Android:8.0", "iOS:13.0"]
                    for val in vals:
                        if ':' in val:
                            req_os, req_ver = val.split(':', 1)
                            if req_os.lower() == user_os.lower():
                                if not OSVersionFilter.meets_requirement(
                                    user_os, user_os_version, req_ver
                                ):
                                    allowed = False
                                    break
                if allowed:
                    result.append(offer)
            except Exception:
                result.append(offer)
        return result


# ─────────────────────────────────────────────────────
# api/offer_inventory/targeting/browser_targeting.py
# ─────────────────────────────────────────────────────

class BrowserTargetingEngine:
    """Target offers based on browser type and version."""

    SUPPORTED_BROWSERS = [
        'Chrome', 'Firefox', 'Safari', 'Edge',
        'Opera', 'Samsung Internet', 'UCBrowser',
    ]

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
        """Check if browser is in supported list."""
        return any(b.lower() in browser.lower() for b in BrowserTargetingEngine.SUPPORTED_BROWSERS)


# ─────────────────────────────────────────────────────
# api/offer_inventory/targeting/language_filter.py
# ─────────────────────────────────────────────────────

class LanguageFilter:
    """Filter offers based on user's language preference."""

    @staticmethod
    def get_user_language(request) -> str:
        """Extract language from request headers."""
        accept_lang = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        if accept_lang:
            # Extract primary language (e.g., 'en-US,en;q=0.9' → 'en')
            primary = accept_lang.split(',')[0].split(';')[0].strip()
            return primary[:5].lower()
        return 'en'

    @staticmethod
    def filter_offers(offers: list, language: str) -> list:
        """Filter offers by language rules."""
        result = []
        for offer in offers:
            try:
                rules = offer.visibility_rules.filter(
                    rule_type='language', is_active=True
                )
                excluded = False
                for rule in rules:
                    vals = [v.lower() for v in (rule.values or [])]
                    lang = language.lower()[:2]  # Primary language code
                    if rule.operator == 'include' and lang not in vals and vals:
                        excluded = True
                        break
                    if rule.operator == 'exclude' and lang in vals:
                        excluded = True
                        break
                if not excluded:
                    result.append(offer)
            except Exception:
                result.append(offer)
        return result

    @staticmethod
    def localize_offer(offer, language: str) -> dict:
        """Return offer with localized content if available."""
        base = {
            'id'         : str(offer.id),
            'title'      : offer.title,
            'description': offer.description,
            'language'   : language,
        }
        # TODO: Integrate with CMS for multilingual content
        return base


# ─────────────────────────────────────────────────────
# api/offer_inventory/targeting/re_engagement_logic.py
# ─────────────────────────────────────────────────────

class ReEngagementEngine:
    """
    Re-engagement logic — target lapsed users with special offers.
    Identifies inactive users and serves them high-value offers.
    """

    INACTIVE_DAYS_THRESHOLD = 7    # Days without activity = inactive
    HIGH_VALUE_PAYOUT_MIN   = 0.5  # Minimum payout for re-engagement offers

    @staticmethod
    def get_reengagement_offers(user, limit: int = 5) -> list:
        """
        Get high-value offers for a lapsed user.
        Prioritizes: high payout + low completion + featured.
        """
        from api.offer_inventory.models import Offer, Conversion
        from django.db.models import Q

        # Exclude already completed
        done_ids = set(
            Conversion.objects.filter(
                user=user, status__name='approved'
            ).values_list('offer_id', flat=True)
        )

        offers = list(
            Offer.objects.filter(
                status='active',
                payout_amount__gte=ReEngagementEngine.HIGH_VALUE_PAYOUT_MIN,
            )
            .exclude(id__in=done_ids)
            .order_by('-is_featured', '-payout_amount', '-conversion_rate')
            [:limit]
        )
        return offers

    @staticmethod
    def is_user_lapsed(user) -> bool:
        """Check if user is considered lapsed/inactive."""
        from api.offer_inventory.models import Click
        from datetime import timedelta
        from django.utils import timezone

        since = timezone.now() - timedelta(days=ReEngagementEngine.INACTIVE_DAYS_THRESHOLD)
        return not Click.objects.filter(user=user, created_at__gte=since).exists()

    @staticmethod
    def get_lapsed_users(days: int = 14, limit: int = 10000) -> list:
        """Get list of lapsed user IDs for campaign targeting."""
        from api.offer_inventory.models import Click
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from datetime import timedelta

        User  = get_user_model()
        since = timezone.now() - timedelta(days=days)

        active_user_ids = set(
            Click.objects.filter(created_at__gte=since)
            .values_list('user_id', flat=True)
            .distinct()
        )
        return list(
            User.objects.filter(is_active=True)
            .exclude(id__in=active_user_ids)
            .values_list('id', flat=True)[:limit]
        )
