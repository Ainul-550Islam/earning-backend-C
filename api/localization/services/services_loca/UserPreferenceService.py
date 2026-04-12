# api/localization/services/services_loca/UserPreferenceService.py
"""
UserPreferenceService — EXPANDED from 66L to full 300L+ implementation.
Language, currency, timezone, date format, notification language — all covered.
"""
import logging
from typing import Optional, Dict, List
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)
PREF_CACHE_TTL = getattr(settings, 'USER_PREF_CACHE_TTL', 3600)


class UserPreferenceService:
    """Full user localization preference management service."""

    # ORIGINAL METHODS (kept intact)
    def get_user_preference(self, user):
        """Get user's language preference — original method kept"""
        try:
            if not user or not user.is_authenticated:
                return None
            if hasattr(user, 'profile'):
                profile = user.profile
                if hasattr(profile, 'language'):
                    return self._create_preference_object(profile.language)
            if hasattr(user, 'language'):
                return self._create_preference_object(user.language)
            return self._create_preference_object(settings.LANGUAGE_CODE)
        except Exception as e:
            logger.error(f"Error getting user preference: {e}")
            return self._create_preference_object(settings.LANGUAGE_CODE)

    def _create_preference_object(self, language_code):
        try:
            from ..models.core import Language
            language = Language.objects.filter(code=language_code).first()
            if language:
                return type('Preference', (), {'ui_language': language})
        except Exception:
            pass
        return type('Preference', (), {'ui_language': language_code})

    def set_user_preference(self, user, language_code):
        """Set user's language preference — original method kept"""
        try:
            if not user or not user.is_authenticated:
                return False
            if hasattr(user, 'profile'):
                user.profile.language = language_code
                user.profile.save()
                return True
            return False
        except Exception as e:
            logger.error(f"Error setting user preference: {e}")
            return False

    # NEW: Full preference management
    def get_full_preference(self, user) -> Optional[Dict]:
        """User-এর সম্পূর্ণ localization preference dict return করে"""
        if not user or not getattr(user, 'is_authenticated', False):
            return self._get_default_preferences()
        cache_key = f"user_full_pref_{user.pk}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            from ..models.core import UserLanguagePreference
            pref, _ = UserLanguagePreference.objects.select_related(
                'primary_language', 'ui_language', 'content_language',
                'preferred_currency', 'preferred_timezone'
            ).get_or_create(user=user)
            effective_lang = pref.effective_language
            result = {
                'user_id': user.pk,
                'language': {
                    'primary': self._lang_dict(pref.primary_language),
                    'ui': self._lang_dict(pref.ui_language),
                    'content': self._lang_dict(pref.content_language),
                    'effective': self._lang_dict(effective_lang),
                    'is_rtl': getattr(effective_lang, 'is_rtl', False),
                    'text_direction': getattr(effective_lang, 'text_direction', 'ltr'),
                    'bcp47': getattr(effective_lang, 'bcp47_code', None) or getattr(effective_lang, 'code', 'en'),
                    'last_used': pref.last_used_languages or [],
                },
                'currency': self._currency_dict(getattr(pref, 'preferred_currency', None)),
                'timezone': self._timezone_dict(getattr(pref, 'preferred_timezone', None)),
                'formats': {
                    'date': getattr(pref, 'preferred_date_format', '') or self._get_locale_date_format(effective_lang),
                    'time': getattr(pref, 'preferred_time_format', '') or '24h',
                    'number': getattr(pref, 'preferred_number_format', '') or '1,234.56',
                },
                'auto_translate': pref.auto_translate,
                'show_translation_hints': getattr(pref, 'show_translation_hints', True),
                'enable_rtl': getattr(pref, 'enable_rtl_support', True),
                'translation_feedback_enabled': getattr(pref, 'translation_feedback_enabled', True),
                'preferred_languages': [self._lang_dict(l) for l in pref.preferred_languages.filter(is_active=True)],
            }
            cache.set(cache_key, result, PREF_CACHE_TTL)
            return result
        except Exception as e:
            logger.error(f"get_full_preference failed for user {getattr(user,'pk','?')}: {e}")
            return self._get_default_preferences()

    def set_language(self, user, language_code: str, pref_type: str = 'ui') -> Dict:
        """User-এর language preference set করে. pref_type: ui|primary|content"""
        try:
            from ..models.core import UserLanguagePreference, Language
            language = Language.objects.filter(code=language_code, is_active=True).first()
            if not language:
                return {'success': False, 'error': f'Language {language_code} not found'}
            pref, _ = UserLanguagePreference.objects.get_or_create(user=user)
            field = {'ui': 'ui_language', 'primary': 'primary_language', 'content': 'content_language'}.get(pref_type, 'ui_language')
            setattr(pref, field, language)
            history = list(pref.last_used_languages or [])
            if language_code in history:
                history.remove(language_code)
            history.insert(0, language_code)
            pref.last_used_languages = history[:10]
            pref.save(update_fields=[field, 'last_used_languages'])
            self._invalidate_cache(user)
            self._log_pref_change(user, 'language_switch', {'to': language_code, 'type': pref_type})
            return {'success': True, 'language': language_code, 'type': pref_type}
        except Exception as e:
            logger.error(f"set_language failed: {e}")
            return {'success': False, 'error': str(e)}

    def set_currency(self, user, currency_code: str) -> Dict:
        """User-এর preferred currency set করে"""
        try:
            from ..models.core import UserLanguagePreference, Currency
            currency = Currency.objects.filter(code=currency_code, is_active=True).first()
            if not currency:
                return {'success': False, 'error': f'Currency {currency_code} not found'}
            pref, _ = UserLanguagePreference.objects.get_or_create(user=user)
            pref.preferred_currency = currency
            pref.save(update_fields=['preferred_currency'])
            self._invalidate_cache(user)
            return {'success': True, 'currency': currency_code, 'symbol': currency.symbol}
        except Exception as e:
            logger.error(f"set_currency failed: {e}")
            return {'success': False, 'error': str(e)}

    def set_timezone(self, user, timezone_name: str) -> Dict:
        """User-এর preferred timezone set করে"""
        try:
            import pytz
            if timezone_name not in pytz.all_timezones:
                return {'success': False, 'error': f'Invalid timezone: {timezone_name}'}
            from ..models.core import UserLanguagePreference, Timezone
            tz_obj = Timezone.objects.filter(name=timezone_name).first()
            if not tz_obj:
                return {'success': False, 'error': f'Timezone {timezone_name} not in database'}
            pref, _ = UserLanguagePreference.objects.get_or_create(user=user)
            pref.preferred_timezone = tz_obj
            pref.save(update_fields=['preferred_timezone'])
            self._invalidate_cache(user)
            return {'success': True, 'timezone': timezone_name}
        except Exception as e:
            logger.error(f"set_timezone failed: {e}")
            return {'success': False, 'error': str(e)}

    def set_date_format(self, user, date_format: str, time_format: str = None) -> Dict:
        """User-এর date/time format preference set করে"""
        VALID = ['DD/MM/YYYY','MM/DD/YYYY','YYYY-MM-DD','DD-MM-YYYY','DD.MM.YYYY','MMM D, YYYY']
        if date_format not in VALID:
            return {'success': False, 'error': f'Invalid date format. Valid: {VALID}'}
        try:
            from ..models.core import UserLanguagePreference
            pref, _ = UserLanguagePreference.objects.get_or_create(user=user)
            pref.preferred_date_format = date_format
            if time_format in ['12h', '24h']:
                pref.preferred_time_format = time_format
            pref.save(update_fields=['preferred_date_format', 'preferred_time_format'])
            self._invalidate_cache(user)
            return {'success': True, 'date_format': date_format, 'time_format': time_format}
        except Exception as e:
            logger.error(f"set_date_format failed: {e}")
            return {'success': False, 'error': str(e)}

    def set_auto_translate(self, user, enabled: bool) -> Dict:
        """Auto-translate toggle করে"""
        try:
            from ..models.core import UserLanguagePreference
            pref, _ = UserLanguagePreference.objects.get_or_create(user=user)
            pref.auto_translate = enabled
            pref.save(update_fields=['auto_translate'])
            self._invalidate_cache(user)
            return {'success': True, 'auto_translate': enabled}
        except Exception as e:
            logger.error(f"set_auto_translate failed: {e}")
            return {'success': False, 'error': str(e)}

    def add_preferred_language(self, user, language_code: str) -> Dict:
        try:
            from ..models.core import UserLanguagePreference, Language
            language = Language.objects.filter(code=language_code, is_active=True).first()
            if not language:
                return {'success': False, 'error': f'Language {language_code} not found'}
            pref, _ = UserLanguagePreference.objects.get_or_create(user=user)
            if language not in pref.preferred_languages.all():
                pref.preferred_languages.add(language)
            self._invalidate_cache(user)
            return {'success': True, 'added': language_code}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def detect_and_set_from_request(self, user, request) -> Dict:
        """Request থেকে language/timezone auto-detect করে set করে"""
        detected = {}
        results = {}
        try:
            accept_lang = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
            if accept_lang:
                lang_code = accept_lang.split(',')[0].split(';')[0].strip()[:5].split('-')[0].lower()
                detected['browser_lang'] = lang_code
            try:
                from ..services.geo.GeoIPService import GeoIPService
                x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
                ip = x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR', '')
                geo = GeoIPService().lookup(ip)
                if geo.get('country_code'):
                    detected['country_code'] = geo['country_code']
                if geo.get('detected_language'):
                    detected['geo_lang'] = geo['detected_language']
                if geo.get('timezone'):
                    detected['timezone'] = geo['timezone']
            except Exception:
                pass
            from ..models.core import Language
            lang_to_set = detected.get('geo_lang') or detected.get('browser_lang', 'en')
            if user and getattr(user, 'is_authenticated', False):
                if Language.objects.filter(code=lang_to_set, is_active=True).exists():
                    results['language'] = self.set_language(user, lang_to_set, 'ui')
                if detected.get('timezone'):
                    results['timezone'] = self.set_timezone(user, detected['timezone'])
            return {'success': True, 'detected': detected, 'applied': results}
        except Exception as e:
            logger.error(f"detect_and_set_from_request failed: {e}")
            return {'success': False, 'error': str(e), 'detected': detected}

    def get_notification_language(self, user) -> str:
        """User-এর notification language code return করে"""
        try:
            from ..models.core import UserLanguagePreference
            pref = UserLanguagePreference.objects.filter(user=user).select_related('primary_language').first()
            if pref:
                lang = pref.primary_language or pref.effective_language
                if lang:
                    return lang.code
        except Exception:
            pass
        return getattr(settings, 'LANGUAGE_CODE', 'en')

    def format_amount_for_user(self, user, amount, currency_code: str = None) -> str:
        """User preference অনুযায়ী amount format করে"""
        try:
            prefs = self.get_full_preference(user)
            curr_code = currency_code or (prefs or {}).get('currency', {}).get('code', 'USD')
            lang_code = ((prefs or {}).get('language') or {}).get('effective', {}).get('code', 'en')
            from ..services.currency.CurrencyFormatService import CurrencyFormatService
            from decimal import Decimal
            return CurrencyFormatService().format(Decimal(str(amount)), curr_code, lang_code)
        except Exception as e:
            logger.error(f"format_amount_for_user failed: {e}")
            return str(amount)

    def get_language_distribution(self) -> List[Dict]:
        """সব users-এর language distribution"""
        try:
            from ..models.core import UserLanguagePreference
            from django.db.models import Count
            return list(
                UserLanguagePreference.objects.filter(ui_language__isnull=False)
                .values('ui_language__code', 'ui_language__name', 'ui_language__flag_emoji')
                .annotate(user_count=Count('id')).order_by('-user_count')
            )
        except Exception as e:
            logger.error(f"get_language_distribution failed: {e}")
            return []

    def reset_to_defaults(self, user) -> Dict:
        """User preference সব default-এ reset করে"""
        try:
            from ..models.core import UserLanguagePreference, Language
            default_lang = Language.objects.filter(is_default=True, is_active=True).first()
            pref, _ = UserLanguagePreference.objects.get_or_create(user=user)
            pref.ui_language = default_lang
            pref.primary_language = None
            pref.content_language = None
            pref.preferred_currency = None
            pref.preferred_timezone = None
            pref.preferred_date_format = ''
            pref.preferred_time_format = '24h'
            pref.auto_translate = True
            pref.last_used_languages = []
            pref.save()
            pref.preferred_languages.clear()
            self._invalidate_cache(user)
            return {'success': True, 'message': 'Preferences reset to defaults'}
        except Exception as e:
            logger.error(f"reset_to_defaults failed: {e}")
            return {'success': False, 'error': str(e)}

    # Private helpers
    def _get_default_preferences(self) -> Dict:
        return {
            'user_id': None,
            'language': {
                'primary': None, 'ui': None, 'content': None,
                'effective': {'code': 'en', 'name': 'English'},
                'is_rtl': False, 'text_direction': 'ltr', 'bcp47': 'en', 'last_used': [],
            },
            'currency': {'code': 'USD', 'symbol': '$', 'name': 'US Dollar'},
            'timezone': {'name': 'UTC', 'offset': '+00:00', 'code': 'UTC'},
            'formats': {'date': 'YYYY-MM-DD', 'time': '24h', 'number': '1,234.56'},
            'auto_translate': True, 'show_translation_hints': True,
            'enable_rtl': True, 'preferred_languages': [],
        }

    def _lang_dict(self, lang_obj) -> Optional[Dict]:
        if not lang_obj:
            return None
        return {
            'code': getattr(lang_obj, 'code', ''),
            'name': getattr(lang_obj, 'name', ''),
            'name_native': getattr(lang_obj, 'name_native', ''),
            'flag_emoji': getattr(lang_obj, 'flag_emoji', ''),
            'is_rtl': getattr(lang_obj, 'is_rtl', False),
            'text_direction': getattr(lang_obj, 'text_direction', 'ltr'),
        }

    def _currency_dict(self, curr_obj) -> Dict:
        if not curr_obj:
            return {'code': 'USD', 'symbol': '$', 'name': 'US Dollar'}
        return {
            'code': getattr(curr_obj, 'code', 'USD'),
            'symbol': getattr(curr_obj, 'symbol', '$'),
            'name': getattr(curr_obj, 'name', ''),
        }

    def _timezone_dict(self, tz_obj) -> Dict:
        if not tz_obj:
            return {'name': 'UTC', 'offset': '+00:00', 'code': 'UTC'}
        return {
            'name': getattr(tz_obj, 'name', 'UTC'),
            'offset': getattr(tz_obj, 'offset', '+00:00'),
            'code': getattr(tz_obj, 'code', 'UTC'),
        }

    def _get_locale_date_format(self, lang_obj) -> str:
        if not lang_obj:
            return 'YYYY-MM-DD'
        try:
            from ..models.settings import DateTimeFormat
            fmt = DateTimeFormat.objects.filter(language=lang_obj).first()
            return fmt.date_short if fmt else 'YYYY-MM-DD'
        except Exception:
            return 'YYYY-MM-DD'

    def _invalidate_cache(self, user):
        try:
            if user and getattr(user, 'pk', None):
                cache.delete(f"user_full_pref_{user.pk}")
                cache.delete(f"user_pref_{user.pk}")
        except Exception:
            pass

    def _log_pref_change(self, user, event_type: str, extra_data: dict = None):
        try:
            from ..models.analytics import LocalizationAnalytics
            LocalizationAnalytics.log_event(
                event_type=LocalizationAnalytics.EventType.USER_PREFERENCE_UPDATED,
                user=user, extra_data=extra_data or {},
            )
        except Exception:
            pass
