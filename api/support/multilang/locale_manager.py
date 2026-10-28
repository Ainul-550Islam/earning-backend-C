"""
api/support/multilang/locale_manager.py
FILE 58/70 — Locale & Timezone Manager

User-এর locale, timezone, currency preference।
Support portal + emails language-এ personalize করো।
"""
import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Supported locales
SUPPORTED_LOCALES = {
    'en': {'name': 'English',    'dir': 'ltr', 'currency': 'USD', 'date_fmt': '%m/%d/%Y'},
    'bn': {'name': 'বাংলা',      'dir': 'ltr', 'currency': 'BDT', 'date_fmt': '%d/%m/%Y'},
    'hi': {'name': 'हिन्दी',     'dir': 'ltr', 'currency': 'INR', 'date_fmt': '%d/%m/%Y'},
    'ar': {'name': 'العربية',    'dir': 'rtl', 'currency': 'USD', 'date_fmt': '%d/%m/%Y'},
    'fr': {'name': 'Français',   'dir': 'ltr', 'currency': 'EUR', 'date_fmt': '%d/%m/%Y'},
    'de': {'name': 'Deutsch',    'dir': 'ltr', 'currency': 'EUR', 'date_fmt': '%d.%m.%Y'},
    'es': {'name': 'Español',    'dir': 'ltr', 'currency': 'USD', 'date_fmt': '%d/%m/%Y'},
}

# Common timezones
TIMEZONES = [
    {'value': 'Asia/Dhaka',       'label': 'Dhaka (UTC+6)',            'offset': '+06:00'},
    {'value': 'Asia/Kolkata',     'label': 'India (UTC+5:30)',         'offset': '+05:30'},
    {'value': 'UTC',              'label': 'UTC (UTC+0)',               'offset': '+00:00'},
    {'value': 'America/New_York', 'label': 'New York (UTC-5)',         'offset': '-05:00'},
    {'value': 'Europe/London',    'label': 'London (UTC+0)',           'offset': '+00:00'},
    {'value': 'Asia/Dubai',       'label': 'Dubai (UTC+4)',            'offset': '+04:00'},
    {'value': 'Asia/Singapore',   'label': 'Singapore (UTC+8)',        'offset': '+08:00'},
    {'value': 'Australia/Sydney', 'label': 'Sydney (UTC+10)',          'offset': '+10:00'},
]

DEFAULT_LOCALE = 'en'
DEFAULT_TZ     = 'Asia/Dhaka'


class LocaleManager:
    """User locale + timezone preferences"""

    def get_user_locale(self, user) -> dict:
        cache_key = f'user_locale:{user.id}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        locale = DEFAULT_LOCALE
        tz     = DEFAULT_TZ

        try:
            if hasattr(user, 'profile'):
                locale = getattr(user.profile, 'language', DEFAULT_LOCALE) or DEFAULT_LOCALE
                tz     = getattr(user.profile, 'timezone',  DEFAULT_TZ)    or DEFAULT_TZ
        except Exception:
            pass

        result = {
            'locale':      locale,
            'timezone':    tz,
            'locale_info': SUPPORTED_LOCALES.get(locale, SUPPORTED_LOCALES['en']),
            'is_rtl':      SUPPORTED_LOCALES.get(locale, {}).get('dir') == 'rtl',
        }
        cache.set(cache_key, result, timeout=3600)
        return result

    def set_user_locale(self, user, locale: str = None, timezone_name: str = None) -> bool:
        try:
            if locale and locale not in SUPPORTED_LOCALES:
                return False

            if hasattr(user, 'profile'):
                if locale:
                    user.profile.language = locale
                if timezone_name:
                    user.profile.timezone = timezone_name
                user.profile.save(update_fields=['language','timezone'])

            cache.delete(f'user_locale:{user.id}')
            return True
        except Exception as e:
            logger.error(f'Set locale failed: {e}')
            return False

    def format_datetime(self, dt, user=None) -> str:
        locale_data = self.get_user_locale(user) if user else {}
        fmt         = locale_data.get('locale_info', {}).get('date_fmt', '%Y-%m-%d %H:%M')
        try:
            import pytz
            tz = pytz.timezone(locale_data.get('timezone', DEFAULT_TZ))
            dt = dt.astimezone(tz)
        except Exception:
            pass
        return dt.strftime(fmt + ' %H:%M')

    def get_supported_locales(self) -> list:
        return [{'code': k, **v} for k, v in SUPPORTED_LOCALES.items()]

    def get_timezones(self) -> list:
        return TIMEZONES

    def detect_from_request(self, request) -> str:
        """HTTP Accept-Language header থেকে locale detect করো"""
        accept_lang = request.META.get('HTTP_ACCEPT_LANGUAGE', 'en')
        lang        = accept_lang.split(',')[0].split('-')[0].lower().strip()
        return lang if lang in SUPPORTED_LOCALES else DEFAULT_LOCALE


locale_manager = LocaleManager()