# api/offer_inventory/targeting/language_filter.py
"""
Language Filter — Target offers based on user's language preference.
Supports BN, EN, HI, AR, UR, FR, DE, ES.
"""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    'bn': 'বাংলা',
    'en': 'English',
    'hi': 'हिन्दी',
    'ar': 'العربية',
    'ur': 'اردو',
    'fr': 'Français',
    'de': 'Deutsch',
    'es': 'Español',
}

RTL_LANGUAGES = {'ar', 'ur', 'he', 'fa'}


class LanguageFilter:
    """Filter and route offers based on user's language."""

    @staticmethod
    def get_user_language(request) -> str:
        """Extract language from request headers or user profile."""
        # Check stored preference first
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                from api.offer_inventory.models import UserLanguage
                pref = UserLanguage.objects.get(user=request.user)
                return pref.primary_language
            except Exception:
                pass

        # Detect from Accept-Language header
        accept_lang = request.META.get('HTTP_ACCEPT_LANGUAGE', 'en')
        lang = accept_lang.split(',')[0].split(';')[0].strip()[:2].lower()
        return lang if lang in SUPPORTED_LANGUAGES else 'en'

    @staticmethod
    def filter_offers(offers: list, language: str) -> list:
        """Filter offers by language targeting rules."""
        result = []
        for offer in offers:
            try:
                rules = offer.visibility_rules.filter(
                    rule_type='language', is_active=True
                )
                excluded = False
                for rule in rules:
                    vals = [v.lower() for v in (rule.values or [])]
                    lang = language.lower()[:2]
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
    def is_rtl(language: str) -> bool:
        """Check if language is right-to-left."""
        return language.lower()[:2] in RTL_LANGUAGES

    @staticmethod
    def get_language_name(code: str) -> str:
        """Get display name for language code."""
        return SUPPORTED_LANGUAGES.get(code.lower()[:2], code)

    @staticmethod
    def set_user_language(user, language: str) -> object:
        """Save user's language preference."""
        from api.offer_inventory.models import UserLanguage
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f'Unsupported language: {language}')
        obj, _ = UserLanguage.objects.update_or_create(
            user=user, defaults={'primary_language': language}
        )
        return obj

    @staticmethod
    def localize_offer(offer, language: str = 'bn') -> dict:
        """Return offer with localized content."""
        return {
            'id'           : str(offer.id),
            'title'        : offer.title,
            'description'  : offer.description,
            'reward_amount': str(offer.reward_amount),
            'language'     : language,
            'is_rtl'       : LanguageFilter.is_rtl(language),
        }

    @staticmethod
    def get_language_breakdown(days: int = 7) -> list:
        """User language distribution from UserLanguage model."""
        from api.offer_inventory.models import UserLanguage
        from django.db.models import Count
        return list(
            UserLanguage.objects.values('primary_language')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
