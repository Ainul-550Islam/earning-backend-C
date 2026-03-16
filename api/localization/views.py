# views.py
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view, permission_classes
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django.views import View
from django.db.models import Q, Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.core.exceptions import PermissionDenied
from django.views.decorators.gzip import gzip_page
from django.views.decorators.vary import vary_on_headers
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django_ratelimit.decorators import ratelimit
from .models import TranslationCache
from .serializers import TranslationSerializer, TranslationKeySerializer,  LanguageSerializer, MissingTranslationSerializer, TranslationCacheSerializer
import logging
import json
from typing import Dict, Any, Optional, List
from decimal import Decimal, DivisionByZero, InvalidOperation
from .models import (
    Language, Country, Currency, Timezone, City,
    TranslationKey, Translation, TranslationCache,
    UserLanguagePreference, MissingTranslation
)

logger = logging.getLogger(__name__)

# ======================== Constants ========================
CACHE_TIMEOUT = getattr(settings, 'API_CACHE_TIMEOUT', 3600)
CACHE_24_HOURS = getattr(settings, 'CACHE_24_HOURS', 86400)
PAGE_SIZE = getattr(settings, 'PAGE_SIZE', 20)
MAX_PAGE_SIZE = getattr(settings, 'MAX_PAGE_SIZE', 100)
MAX_TEXT_LENGTH = getattr(settings, 'MAX_TRANSLATION_TEXT_LENGTH', 5000)

# Tracked cache keys for invalidation
TRACKED_CACHE_KEYS = getattr(settings, 'TRACKED_CACHE_KEYS', [])


# ======================== Cache Key Constants ========================
class CacheKeys:
    """Centralized cache key management"""
    LANGUAGES = 'languages_list_v1'
    COUNTRIES = 'countries_list_v1'
    CURRENCIES = 'currencies_list_v1'
    TIMEZONES = 'timezones_list_v1'
    API_DOCS = 'api_docs_v1'
    
    @staticmethod
    def language_detail(code: str) -> str:
        return f"language_detail_{code}"
    
    @staticmethod
    def country_detail(code: str, include_cities: bool = False) -> str:
        return f"country_detail_{code}_{include_cities}"
    
    @staticmethod
    def cities_list(country: str = 'all', page: int = 1, per_page: int = 20) -> str:
        return f"cities_list_{country}_{page}_{per_page}"
    
    @staticmethod
    def user_preference(user_id: int) -> str:
        return f"user_pref_{user_id}"
    
    @staticmethod
    def translation_api(language_code: str) -> str:
        return f"translations_api_{language_code}"


# ======================== Parameter Constants ========================
class ParamKeys:
    PAGE = 'page'
    PER_PAGE = 'per_page'
    SEARCH = 'search'
    INCLUDE_CITIES = 'include_cities'
    COUNTRY = 'country'
    FROM = 'from'
    TO = 'to'
    AMOUNT = 'amount'
    TEXT = 'text'
    LANGUAGE_CODE = 'language_code'
    CACHE_TYPE = 'type'


# ======================== Custom Exception Classes ========================
class APIError(Exception):
    """Base API exception"""
    def __init__(self, message, status_code=400, code=None, field=None):
        self.message = message
        self.status_code = status_code
        self.code = code or 'api_error'
        self.field = field
        super().__init__(message)


# ======================== Base View with Advanced Defensive Coding ========================
class BulletproofView(View):
    """Base view with advanced defensive coding techniques"""
    
    api_version = 'v1'
    cache_timeout = CACHE_TIMEOUT
    rate_limit = '100/h'  # Default rate limit
    
    @method_decorator(ratelimit(key='ip', rate='100/h', method='ALL', block=True))
    def dispatch(self, request, *args, **kwargs):
        """Main dispatch with rate limiting and error handling"""
        try:
            response = super().dispatch(request, *args, **kwargs)
            
            # Add security headers
            if isinstance(response, JsonResponse):
                response['X-Content-Type-Options'] = 'nosniff'
                response['X-Frame-Options'] = 'DENY'
                response['API-Version'] = self.api_version
            
            return response
            
        except PermissionDenied:
            return self.error_response("Permission denied", 403, 'permission_denied')
        except Exception as e:
            logger.error(f"Unhandled exception in {self.__class__.__name__}: {e}", exc_info=True)
            return self.error_response("Internal server error", 500, 'internal_error')
    
    # ======================== Pagination Helpers ========================
    @property
    def page(self) -> int:
        try:
            page = int(self.request.GET.get(ParamKeys.PAGE, 1))
            return max(1, page)
        except (TypeError, ValueError):
            return 1
    
    @property
    def per_page(self) -> int:
        try:
            per_page = int(self.request.GET.get(ParamKeys.PER_PAGE, PAGE_SIZE))
            return min(max(1, per_page), MAX_PAGE_SIZE)
        except (TypeError, ValueError):
            return PAGE_SIZE
    
    def paginate_queryset(self, queryset):
        try:
            paginator = Paginator(queryset, self.per_page)
            return paginator.get_page(self.page)
        except (PageNotAnInteger, EmptyPage):
            return paginator.get_page(1)
        except Exception as e:
            logger.error(f"Pagination error: {e}")
            return []
    
    # ======================== Parameter Extraction ========================
    def get_param(self, param_name: str, default=None, param_type=str):
        try:
            value = self.request.GET.get(param_name, default)
            if value is not None and param_type != str:
                return param_type(value)
            return value
        except (TypeError, ValueError):
            return default
    
    def get_post_data(self) -> Dict:
        try:
            if self.request.content_type == 'application/json':
                return json.loads(self.request.body)
            return self.request.POST.dict()
        except json.JSONDecodeError:
            raise APIError("Invalid JSON data", 400, 'invalid_json')
        except Exception as e:
            logger.error(f"Failed to parse POST data: {e}")
            return {}
    
    # ======================== Response Helpers ========================
    def success_response(self, data: Any = None, message: str = None, status: int = 200):
        response = {
            'success': True,
            'timestamp': timezone.now().isoformat(),
        }
        
        if message:
            response['message'] = message
        if data is not None:
            response['data'] = data
        
        return JsonResponse(response, status=status)
    
    def error_response(self, message: str, status: int = 400, code: str = None, field: str = None):
        response = {
            'success': False,
            'error': message,
            'code': code or 'error',
            'timestamp': timezone.now().isoformat(),
        }
        
        if field:
            response['field'] = field
        
        return JsonResponse(response, status=status)
    
    # ======================== Cache Helpers ========================
    def get_cached(self, key: str, default=None):
        """Get from Django cache"""
        try:
            return cache.get(key, default)
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            return default
    
    def set_cached(self, key: str, value: Any, timeout: int = None):
        """Set to Django cache and track key"""
        try:
            cache.set(key, value, timeout or self.cache_timeout)
            # Track key for invalidation
            if key not in TRACKED_CACHE_KEYS:
                TRACKED_CACHE_KEYS.append(key)
            return True
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
            return False
    
    def delete_cached(self, key: str):
        """Delete from cache"""
        try:
            cache.delete(key)
            if key in TRACKED_CACHE_KEYS:
                TRACKED_CACHE_KEYS.remove(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")
            return False


# ======================== Language Views ========================
class LanguageListView(BulletproofView):
    """List all active languages"""
    cache_timeout = CACHE_24_HOURS
    
    @method_decorator(gzip_page)
    @method_decorator(vary_on_headers('Accept-Language'))
    def get(self, request):
        try:
            # Use Django cache only (Option 1)
            cached_data = self.get_cached(CacheKeys.LANGUAGES)
            if cached_data:
                return self.success_response(cached_data)
            
            languages = Language.objects.filter(is_active=True)
            
            search = self.get_param(ParamKeys.SEARCH)
            if search:
                languages = languages.filter(
                    Q(name__icontains=search) | 
                    Q(code__icontains=search)
                )
            
            default_lang = Language.objects.filter(is_default=True).first()
            paginated = self.paginate_queryset(languages)
            
            data = {
                'default_language': {
                    'code': default_lang.code if default_lang else 'en',
                    'name': default_lang.name if default_lang else 'English'
                } if default_lang else None,
                'languages': [
                    {
                        'code': lang.code,
                        'name': lang.name,
                        'name_native': lang.name_native or lang.name,
                        'is_rtl': lang.is_rtl,
                        'flag_emoji': lang.flag_emoji or '🌐',
                        'locale_code': lang.locale_code or lang.code,
                    }
                    for lang in paginated
                ],
                'pagination': {
                    'total': languages.count(),
                    'page': paginated.number,
                    'pages': paginated.paginator.num_pages if hasattr(paginated, 'paginator') else 1,
                    'per_page': self.per_page,
                }
            }
            
            self.set_cached(CacheKeys.LANGUAGES, data, CACHE_24_HOURS)
            return self.success_response(data)
            
        except Exception as e:
            logger.error(f"Language list error: {e}")
            return self.error_response(
                "Failed to load languages", 
                status=500,
                code='language_list_error'
            )


class LanguageDetailView(BulletproofView):
    """Get language details by code"""
    cache_timeout = CACHE_24_HOURS
    
    def get(self, request, code):
        try:
            cache_key = CacheKeys.language_detail(code)
            cached_data = self.get_cached(cache_key)
            if cached_data:
                return self.success_response(cached_data)
            
            language = get_object_or_404(Language, code=code)
            
            data = {
                'code': language.code,
                'name': language.name,
                'name_native': language.name_native or language.name,
                'is_active': language.is_active,
                'is_default': language.is_default,
                'is_rtl': language.is_rtl,
                'flag_emoji': language.flag_emoji or '🌐',
                'locale_code': language.locale_code or language.code,
                'created_at': language.created_at.isoformat() if language.created_at else None,
            }
            
            self.set_cached(cache_key, data, CACHE_24_HOURS)
            return self.success_response(data)
            
        except Exception as e:
            logger.error(f"Language detail error: {e}")
            return self.error_response(
                "Language not found", 
                status=404,
                code='language_not_found'
            )


# ======================== Country Views ========================
class CountryListView(BulletproofView):
    """List all active countries"""
    cache_timeout = CACHE_24_HOURS
    
    @method_decorator(gzip_page)
    def get(self, request):
        try:
            cached_data = self.get_cached(CacheKeys.COUNTRIES)
            if cached_data:
                return self.success_response(cached_data)
            
            countries = Country.get_active_countries()
            
            search = self.get_param(ParamKeys.SEARCH)
            if search:
                countries = countries.filter(
                    Q(name__icontains=search) | 
                    Q(code__icontains=search)
                )
            
            paginated = self.paginate_queryset(countries)
            
            data = {
                'countries': [
                    {
                        'code': c.code,
                        'code_alpha3': c.code_alpha3 or c.code,
                        'name': c.name,
                        'native_name': c.native_name or c.name,
                        'phone_code': c.get_safe_phone_code(),
                        'phone_digits': c.phone_digits,
                        'flag_emoji': c.flag_emoji or '🏳️',
                        'flag_svg_url': c.flag_svg_url or '',
                    }
                    for c in paginated
                ],
                'pagination': {
                    'total': countries.count(),
                    'page': paginated.number,
                    'pages': paginated.paginator.num_pages if hasattr(paginated, 'paginator') else 1,
                    'per_page': self.per_page,
                }
            }
            
            self.set_cached(CacheKeys.COUNTRIES, data, CACHE_24_HOURS)
            return self.success_response(data)
            
        except Exception as e:
            logger.error(f"Country list error: {e}")
            return self.error_response(
                "Failed to load countries",
                status=500,
                code='country_list_error'
            )


class CountryDetailView(BulletproofView):
    """Get country details with cities"""
    cache_timeout = CACHE_24_HOURS
    
    def get(self, request, code):
        try:
            include_cities = self.get_param(ParamKeys.INCLUDE_CITIES, 'false').lower() == 'true'
            cache_key = CacheKeys.country_detail(code, include_cities)
            
            cached_data = self.get_cached(cache_key)
            if cached_data:
                return self.success_response(cached_data)
            
            country = get_object_or_404(Country, code=code.upper())
            
            data = {
                'code': country.code,
                'code_alpha3': country.code_alpha3 or country.code,
                'name': country.name,
                'native_name': country.native_name or country.name,
                'phone_code': country.get_safe_phone_code(),
                'phone_digits': country.phone_digits,
                'flag_emoji': country.flag_emoji or '🏳️',
                'flag_svg_url': country.flag_svg_url or '',
                'is_active': country.is_active,
            }
            
            if include_cities:
                cities = City.get_active_cities_for_country(country.code)
                data['cities'] = [
                    {
                        'id': city.id,
                        'name': city.name,
                        'native_name': city.native_name or city.name,
                        'is_capital': city.is_capital,
                        'timezone': city.timezone.name if city.timezone else None,
                    }
                    for city in cities
                ]
            
            self.set_cached(cache_key, data, CACHE_24_HOURS)
            return self.success_response(data)
            
        except Exception as e:
            logger.error(f"Country detail error: {e}")
            return self.error_response(
                "Country not found",
                status=404,
                code='country_not_found'
            )


# ======================== Currency Views ========================
class CurrencyListView(BulletproofView):
    """List all active currencies"""
    cache_timeout = CACHE_24_HOURS
    
    @method_decorator(gzip_page)
    def get(self, request):
        try:
            cached_data = self.get_cached(CacheKeys.CURRENCIES)
            if cached_data:
                return self.success_response(cached_data)
            
            currencies = Currency.objects.filter(is_active=True)
            default_currency = currencies.filter(is_default=True).first()
            
            data = {
                'currencies': [
                    {
                        'code': c.code,
                        'name': c.name,
                        'symbol': c.symbol,
                        'symbol_native': c.symbol_native or c.symbol,
                        'decimal_digits': c.decimal_digits,
                        'is_default': c.is_default,
                        'exchange_rate': str(c.exchange_rate),
                    }
                    for c in currencies
                ],
                'default_currency': {
                    'code': default_currency.code if default_currency else 'USD',
                    'symbol': default_currency.symbol if default_currency else '$'
                } if default_currency else {'code': 'USD', 'symbol': '$'},
                'total': currencies.count()
            }
            
            self.set_cached(CacheKeys.CURRENCIES, data, CACHE_24_HOURS)
            return self.success_response(data)
            
        except Exception as e:
            logger.error(f"Currency list error: {e}")
            return self.error_response(
                "Failed to load currencies",
                status=500,
                code='currency_list_error'
            )


class CurrencyConvertView(BulletproofView):
    """Convert amount between currencies"""
    
    def get(self, request):
        try:
            amount_str = self.get_param(ParamKeys.AMOUNT, '1')
            from_code = self.get_param(ParamKeys.FROM, 'USD').upper()
            to_code = self.get_param(ParamKeys.TO, 'BDT').upper()
            
            try:
                amount = Decimal(amount_str)
                if amount <= 0:
                    raise APIError("Amount must be positive", 400, 'invalid_amount', ParamKeys.AMOUNT)
            except (InvalidOperation, TypeError):
                raise APIError("Invalid amount format", 400, 'invalid_amount', ParamKeys.AMOUNT)
            
            from_curr = Currency.objects.filter(code=from_code, is_active=True).first()
            to_curr = Currency.objects.filter(code=to_code, is_active=True).first()
            
            if not from_curr:
                raise APIError(f"Currency not found: {from_code}", 404, 'currency_not_found', ParamKeys.FROM)
            if not to_curr:
                raise APIError(f"Currency not found: {to_code}", 404, 'currency_not_found', ParamKeys.TO)
            
            if from_curr.exchange_rate == 0:
                logger.error(f"Zero exchange rate for {from_curr.code}")
                return self.error_response(
                    "Invalid exchange rate for source currency",
                    status=500,
                    code='exchange_rate_error'
                )
            
            try:
                if from_code == 'USD':
                    converted = amount * to_curr.exchange_rate
                elif to_code == 'USD':
                    converted = amount / from_curr.exchange_rate
                else:
                    in_usd = amount / from_curr.exchange_rate
                    converted = in_usd * to_curr.exchange_rate
            except (DivisionByZero, InvalidOperation):
                return self.error_response(
                    "Conversion calculation failed",
                    status=500,
                    code='conversion_error'
                )
            
            formatted_from = from_curr.format_amount(amount)
            formatted_to = to_curr.format_amount(converted)
            
            data = {
                'from': {
                    'code': from_curr.code,
                    'amount': str(amount),
                    'formatted': formatted_from,
                },
                'to': {
                    'code': to_curr.code,
                    'amount': str(converted),
                    'formatted': formatted_to,
                },
                'exchange_rate': str(to_curr.exchange_rate / from_curr.exchange_rate),
                'updated_at': to_curr.exchange_rate_updated_at.isoformat() if to_curr.exchange_rate_updated_at else None,
            }
            
            return self.success_response(data)
            
        except APIError as e:
            return self.error_response(e.message, e.status_code, e.code, e.field)
        except Exception as e:
            logger.error(f"Currency conversion error: {e}")
            return self.error_response(
                "Conversion failed",
                status=500,
                code='conversion_error'
            )


# ======================== Timezone Views ========================
class TimezoneListView(BulletproofView):
    """List all timezones"""
    cache_timeout = CACHE_24_HOURS
    
    @method_decorator(gzip_page)
    def get(self, request):
        try:
            cached_data = self.get_cached(CacheKeys.TIMEZONES)
            if cached_data:
                return self.success_response(cached_data)
            
            timezones = Timezone.objects.filter(is_active=True)
            
            grouped = {}
            for tz in timezones:
                offset = tz.offset or '+00:00'
                if offset not in grouped:
                    grouped[offset] = []
                grouped[offset].append({
                    'name': tz.name,
                    'code': tz.code,
                    'is_dst': tz.is_dst,
                })
            
            current_time = Timezone.get_current_time()
            
            data = [
                {
                    'offset': offset,
                    'offset_seconds': self._offset_to_seconds(offset),
                    'timezones': zones,
                    'sample_time': self._get_sample_time(offset),
                }
                for offset, zones in grouped.items()
            ]
            
            data.sort(key=lambda x: x['offset_seconds'])
            
            response_data = {
                'timezones': data,
                'total': timezones.count(),
                'server_time': current_time.isoformat(),
            }
            
            self.set_cached(CacheKeys.TIMEZONES, response_data, CACHE_24_HOURS)
            return self.success_response(response_data)
            
        except Exception as e:
            logger.error(f"Timezone list error: {e}")
            return self.error_response(
                "Failed to load timezones",
                status=500,
                code='timezone_list_error'
            )
    
    def _offset_to_seconds(self, offset):
        try:
            sign = 1 if offset[0] == '+' else -1
            hours = int(offset[1:3])
            minutes = int(offset[4:6])
            return sign * (hours * 3600 + minutes * 60)
        except (IndexError, ValueError):
            return 0
    
    def _get_sample_time(self, offset):
        try:
            tz = Timezone.objects.filter(offset=offset, is_active=True).first()
            if tz:
                return Timezone.get_current_time(tz.name).isoformat()
            return timezone.now().isoformat()
        except Exception:
            return timezone.now().isoformat()


# ======================== Translation Views ========================
class TranslationView(BulletproofView):
    """Get translations for a language - Using Django Cache only"""
    
    def get(self, request, language_code):
        try:
            # Use Django cache only (Option 1)
            cache_key = CacheKeys.translation_api(language_code)
            cached_data = self.get_cached(cache_key)
            
            if cached_data:
                return self.success_response(cached_data)
            
            # Get language
            language = Language.objects.filter(code=language_code, is_active=True).first()
            if not language:
                language = Language.objects.filter(is_default=True, is_active=True).first()
                if not language:
                    MissingTranslation.log_missing(
                        key='language_not_found',
                        language_code=language_code,
                        request=request,
                        user=request.user if request.user.is_authenticated else None
                    )
                    return self.error_response(
                        "Language not found",
                        status=404,
                        code='language_not_found'
                    )
            
            # Get translations with optimized query
            translations = Translation.objects.filter(
                language=language,
                is_approved=True
            ).select_related('key').only('key__key', 'value')
            
            data = {
                'language': {
                    'code': language.code,
                    'name': language.name,
                    'is_rtl': language.is_rtl,
                },
                'translations': {
                    t.key.key: t.value
                    for t in translations
                },
                'count': translations.count(),
            }
            
            # Save to Django cache
            self.set_cached(cache_key, data, self.cache_timeout)
            
            return self.success_response(data)
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return self.error_response(
                "Failed to load translations",
                status=500,
                code='translation_error'
            )


@require_http_methods(["POST"])
@ensure_csrf_cookie
def translate_text(request):
    """Translate a single text (with fallback)"""
    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON',
                'code': 'invalid_json'
            }, status=400)
        
        text = data.get(ParamKeys.TEXT, '').strip()
        from_lang = data.get(ParamKeys.FROM, 'en').lower()
        to_lang = data.get(ParamKeys.TO, 'bn').lower()
        
        if not text:
            return JsonResponse({
                'success': False,
                'error': 'Text is required',
                'code': 'text_required',
                'field': ParamKeys.TEXT
            }, status=400)
        
        if len(text) > MAX_TEXT_LENGTH:
            return JsonResponse({
                'success': False,
                'error': f'Text too long (max {MAX_TEXT_LENGTH} characters)',
                'code': 'text_too_long',
                'field': ParamKeys.TEXT
            }, status=400)
        
        from_lang_obj = Language.objects.filter(code=from_lang, is_active=True).first()
        to_lang_obj = Language.objects.filter(code=to_lang, is_active=True).first()
        
        if not from_lang_obj:
            return JsonResponse({
                'success': False,
                'error': f'Invalid source language: {from_lang}',
                'code': 'invalid_language',
                'field': ParamKeys.FROM
            }, status=400)
        
        if not to_lang_obj:
            return JsonResponse({
                'success': False,
                'error': f'Invalid target language: {to_lang}',
                'code': 'invalid_language',
                'field': ParamKeys.TO
            }, status=400)
        
        # Here you would call your translation service
        return JsonResponse({
            'success': True,
            'data': {
                'original': text,
                'translated': f"[{from_lang} to {to_lang}] {text}",
                'from': from_lang,
                'to': to_lang,
                'character_count': len(text),
            },
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Translate text error: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Translation failed',
            'code': 'translation_error'
        }, status=500)


# ======================== User Preference Views ========================
@method_decorator(login_required, name='dispatch')
class UserLanguagePreferenceView(BulletproofView):
    """Get/Update user language preferences"""
    
    def get(self, request):
        try:
            cache_key = CacheKeys.user_preference(request.user.id)
            cached_data = self.get_cached(cache_key)
            if cached_data:
                return self.success_response(cached_data)
            
            pref, created = UserLanguagePreference.objects.select_related(
                'primary_language', 'ui_language', 'content_language'
            ).prefetch_related(
                Prefetch('preferred_languages', 
                        queryset=Language.objects.filter(is_active=True))
            ).get_or_create(user=request.user)
            
            effective = pref.effective_language
            
            data = {
                'primary_language': {
                    'code': pref.primary_language.code,
                    'name': pref.primary_language.name,
                } if pref.primary_language else None,
                'ui_language': {
                    'code': pref.ui_language.code,
                    'name': pref.ui_language.name,
                } if pref.ui_language else None,
                'content_language': {
                    'code': pref.content_language.code,
                    'name': pref.content_language.name,
                } if pref.content_language else None,
                'effective_language': {
                    'code': effective.code,
                    'name': effective.name,
                } if effective else {'code': 'en', 'name': 'English'},
                'auto_translate': pref.auto_translate,
                'preferred_languages': [
                    {'code': lang.code, 'name': lang.name}
                    for lang in pref.preferred_languages.all()
                ],
            }
            
            self.set_cached(cache_key, data, CACHE_TIMEOUT)
            return self.success_response(data)
            
        except Exception as e:
            logger.error(f"User preference error: {e}")
            return self.error_response(
                "Failed to load preferences",
                status=500,
                code='preference_load_error'
            )
    
    def post(self, request):
        try:
            data = self.get_post_data()
            pref, created = UserLanguagePreference.objects.get_or_create(
                user=request.user
            )
            
            if ParamKeys.LANGUAGE_CODE in data:
                lang = Language.objects.filter(
                    code=data[ParamKeys.LANGUAGE_CODE], 
                    is_active=True
                ).first()
                if lang:
                    # Determine which field to update based on context
                    if 'primary' in data.get('type', ''):
                        pref.primary_language = lang
                    elif 'ui' in data.get('type', ''):
                        pref.ui_language = lang
                    elif 'content' in data.get('type', ''):
                        pref.content_language = lang
                else:
                    return self.error_response(
                        "Invalid language",
                        field=ParamKeys.LANGUAGE_CODE,
                        code='invalid_language'
                    )
            
            if 'auto_translate' in data:
                pref.auto_translate = bool(data['auto_translate'])
            
            pref.save()
            
            # Clear cached preferences
            cache_key = CacheKeys.user_preference(request.user.id)
            self.delete_cached(cache_key)
            
            return self.success_response(
                message="Preferences updated successfully"
            )
            
        except APIError as e:
            return self.error_response(e.message, e.status_code, e.code, e.field)
        except Exception as e:
            logger.error(f"Update preference error: {e}")
            return self.error_response(
                "Failed to update preferences",
                status=500,
                code='preference_update_error'
            )


@login_required
@require_http_methods(["POST"])
def add_preferred_language(request):
    """Add a language to user's preferred list"""
    try:
        data = json.loads(request.body)
        language_code = data.get(ParamKeys.LANGUAGE_CODE)
        
        if not language_code:
            return JsonResponse({
                'success': False,
                'error': 'Language code required',
                'code': 'language_code_required',
                'field': ParamKeys.LANGUAGE_CODE
            }, status=400)
        
        language = Language.objects.filter(code=language_code, is_active=True).first()
        if not language:
            return JsonResponse({
                'success': False,
                'error': f'Language not found: {language_code}',
                'code': 'language_not_found',
                'field': ParamKeys.LANGUAGE_CODE
            }, status=404)
        
        pref, created = UserLanguagePreference.objects.get_or_create(user=request.user)
        success = pref.add_preferred_language(language_code)
        
        if success:
            # Clear cached preferences
            cache.delete(CacheKeys.user_preference(request.user.id))
            
            return JsonResponse({
                'success': True,
                'message': f'Added {language.name} to preferred languages',
                'data': {
                    'code': language.code,
                    'name': language.name
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to add language',
                'code': 'add_language_failed'
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON',
            'code': 'invalid_json'
        }, status=400)
    except Exception as e:
        logger.error(f"Add preferred language error: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to add language',
            'code': 'server_error'
        }, status=500)


# ======================== City Views ========================
class CityListView(BulletproofView):
    """List cities by country"""
    cache_timeout = CACHE_24_HOURS
    
    @method_decorator(gzip_page)
    def get(self, request):
        try:
            country_code = self.get_param(ParamKeys.COUNTRY, 'all')
            cache_key = CacheKeys.cities_list(country_code, self.page, self.per_page)
            
            cached_data = self.get_cached(cache_key)
            if cached_data:
                return self.success_response(cached_data)
            
            cities = City.objects.filter(is_active=True).select_related('country', 'timezone')
            
            if country_code != 'all':
                cities = cities.filter(country__code=country_code.upper())
            
            search = self.get_param(ParamKeys.SEARCH)
            if search:
                cities = cities.filter(
                    Q(name__icontains=search) | 
                    Q(native_name__icontains=search)
                )
            
            paginated = self.paginate_queryset(cities)
            
            data = {
                'cities': [
                    {
                        'id': city.id,
                        'name': city.name,
                        'native_name': city.native_name or city.name,
                        'country_code': city.country.code if city.country else None,
                        'country_name': city.country.name if city.country else None,
                        'is_capital': city.is_capital,
                        'timezone': city.timezone.name if city.timezone else None,
                        'latitude': str(city.latitude) if city.latitude else None,
                        'longitude': str(city.longitude) if city.longitude else None,
                    }
                    for city in paginated
                ],
                'pagination': {
                    'total': cities.count(),
                    'page': paginated.number,
                    'pages': paginated.paginator.num_pages if hasattr(paginated, 'paginator') else 1,
                    'per_page': self.per_page,
                }
            }
            
            self.set_cached(cache_key, data, CACHE_24_HOURS)
            return self.success_response(data)
            
        except Exception as e:
            logger.error(f"City list error: {e}")
            return self.error_response(
                "Failed to load cities",
                status=500,
                code='city_list_error'
            )


# ======================== Health Check ========================
@require_http_methods(["GET"])
def health_check(request):
    """Health check endpoint for monitoring"""
    health_status = {
        'success': True,
        'data': {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'version': '1.0',
            'services': {}
        }
    }
    
    try:
        language_count = Language.objects.count()
        health_status['data']['services']['database'] = {
            'status': 'ok',
            'records': language_count
        }
    except Exception as e:
        health_status['data']['services']['database'] = {
            'status': 'error',
            'error': str(e)
        }
        health_status['data']['status'] = 'degraded'
    
    try:
        cache.set('health_check', 'ok', 10)
        cache_ok = cache.get('health_check') == 'ok'
        health_status['data']['services']['cache'] = {
            'status': 'ok' if cache_ok else 'error'
        }
        if not cache_ok:
            health_status['data']['status'] = 'degraded'
    except Exception as e:
        health_status['data']['services']['cache'] = {
            'status': 'error',
            'error': str(e)
        }
        health_status['data']['status'] = 'degraded'
    
    return JsonResponse(health_status)


# ======================== API Documentation ========================
@require_http_methods(["GET"])
@cache_page(CACHE_24_HOURS)
def api_docs(request):
    """Simple API documentation"""
    docs = {
        'success': True,
        'data': {
            'name': 'Localization API',
            'version': 'v1',
            'base_url': '/api/v1/',
            'endpoints': [
                {
                    'path': '/api/v1/languages/',
                    'method': 'GET',
                    'description': 'List all active languages',
                    'params': [
                        {'name': ParamKeys.SEARCH, 'type': 'string', 'required': False},
                        {'name': ParamKeys.PAGE, 'type': 'integer', 'required': False, 'default': 1},
                        {'name': ParamKeys.PER_PAGE, 'type': 'integer', 'required': False, 'default': 20}
                    ]
                },
                {
                    'path': '/api/v1/languages/{code}/',
                    'method': 'GET',
                    'description': 'Get language details by code'
                },
                {
                    'path': '/api/v1/countries/',
                    'method': 'GET',
                    'description': 'List all active countries'
                },
                {
                    'path': '/api/v1/countries/{code}/',
                    'method': 'GET',
                    'description': 'Get country details',
                    'params': [
                        {'name': ParamKeys.INCLUDE_CITIES, 'type': 'boolean', 'required': False, 'default': False}
                    ]
                },
                {
                    'path': '/api/v1/currencies/',
                    'method': 'GET',
                    'description': 'List all active currencies'
                },
                {
                    'path': '/api/v1/currency/convert/',
                    'method': 'GET',
                    'description': 'Convert amount between currencies',
                    'params': [
                        {'name': ParamKeys.AMOUNT, 'type': 'number', 'required': False, 'default': 1},
                        {'name': ParamKeys.FROM, 'type': 'string', 'required': False, 'default': 'USD'},
                        {'name': ParamKeys.TO, 'type': 'string', 'required': False, 'default': 'BDT'}
                    ]
                },
                {
                    'path': '/api/v1/timezones/',
                    'method': 'GET',
                    'description': 'List all timezones'
                },
                {
                    'path': '/api/v1/translations/{language_code}/',
                    'method': 'GET',
                    'description': 'Get translations for a language'
                },
                {
                    'path': '/api/v1/translate/',
                    'method': 'POST',
                    'description': 'Translate text',
                    'body': [
                        {'name': ParamKeys.TEXT, 'type': 'string', 'required': True},
                        {'name': ParamKeys.FROM, 'type': 'string', 'required': False, 'default': 'en'},
                        {'name': ParamKeys.TO, 'type': 'string', 'required': False, 'default': 'bn'}
                    ]
                },
                {
                    'path': '/api/v1/user/preferences/',
                    'method': 'GET, POST',
                    'description': 'Get/update user language preferences',
                    'auth_required': True
                },
                {
                    'path': '/api/v1/user/preferences/add-language/',
                    'method': 'POST',
                    'description': 'Add language to preferred list',
                    'auth_required': True,
                    'body': [
                        {'name': ParamKeys.LANGUAGE_CODE, 'type': 'string', 'required': True}
                    ]
                },
                {
                    'path': '/api/v1/cities/',
                    'method': 'GET',
                    'description': 'List cities',
                    'params': [
                        {'name': ParamKeys.COUNTRY, 'type': 'string', 'required': False},
                        {'name': ParamKeys.SEARCH, 'type': 'string', 'required': False},
                        {'name': ParamKeys.PAGE, 'type': 'integer', 'required': False},
                        {'name': ParamKeys.PER_PAGE, 'type': 'integer', 'required': False}
                    ]
                },
                {
                    'path': '/api/v1/health/',
                    'method': 'GET',
                    'description': 'Health check endpoint'
                }
            ]
        }
    }
    
    return JsonResponse(docs, json_dumps_params={'indent': 2})


# ======================== Cache Invalidation Views (Admin Only) ========================
@method_decorator(login_required, name='dispatch')
class CacheInvalidationView(BulletproofView):
    """Invalidate cache for specific endpoints (admin only)"""
    
    def post(self, request):
        if not request.user.is_staff:
            raise PermissionDenied
        
        data = self.get_post_data()
        cache_type = data.get(ParamKeys.CACHE_TYPE, 'all')
        
        try:
            if cache_type == 'all':
                # Clear all cache
                cache.clear()
                # Also clear TranslationCache model if you're using it
                TranslationCache.objects.all().delete()
                message = "All cache cleared"
                
            elif cache_type == 'translations':
                # Clear translation-related cache keys
                pattern = CacheKeys.translation_api('*')
                # Use tracked keys instead of pattern matching
                for key in TRACKED_CACHE_KEYS:
                    if key.startswith('translations_api_'):
                        cache.delete(key)
                TranslationCache.objects.filter(expires_at__gt=timezone.now()).delete()
                message = "Translation cache cleared"
                
            elif cache_type == 'currencies':
                # Clear currency-related cache
                count = 0
                for key in TRACKED_CACHE_KEYS:
                    if key.startswith('currency_'):
                        cache.delete(key)
                        count += 1
                message = f"Cleared {count} currency cache entries"
                
            elif cache_type == 'languages':
                cache.delete(CacheKeys.LANGUAGES)
                # Also delete all language detail keys
                for key in TRACKED_CACHE_KEYS:
                    if key.startswith('language_detail_'):
                        cache.delete(key)
                message = "Language cache cleared"
                
            else:
                return self.error_response("Invalid cache type", code='invalid_cache_type')
            
            logger.info(f"Cache invalidated by {request.user.email}: {cache_type}")
            return self.success_response(message=message)
            
        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")
            return self.error_response(
                "Failed to invalidate cache",
                status=500,
                code='cache_invalidation_error'
            )
            
            
            
class LanguageViewSet(viewsets.ModelViewSet):
    """
    Language ViewSet to manage supported languages
    """
    queryset = Language.objects.filter(is_active=True)
    serializer_class = LanguageSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'code' # এর ফলে আইডি (1, 2) এর বদলে কোড (en, bn) দিয়ে API কল করা যাবে

    def get_queryset(self):
        """
        একটি ফিল্টার রাখা হয়েছে যাতে অ্যাডমিন সব ল্যাঙ্গুয়েজ দেখে, 
        কিন্তু ইউজাররা শুধু একটিভ ল্যাঙ্গুয়েজ দেখে।
        """
        if self.request.user.is_staff:
            return Language.objects.all().order_by('-is_default', 'name')
        return Language.objects.filter(is_active=True).order_by('-is_default', 'name')

    @action(detail=False, methods=['get'])
    def default(self, request):
        """
        সরাসরি ডিফল্ট ল্যাঙ্গুয়েজ পাওয়ার জন্য: /api/localization/languages/default/
        """
        try:
            default_lang = Language.objects.filter(is_default=True, is_active=True).first()
            if not default_lang:
                # যদি কোনো ডিফল্ট না থাকে তবে প্রথম একটিভটি দাও
                default_lang = Language.objects.filter(is_active=True).first()
            
            if default_lang:
                serializer = self.get_serializer(default_lang)
                return Response(serializer.data)
            return Response({"error": "No active language found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error fetching default language: {e}")
            return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticatedOrReadOnly])
    def set_default(self, request, code=None):
        """
        অ্যাডমিন চাইলে API দিয়ে ডিফল্ট ল্যাঙ্গুয়েজ চেঞ্জ করতে পারবে
        """
        if not request.user.is_staff:
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
            
        language = self.get_object()
        language.is_default = True
        language.save()
        return Response({"message": f"{language.name} is now set as default."})
    
class TranslationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing translations
    """
    queryset = Translation.objects.filter(is_approved=True)
    serializer_class = TranslationSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        """
        Filter by language if provided
        """
        queryset = Translation.objects.all()
        
        # Filter by language
        language_code = self.request.query_params.get('language', None)
        if language_code:
            queryset = queryset.filter(language__code=language_code)
        
        # Filter by approval status (staff can see all)
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_approved=True)
        
        return queryset.select_related('key', 'language')
    
    @action(detail=False, methods=['get'])
    def by_language(self, request):
        """
        Get translations grouped by language
        """
        language_code = request.query_params.get('code', None)
        if not language_code:
            return Response({"error": "Language code required"}, status=status.HTTP_400_BAD_REQUEST)
        
        translations = Translation.objects.filter(
            language__code=language_code,
            is_approved=True
        ).select_related('key')
        
        data = {
            'language': language_code,
            'translations': {
                t.key.key: t.value for t in translations
            }
        }
        return Response(data)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticatedOrReadOnly])
    def bulk_create(self, request):
        """
        Bulk create translations
        """
        data = request.data
        if not isinstance(data, list):
            return Response({"error": "Expected a list of translations"}, status=status.HTTP_400_BAD_REQUEST)
        
        created = []
        errors = []
        
        for item in data:
            serializer = self.get_serializer(data=item)
            if serializer.is_valid():
                serializer.save()
                created.append(serializer.data)
            else:
                errors.append({
                    'data': item,
                    'errors': serializer.errors
                })
        
        return Response({
            'created': created,
            'errors': errors,
            'total': len(created)
        }, status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST) 
    
    

class TranslationKeyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing translation keys
    """
    queryset = TranslationKey.objects.all()
    serializer_class = TranslationKeySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'key'  # key ফিল্ড দিয়ে lookup করা যাবে
    
    def get_queryset(self):
        """
        Filter by category if provided
        """
        queryset = TranslationKey.objects.all()
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category=category)
        return queryset
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """
        Get all keys grouped by category
        """
        categories = TranslationKey.objects.values_list('category', flat=True).distinct()
        result = {}
        for category in categories:
            if category:
                keys = TranslationKey.objects.filter(category=category).values('key', 'description')
                result[category] = keys
        return Response(result)
    
    
    
    # --- Missing Translation ViewSet ---
class MissingTranslationViewSet(viewsets.ModelViewSet):
    """
    মিসিং ট্রান্সলেশনগুলো দেখার এবং ম্যানেজ করার জন্য ভিউসেট
    """
    queryset = MissingTranslation.objects.all()
    serializer_class = MissingTranslationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['language', 'resolved']
    search_fields = ['key', 'url']
    ordering_fields = ['created_at', 'occurrence_count']
    
    # অ্যাডমিন ছাড়া কেউ যেন মিসিং ডাটা এডিট করতে না পারে
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminUser()]
        return [AllowAny()]
    
    
class TranslationCacheViewSet(viewsets.ModelViewSet):
    """
    Translation Cache ম্যানেজ করার ভিউসেট (Database-driven cache)
    """
    queryset = TranslationCache.objects.all()
    serializer_class = TranslationCacheSerializer
    permission_classes = [IsAdminUser] # শুধুমাত্র অ্যাডমিনরা এটি অ্যাক্সেস করতে পারবে
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['language_code']
    ordering_fields = ['expires_at', 'hits', 'created_at']

    def get_queryset(self):
        # ডিফল্টভাবে এক্সপায়ারড ক্যাশগুলো বাদ দিয়ে দেখাবে
        return TranslationCache.objects.filter(expires_at__gt=timezone.now())

    @action(detail=False, methods=['post'], url_path='clean-expired')
    def clean_expired(self, request):
        """ম্যানুয়ালি এক্সপায়ারড ক্যাশ ডিলিট করার জন্য এন্ডপয়েন্ট"""
        deleted_count, _ = TranslationCache.clean_expired()
        return Response({
            "message": f"Successfully deleted {deleted_count} expired cache entries.",
            "status": "success"
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='stats')
    def cache_stats(self):
        """ক্যাশ সিস্টেমের স্ট্যাটাস দেখার জন্য"""
        total = TranslationCache.objects.count()
        active = TranslationCache.objects.filter(expires_at__gt=timezone.now()).count()
        total_hits = sum(TranslationCache.objects.values_list('hits', flat=True))
        
        return Response({
            "total_entries": total,
            "active_entries": active,
            "expired_entries": total - active,
            "total_hits": total_hits
        })
        
        
        from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import Language, Translation

@api_view(['GET'])
@permission_classes([AllowAny])
def get_translations(request, language_code):
    """
    নির্দিষ্ট ল্যাঙ্গুয়েজ কোডের সব ট্রান্সলেশন ডাটা পাঠানোর জন্য।
    এটি সাধারণত ফ্রন্টেন্ডে (React/Flutter) ব্যবহারের জন্য লাগে।
    """
    try:
        # প্রথমে ভাষাটি খুঁজে বের করি
        language = Language.objects.filter(code=language_code, is_active=True).first()
        if not language:
            return Response({"error": "Language not found or inactive"}, status=404)

        # ঐ ভাষার সব ট্রান্সলেশন ডিকশনারি আকারে নিয়ে আসি
        translations = Translation.objects.filter(
            language=language, 
            is_approved=True
        ).select_related('key')

        data = {trans.key.key: trans.value for trans in translations}
        
        return Response({
            "language": language.name,
            "code": language.code,
            "translations": data
        })
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    
    
@api_view(['POST'])
@permission_classes([AllowAny])
def report_missing_translation(request):
    """
    যদি কোনো কি (key) বা ট্রান্সলেশন মিসিং থাকে, 
    তবে ফ্রন্টেন্ড এখান থেকে সেটি রিপোর্ট করতে পারবে।
    """
    try:
        from .models import MissingTranslation
        data = request.data
        
        key = data.get('key')
        language_code = data.get('language_code')
        
        if not key or not language_code:
            return Response({"error": "Key and language_code are required"}, status=400)

        # মিসিং ট্রান্সলেশন রেকর্ড তৈরি বা আপডেট করা
        obj, created = MissingTranslation.objects.get_or_create(
            key=key,
            language_code=language_code,
            defaults={
                'url': data.get('url', ''),
                'context': data.get('context', '')
            }
        )
        
        if not created:
            obj.occurrence_count += 1
            obj.save()

        return Response({"message": "Reported successfully"}, status=201)
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    
    
    
class TranslationToolsView(BulletproofView):
    """
    Language detection এবং automated translation tools-এর জন্য ভিউ।
    এটি 'detect-language' এবং 'translate-text' উভয় ইউআরএল-ই হ্যান্ডেল করবে।
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        action = request.resolver_match.url_name
        data = request.data
        text = data.get('text', '')

        if not text:
            return self.error_response("Text is required", status=400)

        if action == 'detect-language':
            # এখানে আপনার ল্যাঙ্গুয়েজ ডিটেকশন লজিক থাকবে
            return self.success_response({
                "detected_language": "en",
                "confidence": 0.98,
                "text": text
            })

        if action == 'translate-text':
            target_lang = data.get('target_lang', 'bn')
            # এখানে আপনার ট্রান্সলেশন (যেমন Google Translate API) লজিক থাকবে
            return self.success_response({
                "original_text": text,
                "translated_text": f"Translated version of: {text}",
                "target_lang": target_lang
            })

        return self.error_response("Invalid action", status=400)
    
    
class LocalizationStatusView(BulletproofView):
    """
    পুরো লোকালাইজেশন সিস্টেমের হেলথ এবং স্ট্যাটাস চেক করার জন্য ভিউ।
    এটি সক্রিয় ভাষা এবং মোট ট্রান্সলেশন কি-র সংখ্যা দেখাবে।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            active_languages = Language.objects.filter(is_active=True).count()
            total_keys = TranslationKey.objects.count()
            
            # সিস্টেমের একটি ওভারভিউ তৈরি করি
            status_data = {
                "system_status": "operational",
                "stats": {
                    "active_languages": active_languages,
                    "total_translation_keys": total_keys,
                    "cache_enabled": True,
                    "timezone": timezone.get_current_timezone_name()
                },
                "timestamp": timezone.now()
            }
            
            return self.success_response(status_data)
            
        except Exception as e:
            logger.error(f"Localization status error: {e}")
            return self.error_response("Could not fetch localization status")
        
        