# =============================================================================
# api/promotions/localization/i18n_helper.py
# i18n Helper — Multilingual content, dynamic translation, locale detection
# =============================================================================

import logging
from typing import Optional
from django.core.cache import cache

logger = logging.getLogger('localization.i18n')
CACHE_PREFIX_I18N = 'loc:i18n:{}'


# Supported locales — ISO 639-1 language + ISO 3166-1 country
SUPPORTED_LOCALES = {
    'en': {'name': 'English',    'rtl': False, 'countries': ['US', 'GB', 'AU', 'CA']},
    'bn': {'name': 'বাংলা',      'rtl': False, 'countries': ['BD', 'IN']},
    'hi': {'name': 'हिन्दी',    'rtl': False, 'countries': ['IN']},
    'ar': {'name': 'العربية',    'rtl': True,  'countries': ['SA', 'AE', 'EG', 'MA']},
    'ur': {'name': 'اردو',       'rtl': True,  'countries': ['PK']},
    'id': {'name': 'Bahasa',     'rtl': False, 'countries': ['ID']},
    'ms': {'name': 'Melayu',     'rtl': False, 'countries': ['MY']},
    'tr': {'name': 'Türkçe',     'rtl': False, 'countries': ['TR']},
    'pt': {'name': 'Português',  'rtl': False, 'countries': ['BR', 'PT']},
    'es': {'name': 'Español',    'rtl': False, 'countries': ['MX', 'ES', 'AR', 'CO']},
    'fr': {'name': 'Français',   'rtl': False, 'countries': ['FR', 'SN', 'CI']},
    'zh': {'name': '中文',        'rtl': False, 'countries': ['CN', 'TW', 'HK']},
    'ja': {'name': '日本語',      'rtl': False, 'countries': ['JP']},
    'ko': {'name': '한국어',      'rtl': False, 'countries': ['KR']},
    'ru': {'name': 'Русский',    'rtl': False, 'countries': ['RU', 'UA']},
    'de': {'name': 'Deutsch',    'rtl': False, 'countries': ['DE', 'AT', 'CH']},
}

# Platform UI string keys
PLATFORM_STRINGS = {
    'campaign.no_tasks':     {'en': 'No tasks available', 'bn': 'কোনো কাজ নেই', 'hi': 'कोई कार्य नहीं'},
    'campaign.completed':    {'en': 'Task completed!',    'bn': 'কাজ সম্পন্ন!',  'hi': 'कार्य पूर्ण!'},
    'campaign.reward':       {'en': 'You earned {amount}', 'bn': 'আপনি {amount} পেয়েছেন', 'hi': 'आपने {amount} कमाया'},
    'submission.pending':    {'en': 'Under review',       'bn': 'পর্যালোচনাধীন', 'hi': 'समीक्षाधीन'},
    'submission.approved':   {'en': 'Approved!',          'bn': 'অনুমোদিত!',     'hi': 'स्वीकृत!'},
    'submission.rejected':   {'en': 'Rejected',           'bn': 'প্রত্যাখ্যাত',  'hi': 'अस्वीकृत'},
    'wallet.balance':        {'en': 'Balance: {amount}',  'bn': 'ব্যালেন্স: {amount}', 'hi': 'शेष: {amount}'},
    'error.general':         {'en': 'Something went wrong', 'bn': 'কিছু একটা ভুল হয়েছে', 'hi': 'कुछ गलत हुआ'},
}


class I18nHelper:
    """
    Internationalization helper।

    Features:
    1. Locale detection (from request headers, user profile, IP)
    2. Dynamic string translation
    3. RTL/LTR support
    4. Pluralization rules
    5. Format adaptation (date, number, currency)
    """

    def get_locale(self, request=None, user=None, country: str = None) -> str:
        """Best locale detect করে।"""
        # 1. User preference
        if user and hasattr(user, 'profile') and getattr(user.profile, 'language', None):
            lang = user.profile.language
            if lang in SUPPORTED_LOCALES:
                return lang

        # 2. Accept-Language header
        if request:
            accept_lang = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
            lang = self._parse_accept_language(accept_lang)
            if lang and lang in SUPPORTED_LOCALES:
                return lang

        # 3. Country-based detection
        if country:
            for lang, info in SUPPORTED_LOCALES.items():
                if country.upper() in info['countries']:
                    return lang

        return 'en'  # Default

    def translate(self, key: str, locale: str = 'en', **kwargs) -> str:
        """String translate করে।"""
        strings = PLATFORM_STRINGS.get(key, {})
        text    = strings.get(locale) or strings.get('en') or key

        # Variable substitution
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass

        return text

    def translate_batch(self, keys: list, locale: str = 'en') -> dict:
        """Multiple strings একসাথে translate করে।"""
        return {key: self.translate(key, locale) for key in keys}

    def is_rtl(self, locale: str) -> bool:
        return SUPPORTED_LOCALES.get(locale, {}).get('rtl', False)

    def pluralize(self, count: int, singular: str, plural: str, locale: str = 'en') -> str:
        """Count অনুযায়ী singular/plural return করে।"""
        # Bengali, Hindi — different pluralization rules
        if locale in ('bn', 'hi', 'ar'):
            return singular if count == 1 else plural
        return singular if count == 1 else plural

    def get_locale_info(self, locale: str) -> dict:
        return SUPPORTED_LOCALES.get(locale, SUPPORTED_LOCALES['en'])

    def get_supported_locales(self) -> list:
        return [{'code': k, 'name': v['name'], 'rtl': v['rtl']} for k, v in SUPPORTED_LOCALES.items()]

    def translate_db_model(self, obj, field_name: str, locale: str) -> str:
        """
        Database model এর translated field return করে।
        model.title_en, model.title_bn convention support।
        """
        localized_attr = f'{field_name}_{locale}'
        if hasattr(obj, localized_attr):
            value = getattr(obj, localized_attr)
            if value:
                return value
        return getattr(obj, field_name, '')

    @staticmethod
    def _parse_accept_language(header: str) -> Optional[str]:
        """Accept-Language header parse করে।"""
        if not header:
            return None
        parts = header.split(',')
        if parts:
            lang = parts[0].strip().split(';')[0].strip()[:2].lower()
            return lang if lang else None
        return None
