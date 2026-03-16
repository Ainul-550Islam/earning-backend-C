# services.py
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.db import transaction
from django.db.models import Q, Count, Avg, F
from django.utils.translation import gettext_lazy as _
from django.http import HttpRequest
import logging
import json
from typing import Optional, Dict, Any, List, Tuple, Union, Callable
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
import pytz
from .models import (
    Language, Country, Currency, Timezone, City,
    TranslationKey, Translation, TranslationCache,
    UserLanguagePreference, MissingTranslation
)

logger = logging.getLogger(__name__)

# ======================== Constants ========================
CACHE_TIMEOUT: int = getattr(settings, 'API_CACHE_TIMEOUT', 3600)
CACHE_24_HOURS: int = getattr(settings, 'CACHE_24_HOURS', 86400)
DEFAULT_LANGUAGE: str = getattr(settings, 'DEFAULT_LANGUAGE', 'en')
DEFAULT_CURRENCY: str = getattr(settings, 'DEFAULT_CURRENCY', 'USD')
DEFAULT_COUNTRY: str = getattr(settings, 'DEFAULT_COUNTRY', 'US')


# ======================== Type Aliases ========================
JSONType = Union[Dict[str, Any], List[Any], str, int, float, bool, None]
LanguageCode = str
CurrencyCode = str
CountryCode = str


# ======================== Base Service with Defensive Coding ========================

class BaseService:
    """Base service class with common functionality"""
    
    def __init__(self) -> None:
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
    
    def handle_exception(self, e: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Centralized exception handling"""
        context = context or {}
        self.logger.error(f"Error in {self.__class__.__name__}: {e}", exc_info=True, extra=context)
        
        return {
            'success': False,
            'error': str(e),
            'code': e.__class__.__name__,
            'context': context
        }
    
    def get_cached(self, key: str, default: Any = None) -> Any:
        """Get from cache with error handling"""
        try:
            return cache.get(key, default)
        except Exception as e:
            self.logger.error(f"Cache get error for {key}: {e}")
            return default
    
    def set_cached(self, key: str, value: Any, timeout: int = CACHE_TIMEOUT) -> bool:
        """Set to cache with error handling"""
        try:
            cache.set(key, value, timeout)
            return True
        except Exception as e:
            self.logger.error(f"Cache set error for {key}: {e}")
            return False
    
    def delete_cached(self, key: str) -> bool:
        """Delete from cache"""
        try:
            cache.delete(key)
            return True
        except Exception as e:
            self.logger.error(f"Cache delete error for {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete cache keys matching pattern (backend-dependent)"""
        deleted_count = 0
        try:
            # Check if cache backend supports delete_pattern
            if hasattr(cache, 'delete_pattern'):
                deleted_count = cache.delete_pattern(pattern)
                self.logger.info(f"Deleted {deleted_count} cache keys matching pattern: {pattern}")
            else:
                # Fallback for backends without delete_pattern
                self.logger.warning(f"Cache backend does not support delete_pattern. Pattern: {pattern}")
                # You could implement a custom solution here if needed
        except Exception as e:
            self.logger.error(f"Failed to delete cache pattern {pattern}: {e}")
        
        return deleted_count


# ======================== Language Service ========================

class LanguageService(BaseService):
    """Service for language operations"""
    
    def get_active_languages(self, search: Optional[str] = None) -> List[Language]:
        """Get all active languages with optional search"""
        try:
            queryset = Language.objects.filter(is_active=True)
            
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) |
                    Q(code__icontains=search) |
                    Q(name_native__icontains=search)
                )
            
            return list(queryset)
        except Exception as e:
            self.logger.error(f"Failed to get active languages: {e}")
            return []
    
    def get_default_language(self) -> Optional[Language]:
        """Get default language with fallback"""
        try:
            # Try to get default from database
            default = Language.objects.filter(is_default=True, is_active=True).first()
            if default:
                return default
            
            # Try to get first active language
            first_active = Language.objects.filter(is_active=True).first()
            if first_active:
                return first_active
            
            # Return None (caller must handle)
            return None
        except Exception as e:
            self.logger.error(f"Failed to get default language: {e}")
            return None
    
    def get_language_by_code(self, code: LanguageCode) -> Optional[Language]:
        """Get language by code with caching"""
        try:
            cache_key = f"language_{code}"
            cached = self.get_cached(cache_key)
            
            if cached:
                return cached
            
            language = Language.objects.filter(code=code, is_active=True).first()
            if language:
                self.set_cached(cache_key, language, CACHE_24_HOURS)
            
            return language
        except Exception as e:
            self.logger.error(f"Failed to get language {code}: {e}")
            return None
    
    def set_default_language(self, language: Language) -> bool:
        """Set a language as default (ensures only one default)"""
        try:
            with transaction.atomic():
                # Clear existing default
                Language.objects.filter(is_default=True).update(is_default=False)
                
                # Set new default
                language.is_default = True
                language.save()
                
                # Clear cache
                self.delete_cached(f"language_{language.code}")
                
                return True
        except Exception as e:
            self.logger.error(f"Failed to set default language {language.code}: {e}")
            return False
    
    def bulk_activate(self, language_codes: List[LanguageCode]) -> Dict[str, Any]:
        """Bulk activate languages"""
        results: Dict[str, Any] = {'success': 0, 'failed': 0, 'errors': []}
        
        try:
            with transaction.atomic():
                for code in language_codes:
                    try:
                        updated = Language.objects.filter(code=code).update(is_active=True)
                        if updated:
                            results['success'] += 1
                            self.delete_cached(f"language_{code}")
                        else:
                            results['failed'] += 1
                            results['errors'].append(f"Language {code} not found")
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(f"Error activating {code}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Bulk activate failed: {e}")
            results['errors'].append(f"Transaction failed: {str(e)}")
        
        return results


# ======================== Translation Service ========================

class TranslationService(BaseService):
    """Service for translation operations"""
    
    def __init__(self) -> None:
        super().__init__()
        self.cache_prefix: str = "translation"
    
    def get_translation(self, key: str, language_code: Optional[LanguageCode] = None, 
                       default: Optional[str] = None, request: Optional[HttpRequest] = None) -> str:
        """
        Get translation with multiple fallback levels:
        1. Requested language
        2. Default language
        3. Key as fallback
        4. Provided default
        """
        try:
            # Get language from request if not provided
            if not language_code and request:
                language_code = self._get_language_from_request(request)
            
            if not language_code:
                language_code = DEFAULT_LANGUAGE
            
            # Try cache first
            cache_key = f"{self.cache_prefix}:{language_code}:{key}"
            cached = self.get_cached(cache_key)
            if cached:
                return cached
            
            # Get language object
            language = Language.objects.filter(code=language_code, is_active=True).first()
            if not language:
                # Try default language
                language = self._get_default_language()
                if not language:
                    return default or key
            
            # Try to get translation
            translation = Translation.objects.filter(
                key__key=key,
                language=language,
                is_approved=True
            ).select_related('key').first()
            
            if translation:
                self.set_cached(cache_key, translation.value, CACHE_24_HOURS)
                return translation.value
            
            # Try default language if different from requested
            if language_code != DEFAULT_LANGUAGE:
                default_lang = Language.objects.filter(code=DEFAULT_LANGUAGE, is_active=True).first()
                if default_lang:
                    default_trans = Translation.objects.filter(
                        key__key=key,
                        language=default_lang,
                        is_approved=True
                    ).first()
                    if default_trans:
                        return default_trans.value
            
            # Log missing translation
            self._log_missing_translation(key, language_code, request)
            
            return default or key
            
        except Exception as e:
            self.logger.error(f"Translation error for key '{key}': {e}")
            return default or key
    
    def get_translations_bulk(self, keys: List[str], language_code: Optional[LanguageCode] = None,
                             request: Optional[HttpRequest] = None) -> Dict[str, str]:
        """Get multiple translations at once"""
        try:
            if not language_code and request:
                language_code = self._get_language_from_request(request)
            
            if not language_code:
                language_code = DEFAULT_LANGUAGE
            
            cache_key = f"{self.cache_prefix}:bulk:{language_code}:{hash(frozenset(keys))}"
            cached = self.get_cached(cache_key)
            if cached:
                return cached
            
            language = Language.objects.filter(code=language_code, is_active=True).first()
            if not language:
                language = self._get_default_language()
            
            if not language:
                return {key: key for key in keys}
            
            translations = Translation.objects.filter(
                key__key__in=keys,
                language=language,
                is_approved=True
            ).select_related('key')
            
            result: Dict[str, str] = {t.key.key: t.value for t in translations}
            
            # Add missing keys as themselves
            for key in keys:
                if key not in result:
                    result[key] = key
                    self._log_missing_translation(key, language_code, request)
            
            self.set_cached(cache_key, result, CACHE_TIMEOUT)
            return result
            
        except Exception as e:
            self.logger.error(f"Bulk translation error: {e}")
            return {key: key for key in keys}
    
    def translate_text(self, text: str, from_lang: LanguageCode, to_lang: LanguageCode, 
                      service: str = 'google', request: Optional[HttpRequest] = None) -> Dict[str, Any]:
        """
        Translate text using external service
        This is a placeholder - implement actual translation service integration
        """
        try:
            # Validate languages
            from_lang_obj = Language.objects.filter(code=from_lang, is_active=True).first()
            to_lang_obj = Language.objects.filter(code=to_lang, is_active=True).first()
            
            if not from_lang_obj or not to_lang_obj:
                return {
                    'success': False,
                    'error': 'Invalid language code',
                    'translated_text': text
                }
            
            # Check cache
            cache_key = f"translated:{from_lang}:{to_lang}:{hash(text)}"
            cached = self.get_cached(cache_key)
            if cached:
                return cached
            
            # TODO: Implement actual translation service call
            # This is where you'd call Google Translate, DeepL, etc.
            translated_text = f"[{from_lang} to {to_lang}] {text}"
            
            result: Dict[str, Any] = {
                'success': True,
                'original_text': text,
                'translated_text': translated_text,
                'from_language': from_lang,
                'to_language': to_lang,
                'service': service,
                'character_count': len(text),
                'timestamp': timezone.now().isoformat()
            }
            
            self.set_cached(cache_key, result, CACHE_TIMEOUT)
            return result
            
        except Exception as e:
            self.logger.error(f"Text translation error: {e}")
            return {
                'success': False,
                'error': str(e),
                'original_text': text,
                'translated_text': text
            }
    
    def import_translations(self, language_code: LanguageCode, translations: Dict[str, str],
                           source: str = 'import', overwrite: bool = False,
                           request: Optional[HttpRequest] = None) -> Dict[str, Any]:
        """Bulk import translations"""
        results: Dict[str, Any] = {
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'failed': 0,
            'errors': []
        }
        
        try:
            language = Language.objects.filter(code=language_code).first()
            if not language:
                return {'error': f'Language {language_code} not found'}
            
            with transaction.atomic():
                for key_str, value in translations.items():
                    try:
                        # Get or create translation key
                        key, _ = TranslationKey.objects.get_or_create(
                            key=key_str,
                            defaults={'description': f'Imported for {language_code}'}
                        )
                        
                        # Check if exists
                        existing = Translation.objects.filter(key=key, language=language).first()
                        
                        if existing and not overwrite:
                            results['skipped'] += 1
                            continue
                        
                        # Create or update
                        translation, created = Translation.objects.update_or_create(
                            key=key,
                            language=language,
                            defaults={
                                'value': value,
                                'source': source,
                                'is_approved': language.is_default
                            }
                        )
                        
                        if created:
                            results['created'] += 1
                        else:
                            results['updated'] += 1
                            
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append({
                            'key': key_str,
                            'error': str(e)
                        })
            
            # Clear cache
            self._clear_translation_cache(language_code)
            
        except Exception as e:
            self.logger.error(f"Import failed: {e}")
            results['errors'].append({'general': str(e)})
        
        return results
    
    def export_translations(self, language_code: LanguageCode, format: str = 'json',
                           request: Optional[HttpRequest] = None) -> Dict[str, Any]:
        """Export all translations for a language"""
        try:
            language = Language.objects.filter(code=language_code).first()
            if not language:
                return {'error': f'Language {language_code} not found'}
            
            translations = Translation.objects.filter(
                language=language,
                is_approved=True
            ).select_related('key')
            
            if format == 'json':
                data: Dict[str, Any] = {
                    'language': {
                        'code': language.code,
                        'name': language.name,
                        'is_rtl': language.is_rtl
                    },
                    'translations': {
                        t.key.key: t.value
                        for t in translations
                    },
                    'count': translations.count(),
                    'exported_at': timezone.now().isoformat()
                }
                return data
            
            elif format == 'csv':
                # Format for CSV export
                data = [
                    {'key': t.key.key, 'value': t.value}
                    for t in translations
                ]
                return {'data': data, 'format': 'csv'}
            
            else:
                return {'error': f'Unsupported format: {format}'}
                
        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            return {'error': str(e)}
    
    def _get_language_from_request(self, request: HttpRequest) -> str:
        """Extract language from request"""
        try:
            # Check Accept-Language header
            accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
            if accept_language:
                # Parse first language from header (simplified)
                lang_code = accept_language.split(',')[0].split(';')[0].split('-')[0]
                if Language.objects.filter(code=lang_code, is_active=True).exists():
                    return lang_code
            
            # Check session
            if hasattr(request, 'session'):
                session_lang = request.session.get('django_language')
                if session_lang:
                    return session_lang
            
            # Check cookie
            cookie_lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
            if cookie_lang:
                return cookie_lang
            
        except Exception as e:
            self.logger.error(f"Error extracting language from request: {e}")
        
        return DEFAULT_LANGUAGE
    
    def _get_default_language(self) -> Optional[Language]:
        """Get default language object"""
        return Language.objects.filter(is_default=True, is_active=True).first()
    
    def _log_missing_translation(self, key: str, language_code: str, request: Optional[HttpRequest] = None):
        """Log missing translation"""
        try:
            language = Language.objects.filter(code=language_code).first()
            if language:
                MissingTranslation.objects.create(
                    key=key,
                    language=language,
                    context='translation_service',
                    request_path=request.path if request else '',
                    user=request.user if request and request.user.is_authenticated else None
                )
        except Exception as e:
            self.logger.error(f"Failed to log missing translation: {e}")
    
    def _clear_translation_cache(self, language_code: Optional[str] = None):
        """Clear translation cache"""
        try:
            if language_code:
                # Clear specific language cache
                self.delete_pattern(f"{self.cache_prefix}:{language_code}:*")
                TranslationCache.objects.filter(language_code=language_code).delete()
            else:
                # Clear all translation cache
                self.delete_pattern(f"{self.cache_prefix}:*")
                TranslationCache.objects.all().delete()
        except Exception as e:
            self.logger.error(f"Cache clear error: {e}")


# ======================== Currency Service ========================

class CurrencyService(BaseService):
    """Service for currency operations"""
    
    def convert_currency(self, amount: Decimal, from_code: CurrencyCode, 
                        to_code: CurrencyCode) -> Optional[Dict[str, Any]]:
        """Convert amount between currencies"""
        try:
            # Get currencies
            from_curr = Currency.objects.filter(code=from_code, is_active=True).first()
            to_curr = Currency.objects.filter(code=to_code, is_active=True).first()
            
            if not from_curr or not to_curr:
                return None
            
            # Check for zero exchange rates
            if from_curr.exchange_rate == 0 or to_curr.exchange_rate == 0:
                self.logger.error(f"Zero exchange rate detected")
                return None
            
            # Perform conversion
            if from_code == 'USD':
                converted = amount * to_curr.exchange_rate
            elif to_code == 'USD':
                converted = amount / from_curr.exchange_rate
            else:
                # Convert via USD
                in_usd = amount / from_curr.exchange_rate
                converted = in_usd * to_curr.exchange_rate
            
            return {
                'from': {
                    'code': from_curr.code,
                    'amount': str(amount),
                    'formatted': from_curr.format_amount(amount)
                },
                'to': {
                    'code': to_curr.code,
                    'amount': str(converted),
                    'formatted': to_curr.format_amount(converted)
                },
                'exchange_rate': str(to_curr.exchange_rate / from_curr.exchange_rate),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Currency conversion error: {e}")
            return None
    
    def get_exchange_rate(self, from_code: CurrencyCode, to_code: CurrencyCode) -> Optional[Decimal]:
        """Get exchange rate between two currencies"""
        try:
            cache_key = f"exchange_rate:{from_code}:{to_code}"
            cached = self.get_cached(cache_key)
            if cached:
                return Decimal(cached)
            
            from_curr = Currency.objects.filter(code=from_code, is_active=True).first()
            to_curr = Currency.objects.filter(code=to_code, is_active=True).first()
            
            if not from_curr or not to_curr or from_curr.exchange_rate == 0:
                return None
            
            rate = to_curr.exchange_rate / from_curr.exchange_rate
            self.set_cached(cache_key, str(rate), CACHE_TIMEOUT)
            
            return rate
            
        except Exception as e:
            self.logger.error(f"Exchange rate error: {e}")
            return None
    
    def update_exchange_rates(self, rates: Dict[CurrencyCode, Decimal]) -> Dict[str, Any]:
        """Bulk update exchange rates"""
        results: Dict[str, Any] = {'updated': 0, 'failed': 0, 'errors': []}
        
        try:
            with transaction.atomic():
                for code, rate in rates.items():
                    try:
                        updated = Currency.objects.filter(code=code).update(
                            exchange_rate=rate,
                            exchange_rate_updated_at=timezone.now()
                        )
                        if updated:
                            results['updated'] += 1
                            self._clear_currency_cache(code)
                        else:
                            results['failed'] += 1
                            results['errors'].append(f"Currency {code} not found")
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(f"Error updating {code}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Bulk update failed: {e}")
            results['errors'].append(f"Transaction failed: {str(e)}")
        
        return results
    
    def get_currencies_needing_update(self) -> List[Currency]:
        """Get currencies whose exchange rates need updating"""
        try:
            cutoff = timezone.now() - timedelta(hours=24)
            return list(Currency.objects.filter(
                Q(exchange_rate_updated_at__isnull=True) |
                Q(exchange_rate_updated_at__lt=cutoff),
                is_active=True
            ))
        except Exception as e:
            self.logger.error(f"Failed to get currencies needing update: {e}")
            return []
    
    def format_amount_for_display(self, amount: Decimal, currency_code: CurrencyCode) -> str:
        """Format amount for display with proper currency"""
        try:
            currency = Currency.objects.filter(code=currency_code).first()
            if currency:
                return currency.format_amount(amount)
            return f"{currency_code} {amount}"
        except Exception as e:
            self.logger.error(f"Amount formatting error: {e}")
            return f"{amount}"
    
    def _clear_currency_cache(self, currency_code: str):
        """Clear currency-related cache"""
        try:
            self.delete_cached(f"currency:{currency_code}")
            self.delete_pattern(f"exchange_rate:*:{currency_code}")
            self.delete_pattern(f"exchange_rate:{currency_code}:*")
        except Exception as e:
            self.logger.error(f"Cache clear error for {currency_code}: {e}")


# ======================== Timezone Service ========================

class TimezoneService(BaseService):
    """Service for timezone operations"""
    
    def get_user_timezone(self, user) -> Optional[Timezone]:
        """Get user's preferred timezone"""
        try:
            if hasattr(user, 'timezone'):
                return user.timezone
            
            # Try to get from user's country
            if hasattr(user, 'country') and user.country:
                return user.country.default_timezone
            
            return None
        except Exception as e:
            self.logger.error(f"Failed to get user timezone: {e}")
            return None
    
    def convert_to_user_timezone(self, dt: datetime, user) -> datetime:
        """Convert datetime to user's timezone"""
        try:
            tz = self.get_user_timezone(user)
            if tz and dt:
                user_tz = pytz.timezone(tz.name)
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt)
                return dt.astimezone(user_tz)
            return dt
        except Exception as e:
            self.logger.error(f"Timezone conversion error: {e}")
            return dt
    
    def get_current_time_in_timezone(self, timezone_name: str) -> Optional[datetime]:
        """Get current time in specified timezone"""
        try:
            return Timezone.get_current_time(timezone_name)
        except Exception as e:
            self.logger.error(f"Failed to get time in {timezone_name}: {e}")
            return timezone.now()
    
    def get_timezone_offset(self, timezone_name: str) -> Optional[str]:
        """Get offset for timezone"""
        try:
            tz = Timezone.objects.filter(name=timezone_name, is_active=True).first()
            return tz.offset if tz else None
        except Exception as e:
            self.logger.error(f"Failed to get offset for {timezone_name}: {e}")
            return None
    
    def get_all_timezones_grouped(self) -> Dict[str, List[Timezone]]:
        """Get all timezones grouped by offset"""
        try:
            cache_key = "timezones_grouped"
            cached = self.get_cached(cache_key)
            if cached:
                return cached
            
            timezones = Timezone.objects.filter(is_active=True)
            
            grouped: Dict[str, List[Timezone]] = {}
            for tz in timezones:
                offset = tz.offset or '+00:00'
                if offset not in grouped:
                    grouped[offset] = []
                grouped[offset].append(tz)
            
            self.set_cached(cache_key, grouped, CACHE_24_HOURS)
            return grouped
            
        except Exception as e:
            self.logger.error(f"Failed to get grouped timezones: {e}")
            return {}


# ======================== Country Service ========================

class CountryService(BaseService):
    """Service for country operations"""
    
    def get_country_by_code(self, code: CountryCode) -> Optional[Country]:
        """Get country by code with caching"""
        try:
            cache_key = f"country:{code}"
            cached = self.get_cached(cache_key)
            if cached:
                return cached
            
            country = Country.objects.filter(code=code.upper(), is_active=True).first()
            if country:
                self.set_cached(cache_key, country, CACHE_24_HOURS)
            
            return country
        except Exception as e:
            self.logger.error(f"Failed to get country {code}: {e}")
            return None
    
    def get_country_phone_info(self, country_code: CountryCode) -> Dict[str, Any]:
        """Get phone number info for country"""
        try:
            country = self.get_country_by_code(country_code)
            if not country:
                return {}
            
            phone_code = country.get_safe_phone_code()
            example = f"{phone_code}1234567890"[:country.phone_digits + len(phone_code)]
            
            return {
                'phone_code': phone_code,
                'phone_digits': country.phone_digits,
                'example': example
            }
        except Exception as e:
            self.logger.error(f"Failed to get phone info for {country_code}: {e}")
            return {}
    
    def get_countries_with_cities(self, active_only: bool = True) -> List[Country]:
        """Get countries with their cities prefetched"""
        try:
            queryset = Country.objects.all()
            if active_only:
                queryset = queryset.filter(is_active=True)
            
            return list(queryset.prefetch_related('cities'))
        except Exception as e:
            self.logger.error(f"Failed to get countries with cities: {e}")
            return []
    
    def validate_phone_number(self, phone: str, country_code: CountryCode) -> bool:
        """Validate phone number for country"""
        try:
            country = self.get_country_by_code(country_code)
            if not country:
                return False
            
            # Remove non-digits
            digits = ''.join(filter(str.isdigit, phone))
            
            # Check length
            if len(digits) != country.phone_digits:
                return False
            
            # Check phone code
            phone_code = country.get_safe_phone_code().replace('+', '')
            if not digits.startswith(phone_code):
                return False
            
            return True
        except Exception as e:
            self.logger.error(f"Phone validation error: {e}")
            return False


# ======================== City Service ========================

class CityService(BaseService):
    """Service for city operations"""
    
    def search_cities(self, query: str, country_code: Optional[CountryCode] = None, 
                     limit: int = 10) -> List[City]:
        """Search cities by name"""
        try:
            queryset = City.objects.filter(is_active=True)
            
            if country_code:
                queryset = queryset.filter(country__code=country_code)
            
            if query:
                queryset = queryset.filter(
                    Q(name__icontains=query) |
                    Q(native_name__icontains=query)
                )
            
            return list(queryset.select_related('country', 'timezone')[:limit])
        except Exception as e:
            self.logger.error(f"City search error: {e}")
            return []
    
    def get_capital_cities(self) -> List[City]:
        """Get all capital cities"""
        try:
            return list(City.objects.filter(
                is_capital=True,
                is_active=True
            ).select_related('country'))
        except Exception as e:
            self.logger.error(f"Failed to get capital cities: {e}")
            return []
    
    def get_cities_by_country(self, country_code: CountryCode) -> List[City]:
        """Get all cities in a country"""
        try:
            return City.get_active_cities_for_country(country_code)
        except Exception as e:
            self.logger.error(f"Failed to get cities for {country_code}: {e}")
            return []
    
    def get_nearby_cities(self, latitude: Decimal, longitude: Decimal, 
                         radius_km: int = 50) -> List[City]:
        """
        Find cities within radius
        TODO: Implement with PostGIS for production
        For now, returns empty list as placeholder
        """
        try:
            # This is a placeholder
            # In production, implement using PostGIS:
            # from django.contrib.gis.db.models.functions import Distance
            # from django.contrib.gis.geos import Point
            # 
            # point = Point(longitude, latitude, srid=4326)
            # return City.objects.filter(
            #     location__distance_lte=(point, D(km=radius_km))
            # ).annotate(
            #     distance=Distance('location', point)
            # ).order_by('distance')
            
            self.logger.info("get_nearby_cities called - returning empty list (PostGIS not implemented)")
            return []
            
        except Exception as e:
            self.logger.error(f"Nearby cities error: {e}")
            return []


# ======================== User Preference Service ========================

class UserPreferenceService(BaseService):
    """Service for user language preferences"""
    
    def get_user_preference(self, user) -> Optional[UserLanguagePreference]:
        """Get user's language preferences"""
        try:
            cache_key = f"user_pref:{user.id}"
            cached = self.get_cached(cache_key)
            if cached:
                return cached
            
            pref, created = UserLanguagePreference.objects.get_or_create(user=user)
            self.set_cached(cache_key, pref, CACHE_TIMEOUT)
            
            return pref
        except Exception as e:
            self.logger.error(f"Failed to get user preference: {e}")
            return None
    
    def get_user_effective_language(self, user) -> Optional[Language]:
        """Get effective language for user"""
        try:
            pref = self.get_user_preference(user)
            if pref and pref.effective_language:
                return pref.effective_language
            
            # Fallback to default
            return Language.objects.filter(is_default=True, is_active=True).first()
        except Exception as e:
            self.logger.error(f"Failed to get effective language: {e}")
            return None
    
    def update_user_preference(self, user, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user language preferences"""
        try:
            pref = self.get_user_preference(user)
            
            # Update fields
            if 'primary_language' in data:
                lang = Language.objects.filter(code=data['primary_language']).first()
                if lang:
                    pref.primary_language = lang
            
            if 'ui_language' in data:
                lang = Language.objects.filter(code=data['ui_language']).first()
                if lang:
                    pref.ui_language = lang
            
            if 'content_language' in data:
                lang = Language.objects.filter(code=data['content_language']).first()
                if lang:
                    pref.content_language = lang
            
            if 'auto_translate' in data:
                pref.auto_translate = bool(data['auto_translate'])
            
            pref.save()
            
            # Clear cache
            self.delete_cached(f"user_pref:{user.id}")
            
            return {'success': True, 'preference': pref}
            
        except Exception as e:
            self.logger.error(f"Failed to update user preference: {e}")
            return {'success': False, 'error': str(e)}
    
    def add_preferred_language(self, user, language_code: LanguageCode) -> bool:
        """Add language to user's preferred list"""
        try:
            pref = self.get_user_preference(user)
            return pref.add_preferred_language(language_code)
        except Exception as e:
            self.logger.error(f"Failed to add preferred language: {e}")
            return False
    
    def get_recent_languages(self, user) -> List[Language]:
        """Get user's recently used languages"""
        try:
            pref = self.get_user_preference(user)
            if pref and pref.last_used_languages:
                codes = pref.last_used_languages[:5]
                return list(Language.objects.filter(code__in=codes))
            return []
        except Exception as e:
            self.logger.error(f"Failed to get recent languages: {e}")
            return []


# ======================== Cache Service ========================

class CacheService(BaseService):
    """Service for cache management"""
    
    def clear_all_cache(self) -> bool:
        """Clear all cache"""
        try:
            cache.clear()
            TranslationCache.objects.all().delete()
            self.logger.info("All cache cleared")
            return True
        except Exception as e:
            self.logger.error(f"Failed to clear all cache: {e}")
            return False
    
    def clear_model_cache(self, model_name: str) -> bool:
        """Clear cache for specific model"""
        try:
            patterns = {
                'language': ['language_*', 'languages_*'],
                'country': ['country_*', 'countries_*'],
                'currency': ['currency_*', 'currencies_*', 'exchange_rate_*'],
                'translation': ['translation_*', 'translations_*'],
                'timezone': ['timezone_*', 'timezones_*'],
            }
            
            if model_name in patterns:
                for pattern in patterns[model_name]:
                    self.delete_pattern(pattern)
                
                if model_name == 'translation':
                    TranslationCache.objects.all().delete()
                
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to clear {model_name} cache: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            # This depends on your cache backend
            stats: Dict[str, Any] = {
                'translation_cache_count': TranslationCache.objects.count(),
                'translation_cache_hits': TranslationCache.objects.aggregate(
                    total_hits=models.Sum('hits')
                )['total_hits'] or 0,
            }
            return stats
        except Exception as e:
            self.logger.error(f"Failed to get cache stats: {e}")
            return {}


# ======================== Health Check Service ========================

class HealthCheckService(BaseService):
    """Service for health checks"""
    
    def check_database(self) -> Dict[str, Any]:
        """Check database connectivity"""
        try:
            # Try a simple query
            Language.objects.exists()
            return {'status': 'healthy', 'message': 'Database is reachable'}
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return {'status': 'unhealthy', 'error': str(e)}
    
    def check_cache(self) -> Dict[str, Any]:
        """Check cache connectivity"""
        try:
            cache.set('health_check', 'ok', 10)
            if cache.get('health_check') == 'ok':
                return {'status': 'healthy', 'message': 'Cache is working'}
            return {'status': 'unhealthy', 'message': 'Cache read/write failed'}
        except Exception as e:
            self.logger.error(f"Cache health check failed: {e}")
            return {'status': 'unhealthy', 'error': str(e)}
    
    def check_translation_system(self) -> Dict[str, Any]:
        """Check translation system"""
        try:
            # Check default language
            default_lang = Language.objects.filter(is_default=True).first()
            
            # Check translation counts
            translation_count = Translation.objects.filter(is_approved=True).count()
            key_count = TranslationKey.objects.count()
            
            return {
                'status': 'healthy',
                'default_language': default_lang.code if default_lang else None,
                'translations': translation_count,
                'keys': key_count
            }
        except Exception as e:
            self.logger.error(f"Translation system health check failed: {e}")
            return {'status': 'unhealthy', 'error': str(e)}
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks"""
        return {
            'database': self.check_database(),
            'cache': self.check_cache(),
            'translation_system': self.check_translation_system(),
            'timestamp': timezone.now().isoformat()
        }


# ======================== Service Factory ========================

class ServiceFactory:
    """Factory for creating service instances"""
    
    _instances: Dict[str, BaseService] = {}
    
    @classmethod
    def get_language_service(cls) -> LanguageService:
        if 'language' not in cls._instances:
            cls._instances['language'] = LanguageService()
        return cls._instances['language']
    
    @classmethod
    def get_translation_service(cls) -> TranslationService:
        if 'translation' not in cls._instances:
            cls._instances['translation'] = TranslationService()
        return cls._instances['translation']
    
    @classmethod
    def get_currency_service(cls) -> CurrencyService:
        if 'currency' not in cls._instances:
            cls._instances['currency'] = CurrencyService()
        return cls._instances['currency']
    
    @classmethod
    def get_timezone_service(cls) -> TimezoneService:
        if 'timezone' not in cls._instances:
            cls._instances['timezone'] = TimezoneService()
        return cls._instances['timezone']
    
    @classmethod
    def get_country_service(cls) -> CountryService:
        if 'country' not in cls._instances:
            cls._instances['country'] = CountryService()
        return cls._instances['country']
    
    @classmethod
    def get_city_service(cls) -> CityService:
        if 'city' not in cls._instances:
            cls._instances['city'] = CityService()
        return cls._instances['city']
    
    @classmethod
    def get_user_preference_service(cls) -> UserPreferenceService:
        if 'user_preference' not in cls._instances:
            cls._instances['user_preference'] = UserPreferenceService()
        return cls._instances['user_preference']
    
    @classmethod
    def get_cache_service(cls) -> CacheService:
        if 'cache' not in cls._instances:
            cls._instances['cache'] = CacheService()
        return cls._instances['cache']
    
    @classmethod
    def get_health_check_service(cls) -> HealthCheckService:
        if 'health' not in cls._instances:
            cls._instances['health'] = HealthCheckService()
        return cls._instances['health']
    
    @classmethod
    def clear_instances(cls) -> None:
        """Clear all service instances (useful for testing)"""
        cls._instances = {}


# ======================== Singleton Service Instances ========================

# Create singleton instances for easy access
language_service: LanguageService = ServiceFactory.get_language_service()
translation_service: TranslationService = ServiceFactory.get_translation_service()
currency_service: CurrencyService = ServiceFactory.get_currency_service()
timezone_service: TimezoneService = ServiceFactory.get_timezone_service()
country_service: CountryService = ServiceFactory.get_country_service()
city_service: CityService = ServiceFactory.get_city_service()
user_preference_service: UserPreferenceService = ServiceFactory.get_user_preference_service()
cache_service: CacheService = ServiceFactory.get_cache_service()
health_check_service: HealthCheckService = ServiceFactory.get_health_check_service()