"""
api/users/settings/language_settings.py
Language, timezone, currency, date format preferences
"""
import logging
import pytz
from django.core.cache import cache

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    'en': 'English',
    'bn': 'বাংলা',
    'hi': 'हिन्दी',
    'ar': 'العربية',
    'es': 'Español',
    'fr': 'Français',
    'pt': 'Português',
    'id': 'Bahasa Indonesia',
    'tr': 'Türkçe',
    'ru': 'Русский',
    'zh': '中文',
    'ja': '日本語',
    'ko': '한국어',
    'ur': 'اردو',
}

SUPPORTED_CURRENCIES = {
    'USD': '$',
    'BDT': '৳',
    'INR': '₹',
    'EUR': '€',
    'GBP': '£',
    'AED': 'د.إ',
    'SAR': '﷼',
    'PKR': '₨',
    'IDR': 'Rp',
    'MYR': 'RM',
    'NGN': '₦',
}

DATE_FORMATS = {
    'DMY':  'DD/MM/YYYY',
    'MDY':  'MM/DD/YYYY',
    'YMD':  'YYYY-MM-DD',
}

DEFAULTS = {
    'language':       'en',
    'timezone':       'UTC',
    'currency':       'USD',
    'date_format':    'DMY',
    'number_format':  'standard',  # standard | indian | arabic
}


class LanguageSettings:

    CACHE_KEY = 'user:locale:{user_id}'
    CACHE_TTL = 86400

    def get(self, user) -> dict:
        key    = self.CACHE_KEY.format(user_id=user.id)
        cached = cache.get(key)
        if cached:
            return cached

        prefs = self._get_from_db(user)
        cache.set(key, prefs, timeout=self.CACHE_TTL)
        return prefs

    def update(self, user, data: dict) -> dict:
        """Locale settings update করো"""
        current = self._get_from_db(user)
        errors  = []

        if 'language' in data:
            if data['language'] not in SUPPORTED_LANGUAGES:
                errors.append(f"Unsupported language: {data['language']}")
            else:
                current['language'] = data['language']

        if 'timezone' in data:
            if data['timezone'] not in pytz.all_timezones:
                errors.append(f"Invalid timezone: {data['timezone']}")
            else:
                current['timezone'] = data['timezone']

        if 'currency' in data:
            if data['currency'] not in SUPPORTED_CURRENCIES:
                errors.append(f"Unsupported currency: {data['currency']}")
            else:
                current['currency'] = data['currency']

        if 'date_format' in data:
            if data['date_format'] not in DATE_FORMATS:
                errors.append(f"Invalid date format: {data['date_format']}")
            else:
                current['date_format'] = data['date_format']

        if errors:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'locale': errors})

        self._save_to_db(user, current)
        cache.delete(self.CACHE_KEY.format(user_id=user.id))
        return current

    def get_available_languages(self) -> list:
        return [
            {'code': code, 'name': name}
            for code, name in SUPPORTED_LANGUAGES.items()
        ]

    def get_available_timezones(self) -> list:
        """Popular timezone list"""
        popular = [
            'UTC', 'Asia/Dhaka', 'Asia/Kolkata', 'Asia/Karachi',
            'Asia/Dubai', 'Asia/Singapore', 'Asia/Tokyo',
            'Europe/London', 'Europe/Paris', 'America/New_York',
            'America/Los_Angeles', 'Australia/Sydney',
        ]
        return popular

    def get_currency_symbol(self, user) -> str:
        prefs = self.get(user)
        return SUPPORTED_CURRENCIES.get(prefs.get('currency', 'USD'), '$')

    def _get_from_db(self, user) -> dict:
        try:
            from ..models import UserPreferences
            prefs = UserPreferences.objects.filter(user=user).first()
            if prefs:
                saved = {}
                for field in DEFAULTS:
                    if hasattr(prefs, field):
                        saved[field] = getattr(prefs, field)
                return {**DEFAULTS, **saved}
        except Exception:
            pass

        # User model-এর field থেকে নাও
        return {
            **DEFAULTS,
            'language': getattr(user, 'language', 'en'),
            'timezone': getattr(user, 'timezone', 'UTC'),
        }

    def _save_to_db(self, user, data: dict) -> None:
        try:
            from ..models import UserPreferences
            prefs, _ = UserPreferences.objects.get_or_create(user=user)
            update_fields = []
            for field, value in data.items():
                if hasattr(prefs, field):
                    setattr(prefs, field, value)
                    update_fields.append(field)
            if update_fields:
                prefs.save(update_fields=update_fields)
        except Exception as e:
            logger.error(f'Language settings save failed: {e}')


# Singleton
language_settings = LanguageSettings()
