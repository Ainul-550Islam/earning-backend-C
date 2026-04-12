"""
api/users/settings/theme_settings.py
UI theme preferences — dark/light mode, color, font
"""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

DEFAULTS = {
    'mode':         'light',    # light | dark | system
    'primary_color':'#6366f1',  # indigo
    'font_size':    'medium',   # small | medium | large
    'compact':      False,      # compact layout
    'animations':   True,
    'sidebar':      'expanded', # expanded | collapsed
}

ALLOWED = {
    'mode':         ['light', 'dark', 'system'],
    'font_size':    ['small', 'medium', 'large'],
    'sidebar':      ['expanded', 'collapsed'],
}


class ThemeSettings:

    CACHE_KEY = 'user:theme:{user_id}'
    CACHE_TTL = 86400  # 24h

    def get(self, user) -> dict:
        """User-এর theme settings দাও"""
        # Cache check
        key    = self.CACHE_KEY.format(user_id=user.id)
        cached = cache.get(key)
        if cached:
            return cached

        # DB থেকে নাও
        prefs = self._get_from_db(user)
        cache.set(key, prefs, timeout=self.CACHE_TTL)
        return prefs

    def update(self, user, data: dict) -> dict:
        """Theme settings update করো"""
        current = self._get_from_db(user)
        errors  = []

        for field, value in data.items():
            if field not in DEFAULTS:
                continue
            if field in ALLOWED and value not in ALLOWED[field]:
                errors.append(f'Invalid value for {field}: {value}')
                continue
            current[field] = value

        if errors:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'theme': errors})

        self._save_to_db(user, current)

        # Cache invalidate
        cache.delete(self.CACHE_KEY.format(user_id=user.id))
        return current

    def reset(self, user) -> dict:
        """Default-এ ফিরিয়ে দাও"""
        self._save_to_db(user, DEFAULTS.copy())
        cache.delete(self.CACHE_KEY.format(user_id=user.id))
        return DEFAULTS.copy()

    def _get_from_db(self, user) -> dict:
        try:
            from ..models import UserPreferences
            prefs = UserPreferences.objects.filter(user=user).first()
            if prefs and hasattr(prefs, 'theme_settings'):
                saved = prefs.theme_settings or {}
                return {**DEFAULTS, **saved}
        except Exception:
            pass
        return DEFAULTS.copy()

    def _save_to_db(self, user, data: dict) -> None:
        try:
            from ..models import UserPreferences
            prefs, _ = UserPreferences.objects.get_or_create(user=user)
            if hasattr(prefs, 'theme_settings'):
                prefs.theme_settings = data
                prefs.save(update_fields=['theme_settings'])
        except Exception as e:
            logger.error(f'Theme save failed: {e}')


# Singleton
theme_settings = ThemeSettings()
