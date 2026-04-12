# api/offer_inventory/misc_features/multi_language_support.py
"""
Misc Features Package — all 6 modules.
Multi-language support, dark mode assets, documentation builder,
legacy support, system recovery, analytics dashboard.
"""
import logging
import json
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════
# 1. MULTI-LANGUAGE SUPPORT
# ════════════════════════════════════════════════════════

class MultiLanguageSupport:
    """
    Internationalization (i18n) support for the offer inventory.
    Supports: Bengali (bn), English (en), Hindi (hi), Arabic (ar).
    """

    SUPPORTED_LANGUAGES = {
        'bn': 'বাংলা',
        'en': 'English',
        'hi': 'हिन्दी',
        'ar': 'العربية',
        'ur': 'اردو',
    }

    # UI string translations
    TRANSLATIONS = {
        'offer_wall_title': {
            'bn': 'অফার সম্পন্ন করুন এবং আয় করুন',
            'en': 'Complete Offers and Earn',
            'hi': 'ऑफर पूरा करें और कमाएं',
            'ar': 'أكمل العروض واربح',
        },
        'no_offers': {
            'bn': 'এই মুহূর্তে কোনো অফার নেই।',
            'en': 'No offers available right now.',
            'hi': 'अभी कोई ऑफर उपलब्ध नहीं है।',
            'ar': 'لا توجد عروض متاحة الآن.',
        },
        'earn_label': {
            'bn': 'আয় করুন',
            'en': 'Earn',
            'hi': 'कमाएं',
            'ar': 'اكسب',
        },
        'complete_label': {
            'bn': 'সম্পন্ন করুন',
            'en': 'Complete',
            'hi': 'पूरा करें',
            'ar': 'أكمل',
        },
        'withdraw_label': {
            'bn': 'উইথড্রয়াল',
            'en': 'Withdraw',
            'hi': 'निकालें',
            'ar': 'سحب',
        },
        'balance_label': {
            'bn': 'ব্যালেন্স',
            'en': 'Balance',
            'hi': 'शेष राशि',
            'ar': 'الرصيد',
        },
    }

    @classmethod
    def get_string(cls, key: str, language: str = 'bn') -> str:
        """Get translated string for a key."""
        lang_strings = cls.TRANSLATIONS.get(key, {})
        return lang_strings.get(language) or lang_strings.get('en', key)

    @classmethod
    def get_all_strings(cls, language: str = 'bn') -> dict:
        """Get all UI strings for a language."""
        return {key: cls.get_string(key, language) for key in cls.TRANSLATIONS}

    @classmethod
    def translate_offer(cls, offer, language: str = 'bn') -> dict:
        """Return offer data with translated content."""
        from api.offer_inventory.models import DocumentationSnippet

        base = {
            'id'           : str(offer.id),
            'title'        : offer.title,
            'description'  : offer.description,
            'reward_amount': str(offer.reward_amount),
            'language'     : language,
        }

        # Try to find localized content
        try:
            localized = DocumentationSnippet.objects.filter(
                slug=f'offer_{offer.id}_desc',
                language=language,
                is_published=True,
            ).first()
            if localized:
                base['description'] = localized.content
        except Exception:
            pass

        return base

    @classmethod
    def detect_language(cls, request) -> str:
        """Auto-detect user's preferred language from request."""
        # Check stored preference
        if request.user.is_authenticated:
            try:
                from api.offer_inventory.models import UserLanguage
                pref = UserLanguage.objects.get(user=request.user)
                return pref.primary_language
            except Exception:
                pass

        # Detect from Accept-Language header
        accept_lang = request.META.get('HTTP_ACCEPT_LANGUAGE', 'en')
        lang = accept_lang.split(',')[0].split(';')[0].strip()[:2].lower()
        return lang if lang in cls.SUPPORTED_LANGUAGES else 'en'

    @classmethod
    def set_user_language(cls, user, language: str) -> object:
        """Save user's language preference."""
        from api.offer_inventory.models import UserLanguage
        if language not in cls.SUPPORTED_LANGUAGES:
            raise ValueError(f'Unsupported language: {language}')
        obj, _ = UserLanguage.objects.update_or_create(
            user=user,
            defaults={'primary_language': language}
        )
        return obj


# ════════════════════════════════════════════════════════
# 2. DARK MODE ASSETS
# ════════════════════════════════════════════════════════

class DarkModeAssetManager:
    """
    Manage dark/light mode UI assets for the offerwall.
    Returns appropriate CSS variables and asset URLs per theme.
    """

    THEMES = {
        'light': {
            'background'  : '#FFFFFF',
            'surface'     : '#F8F9FA',
            'primary'     : '#6C63FF',
            'secondary'   : '#FF6584',
            'text'        : '#212529',
            'text_muted'  : '#6C757D',
            'border'      : '#DEE2E6',
            'success'     : '#28A745',
            'warning'     : '#FFC107',
            'danger'      : '#DC3545',
            'card_bg'     : '#FFFFFF',
            'shadow'      : 'rgba(0,0,0,0.1)',
        },
        'dark': {
            'background'  : '#0D1117',
            'surface'     : '#161B22',
            'primary'     : '#7C74FF',
            'secondary'   : '#FF7A95',
            'text'        : '#E6EDF3',
            'text_muted'  : '#8B949E',
            'border'      : '#30363D',
            'success'     : '#3FB950',
            'warning'     : '#D29922',
            'danger'      : '#F85149',
            'card_bg'     : '#161B22',
            'shadow'      : 'rgba(0,0,0,0.5)',
        },
        'cyberpunk': {
            'background'  : '#0A0A0F',
            'surface'     : '#12121F',
            'primary'     : '#00FFB3',
            'secondary'   : '#FF00A0',
            'text'        : '#E0E0FF',
            'text_muted'  : '#8080A0',
            'border'      : '#2A2A4A',
            'success'     : '#00FF88',
            'warning'     : '#FFE000',
            'danger'      : '#FF003C',
            'card_bg'     : '#12121F',
            'shadow'      : 'rgba(0,255,179,0.1)',
        },
    }

    @classmethod
    def get_theme(cls, theme_name: str = 'dark') -> dict:
        """Get theme CSS variables."""
        return cls.THEMES.get(theme_name, cls.THEMES['light'])

    @classmethod
    def get_css_variables(cls, theme_name: str = 'dark') -> str:
        """Generate CSS :root variables for a theme."""
        theme = cls.get_theme(theme_name)
        lines = [':root {']
        for key, value in theme.items():
            lines.append(f'  --oi-{key.replace("_", "-")}: {value};')
        lines.append('}')
        return '\n'.join(lines)

    @classmethod
    def get_user_theme(cls, user) -> str:
        """Get user's preferred theme."""
        try:
            from api.offer_inventory.models import UserProfile
            profile = UserProfile.objects.get(user=user)
            prefs   = profile.notification_prefs or {}
            return prefs.get('theme', 'dark')
        except Exception:
            return 'dark'

    @classmethod
    def set_user_theme(cls, user, theme: str) -> bool:
        """Save user's theme preference."""
        if theme not in cls.THEMES:
            return False
        from api.offer_inventory.models import UserProfile
        from django.db.models import F
        profile, _ = UserProfile.objects.get_or_create(user=user)
        prefs = profile.notification_prefs or {}
        prefs['theme'] = theme
        UserProfile.objects.filter(user=user).update(notification_prefs=prefs)
        return True


# ════════════════════════════════════════════════════════
# 3. DOCUMENTATION BUILDER
# ════════════════════════════════════════════════════════

class DocumentationBuilder:
    """Auto-generate API documentation from code."""

    @staticmethod
    def get_endpoint_docs() -> list:
        """Get all documented API endpoints."""
        from api.offer_inventory.urls import urlpatterns
        endpoints = []
        for pattern in urlpatterns:
            try:
                name = getattr(pattern, 'name', '')
                url  = str(pattern.pattern)
                endpoints.append({
                    'url' : f'/api/offer-inventory/{url}',
                    'name': name,
                })
            except Exception:
                pass
        return endpoints

    @staticmethod
    def generate_postman_collection() -> dict:
        """Generate a Postman collection JSON for all endpoints."""
        base_url = '{{base_url}}'
        items    = [
            {'name': 'List Offers',        'method': 'GET',  'url': f'{base_url}/api/offer-inventory/offers/'},
            {'name': 'Get Offer',          'method': 'GET',  'url': f'{base_url}/api/offer-inventory/offers/{{id}}/'},
            {'name': 'Record Click',       'method': 'POST', 'url': f'{base_url}/api/offer-inventory/offers/{{id}}/click/'},
            {'name': 'S2S Postback',       'method': 'POST', 'url': f'{base_url}/api/offer-inventory/postback/'},
            {'name': 'My Wallet',          'method': 'GET',  'url': f'{base_url}/api/offer-inventory/me/wallet/'},
            {'name': 'Request Withdrawal', 'method': 'POST', 'url': f'{base_url}/api/offer-inventory/withdrawals/'},
            {'name': 'Platform KPIs',      'method': 'GET',  'url': f'{base_url}/api/offer-inventory/analytics/kpis/'},
            {'name': 'Health Check',       'method': 'GET',  'url': f'{base_url}/api/offer-inventory/health/'},
        ]
        return {
            'info'    : {'name': 'Offer Inventory API v2', 'schema': 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json'},
            'item'    : items,
            'variable': [{'key': 'base_url', 'value': 'https://yourplatform.com'}],
        }


# ════════════════════════════════════════════════════════
# 4. LEGACY SUPPORT
# ════════════════════════════════════════════════════════

class LegacySupport:
    """Backward compatibility helpers for older integrations."""

    @staticmethod
    def convert_old_offer_format(old_offer: dict) -> dict:
        """Convert older offer data format to current schema."""
        return {
            'id'           : old_offer.get('offer_id') or old_offer.get('id'),
            'title'        : old_offer.get('offer_name') or old_offer.get('name') or old_offer.get('title'),
            'description'  : old_offer.get('description', ''),
            'offer_url'    : old_offer.get('offer_url') or old_offer.get('url', ''),
            'payout_amount': old_offer.get('payout') or old_offer.get('amount', 0),
            'reward_amount': old_offer.get('coins') or old_offer.get('reward', 0),
            'status'       : 'active',
        }

    @staticmethod
    def convert_old_postback_params(params: dict) -> dict:
        """Convert legacy postback parameters to current format."""
        from api.offer_inventory.maintenance_logs import LegacyAPIBridge
        return LegacyAPIBridge.handle_v1_postback(params)

    @staticmethod
    def get_deprecated_endpoints() -> list:
        """List of deprecated endpoints with migration guidance."""
        return [
            {'deprecated': '/api/offers/', 'use_instead': '/api/offer-inventory/offers/', 'removed_in': 'v3.0'},
            {'deprecated': '/api/postback/', 'use_instead': '/api/offer-inventory/postback/', 'removed_in': 'v3.0'},
        ]


# ════════════════════════════════════════════════════════
# 5. SYSTEM RECOVERY
# ════════════════════════════════════════════════════════

class SystemRecovery:
    """
    System recovery procedures for common failure scenarios.
    Auto-recovery from Redis failures, DB overload, stuck tasks.
    """

    @staticmethod
    def recover_stuck_conversions(hours: int = 2) -> dict:
        """Find and recover conversions stuck in 'pending' status."""
        from api.offer_inventory.models import Conversion
        from api.offer_inventory.services import ConversionService

        cutoff = timezone.now() - timedelta(hours=hours)
        stuck  = Conversion.objects.filter(
            status__name='pending',
            created_at__lt=cutoff,
            offer__network__is_s2s_enabled=True,
        )
        count    = stuck.count()
        approved = 0

        for conv in stuck[:100]:
            try:
                ConversionService.approve_conversion(str(conv.id))
                approved += 1
            except Exception as e:
                logger.error(f'Recovery failed for {conv.id}: {e}')

        return {'stuck_found': count, 'recovered': approved}

    @staticmethod
    def recover_failed_payouts() -> dict:
        """Re-queue failed payout tasks."""
        from api.offer_inventory.models import Conversion
        from api.offer_inventory.tasks import process_approved_conversion_payout

        # Find approved conversions without payout (approved_at set but reward not credited)
        approved = Conversion.objects.filter(
            status__name='approved',
            approved_at__isnull=False,
        )
        requeued = 0
        for conv in approved[:200]:
            cache_key = f'payout_done:{conv.id}'
            if not cache.get(cache_key):
                process_approved_conversion_payout.delay(str(conv.id))
                requeued += 1

        return {'requeued': requeued}

    @staticmethod
    def clear_all_caches(tenant=None) -> dict:
        """Clear all application caches (use with caution)."""
        patterns = [
            'offers:*', 'offer_*', 'user_profile:*',
            'ip_bl:*', 'fraud_rules:*', 'dashboard_*',
            'kpi_*', 'feature:*', 'notif_unread:*',
        ]
        cleared = 0
        for pattern in patterns:
            try:
                if hasattr(cache, 'delete_pattern'):
                    cache.delete_pattern(pattern)
                    cleared += 1
            except Exception:
                pass
        logger.warning(f'Cache cleared: {cleared} patterns | tenant={tenant}')
        return {'patterns_cleared': cleared}

    @staticmethod
    def rebuild_offer_caps() -> dict:
        """Recalculate and reset offer cap counts from actual conversion data."""
        from api.offer_inventory.models import Offer, OfferCap, Conversion
        from django.db.models import Count

        fixed = 0
        for offer in Offer.objects.filter(status='active'):
            actual_count = Conversion.objects.filter(
                offer=offer, status__name='approved'
            ).count()
            caps_updated = OfferCap.objects.filter(
                offer=offer, cap_type='total'
            ).update(current_count=actual_count)
            if caps_updated:
                fixed += 1

        logger.info(f'Offer caps rebuilt: {fixed} offers')
        return {'offers_fixed': fixed}


# ════════════════════════════════════════════════════════
# 6. ANALYTICS DASHBOARD
# ════════════════════════════════════════════════════════

class AnalyticsDashboard:
    """
    Comprehensive analytics dashboard aggregator.
    Single call returns all dashboard data.
    """

    @classmethod
    def get_full_dashboard(cls, tenant=None, days: int = 7) -> dict:
        """Get complete analytics dashboard data in one call."""
        from api.offer_inventory.business.kpi_dashboard import KPIDashboard
        from api.offer_inventory.reporting_audit import AdminDashboardStats
        from api.offer_inventory.analytics import OfferAnalytics

        return {
            'summary'         : KPIDashboard.get_platform_kpis(days=days, tenant=tenant),
            'live_stats'      : AdminDashboardStats.get_live_stats(tenant=tenant),
            'conversion_funnel': AdminDashboardStats.get_conversion_funnel(days=days),
            'revenue_trend'   : OfferAnalytics.get_revenue_trend(tenant=tenant, days=days),
            'geo_breakdown'   : OfferAnalytics.get_geo_breakdown(days=days),
            'device_breakdown': OfferAnalytics.get_device_breakdown(days=days),
            'top_offers'      : OfferAnalytics.get_top_performers(metric='revenue', days=days, limit=5),
            'network_roi'     : KPIDashboard.network_roi_report(days=days),
            'forecast'        : KPIDashboard.forecast_revenue(days_ahead=30),
            'generated_at'    : timezone.now().isoformat(),
        }

    @classmethod
    def get_user_dashboard(cls, user) -> dict:
        """Analytics dashboard for a specific user."""
        from api.offer_inventory.user_behavior_analysis import EngagementScoreCalculator, ActivityHeatmapService
        from api.offer_inventory.marketing.referral_program import ReferralProgramManager
        from api.offer_inventory.finance_payment.wallet_integration import WalletIntegration

        return {
            'wallet'         : WalletIntegration.get_balance(user),
            'engagement'     : EngagementScoreCalculator.calculate(user),
            'heatmap'        : ActivityHeatmapService.get_user_heatmap(user),
            'best_send_time' : ActivityHeatmapService.get_best_send_time(user),
            'referral_stats' : ReferralProgramManager.get_stats(user),
        }
