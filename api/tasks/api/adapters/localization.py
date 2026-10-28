"""
api/adapters/localization.py
Localization adapter for earning backend platform
"""
import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, fields
from decimal import Decimal
from datetime import timedelta
import json

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_localization(request):
    """Get user's localization settings."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get user's localization preferences
        from localization.models import UserLocalization
        try:
            user_localization = UserLocalization.objects.get(
                user=user,
                tenant_id=tenant_id
            )
        except UserLocalization.DoesNotExist:
            # Create default localization
            user_localization = UserLocalization.objects.create(
                user=user,
                language='en',
                timezone='UTC',
                date_format='MM/DD/YYYY',
                time_format='12h',
                currency='USD',
                number_format='en-US',
                tenant_id=tenant_id,
                created_at=timezone.now()
            )
        
        # Get available languages
        available_languages = _get_available_languages(tenant_id)
        
        # Get available timezones
        available_timezones = _get_available_timezones(tenant_id)
        
        # Get available currencies
        available_currencies = _get_available_currencies(tenant_id)
        
        localization_data = {
            'user_id': user.id,
            'tenant_id': tenant_id,
            'current_settings': {
                'language': user_localization.language,
                'timezone': user_localization.timezone,
                'date_format': user_localization.date_format,
                'time_format': user_localization.time_format,
                'currency': user_localization.currency,
                'number_format': user_localization.number_format,
                'auto_detect': user_localization.auto_detect,
                'created_at': user_localization.created_at.isoformat(),
                'updated_at': user_localization.updated_at.isoformat() if user_localization.updated_at else None,
            },
            'available_options': {
                'languages': available_languages,
                'timezones': available_timezones,
                'currencies': available_currencies,
                'date_formats': _get_available_date_formats(),
                'time_formats': _get_available_time_formats(),
                'number_formats': _get_available_number_formats(),
            },
            'detected_settings': _detect_user_preferences(request),
            'recommendations': _get_localization_recommendations(user, user_localization, tenant_id)
        }
        
        return Response({
            'success': True,
            'data': localization_data,
            'message': 'User localization retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[LocalizationAdapter] Error getting user localization: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve user localization',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_user_localization(request):
    """Update user's localization settings."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Get user's localization preferences
        from localization.models import UserLocalization
        try:
            user_localization = UserLocalization.objects.get(
                user=user,
                tenant_id=tenant_id
            )
        except UserLocalization.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Localization settings not found',
                'details': 'Please set up your localization preferences first'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Update allowed fields
        if 'language' in data:
            user_localization.language = data['language']
        if 'timezone' in data:
            user_localization.timezone = data['timezone']
        if 'date_format' in data:
            user_localization.date_format = data['date_format']
        if 'time_format' in data:
            user_localization.time_format = data['time_format']
        if 'currency' in data:
            user_localization.currency = data['currency']
        if 'number_format' in data:
            user_localization.number_format = data['number_format']
        if 'auto_detect' in data:
            user_localization.auto_detect = data['auto_detect']
        
        user_localization.updated_at = timezone.now()
        user_localization.save()
        
        # Clear localization cache
        _clear_localization_cache(user, tenant_id)
        
        # Emit localization updated event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('localization.updated', {
            'user_id': user.id,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'user_id': user.id,
                'updated_settings': {
                    'language': user_localization.language,
                    'timezone': user_localization.timezone,
                    'date_format': user_localization.date_format,
                    'time_format': user_localization.time_format,
                    'currency': user_localization.currency,
                    'number_format': user_localization.number_format,
                    'auto_detect': user_localization.auto_detect,
                    'updated_at': user_localization.updated_at.isoformat()
                }
            },
            'message': 'Localization settings updated successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[LocalizationAdapter] Error updating user localization: {e}")
        return Response({
            'success': False,
            'error': 'Failed to update localization settings',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_translations(request):
    """Get translations for user's language."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        language = request.GET.get('language', 'en')
        namespace = request.GET.get('namespace', 'common')
        keys = request.GET.getlist('keys', [])
        
        # Get user's language preference
        if language == 'auto':
            from localization.models import UserLocalization
            try:
                user_localization = UserLocalization.objects.get(
                    user=user,
                    tenant_id=tenant_id
                )
                language = user_localization.language
            except UserLocalization.DoesNotExist:
                language = 'en'
        
        # Get translations
        from localization.models import Translation
        queryset = Translation.objects.filter(
            tenant_id=tenant_id,
            language=language,
            namespace=namespace
        )
        
        if keys:
            queryset = queryset.filter(key__in=keys)
        
        # Serialize translations
        translations = {}
        for translation in queryset:
            translations[translation.key] = translation.value
        
        return Response({
            'success': True,
            'data': {
                'language': language,
                'namespace': namespace,
                'translations': translations,
                'total_keys': len(translations),
                'requested_keys': keys,
                'cache_info': {
                    'cached': _is_translation_cached(language, namespace, tenant_id),
                    'cache_key': _get_translation_cache_key(language, namespace, tenant_id),
                    'expires_at': _get_translation_cache_expiry(language, namespace, tenant_id)
                }
            },
            'message': 'Translations retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[LocalizationAdapter] Error getting translations: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve translations',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_supported_languages(request):
    """Get supported languages."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        include_translations = request.GET.get('include_translations', 'false').lower() == 'true'
        
        # Get supported languages
        languages = _get_available_languages(tenant_id)
        
        # Include translations if requested
        if include_translations:
            for language in languages:
                language['translations'] = _get_language_translations(language['code'], tenant_id)
        
        return Response({
            'success': True,
            'data': {
                'languages': languages,
                'total_languages': len(languages),
                'default_language': _get_default_language(tenant_id),
                'include_translations': include_translations
            },
            'message': 'Supported languages retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[LocalizationAdapter] Error getting supported languages: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve supported languages',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_currency_rates(request):
    """Get currency exchange rates."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        base_currency = request.GET.get('base_currency', 'USD')
        target_currencies = request.GET.getlist('target_currencies', [])
        
        # Get user's currency preference
        if base_currency == 'user':
            from localization.models import UserLocalization
            try:
                user_localization = UserLocalization.objects.get(
                    user=user,
                    tenant_id=tenant_id
                )
                base_currency = user_localization.currency
            except UserLocalization.DoesNotExist:
                base_currency = 'USD'
        
        # Get currency rates
        rates = _get_currency_rates(base_currency, target_currencies, tenant_id)
        
        return Response({
            'success': True,
            'data': {
                'base_currency': base_currency,
                'rates': rates,
                'last_updated': _get_rates_last_updated(tenant_id),
                'cache_info': {
                    'cached': _is_rates_cached(tenant_id),
                    'cache_key': _get_rates_cache_key(base_currency, tenant_id),
                    'expires_at': _get_rates_cache_expiry(tenant_id)
                }
            },
            'message': 'Currency rates retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[LocalizationAdapter] Error getting currency rates: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve currency rates',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_localization_analytics(request):
    """Get localization analytics for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get localization analytics
        from localization.models import UserLocalization, Translation
        localizations = UserLocalization.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        ).select_related('user')
        
        translations = Translation.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        )
        
        # Calculate analytics
        analytics_data = {
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'user_preferences': {
                'total_users': localizations.count(),
                'language_distribution': list(localizations.values('language').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'timezone_distribution': list(localizations.values('timezone').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'currency_distribution': list(localizations.values('currency').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'date_format_distribution': list(localizations.values('date_format').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'time_format_distribution': list(localizations.values('time_format').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'auto_detect_usage': localizations.filter(auto_detect=True).count(),
                'recent_changes': localizations.filter(
                    updated_at__gte=timezone.now() - timedelta(days=7)
                ).count()
            },
            'translation_metrics': {
                'total_translations': translations.count(),
                'languages': list(translations.values('language').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'namespaces': list(translations.values('namespace').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'translation_keys': translations.values('key').distinct().count(),
                'average_length': translations.aggregate(
                    avg_length=Avg(F('length'))
                )['avg_length'] or 0,
                'total_characters': translations.aggregate(
                    total=Sum(F('length'))
                )['total'] or 0,
                'daily_trends': _get_translation_trends(translations, days),
                'most_translated_keys': list(translations.values('key').annotate(
                    translation_count=Count('id')
                ).order_by('-translation_count')[:10])
            },
            'usage_metrics': {
                'translation_cache_hits': _get_translation_cache_hits(tenant_id),
                'translation_cache_misses': _get_translation_cache_misses(tenant_id),
                'cache_hit_rate': _get_translation_cache_hit_rate(tenant_id),
                'most_accessed_languages': _get_most_accessed_languages(tenant_id),
                'translation_requests_per_day': _get_translation_requests_per_day(tenant_id, days)
            },
            'performance_metrics': {
                'average_translation_load_time_ms': _get_average_translation_load_time(tenant_id),
                'translation_cache_performance': _get_translation_cache_performance(tenant_id),
                'database_query_time_ms': _get_database_query_time(tenant_id),
                'memory_usage_mb': _get_localization_memory_usage(tenant_id)
            }
        }
        
        return Response({
            'success': True,
            'data': analytics_data,
            'message': 'Localization analytics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[LocalizationAdapter] Error getting localization analytics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve localization analytics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def upload_translation_file(request):
    """Upload translation file."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        required_fields = ['language', 'namespace', 'translations']
        for field in required_fields:
            if field not in data:
                return Response({
                    'success': False,
                    'error': 'Missing required field',
                    'details': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Process translation file
        translations = data['translations']
        language = data['language']
        namespace = data['namespace']
        
        # Validate language
        if not _is_valid_language(language, tenant_id):
            return Response({
                'success': False,
                'error': 'Invalid language',
                'details': f'{language} is not a supported language'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create or update translations
        from localization.models import Translation
        created_count = 0
        updated_count = 0
        
        for key, value in translations.items():
            try:
                translation = Translation.objects.get(
                    tenant_id=tenant_id,
                    language=language,
                    namespace=namespace,
                    key=key
                )
                translation.value = value
                translation.updated_at = timezone.now()
                translation.save()
                updated_count += 1
            except Translation.DoesNotExist:
                Translation.objects.create(
                    tenant_id=tenant_id,
                    language=language,
                    namespace=namespace,
                    key=key,
                    value=value,
                    length=len(str(value)),
                    created_at=timezone.now()
                )
                created_count += 1
        
        # Clear translation cache
        _clear_translation_cache(language, namespace, tenant_id)
        
        # Emit translation uploaded event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('localization.translations_uploaded', {
            'user_id': user.id,
            'language': language,
            'namespace': namespace,
            'created_count': created_count,
            'updated_count': updated_count,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'language': language,
                'namespace': namespace,
                'created_count': created_count,
                'updated_count': updated_count,
                'total_translations': created_count + updated_count,
                'uploaded_at': timezone.now().isoformat()
            },
            'message': 'Translation file uploaded successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[LocalizationAdapter] Error uploading translation file: {e}")
        return Response({
            'success': False,
            'error': 'Failed to upload translation file',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper functions
def _get_available_languages(tenant_id) -> List[Dict]:
    """Get available languages."""
    try:
        from localization.models import Language
        languages = Language.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        ).order_by('sort_order', 'name')
        
        return [
            {
                'code': lang.code,
                'name': lang.name,
                'native_name': lang.native_name,
                'direction': lang.direction,
                'is_rtl': lang.direction == 'rtl',
                'flag': lang.flag,
                'is_default': lang.is_default,
                'sort_order': lang.sort_order
            }
            for lang in languages
        ]
    except Exception:
        return [
            {
                'code': 'en',
                'name': 'English',
                'native_name': 'English',
                'direction': 'ltr',
                'is_rtl': False,
                'flag': '🇺🇸',
                'is_default': True,
                'sort_order': 1
            }
        ]


def _get_available_timezones(tenant_id) -> List[Dict]:
    """Get available timezones."""
    try:
        from localization.models import Timezone
        timezones = Timezone.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        ).order_by('name')
        
        return [
            {
                'code': tz.code,
                'name': tz.name,
                'offset': tz.utc_offset,
                'country': tz.country,
                'is_default': tz.is_default
            }
            for tz in timezones
        ]
    except Exception:
        # Return common timezones
        return [
            {'code': 'UTC', 'name': 'UTC', 'offset': '+00:00', 'country': 'International', 'is_default': True},
            {'code': 'EST', 'name': 'Eastern Time', 'offset': '-05:00', 'country': 'US', 'is_default': False},
            {'code': 'PST', 'name': 'Pacific Time', 'offset': '-08:00', 'country': 'US', 'is_default': False},
            {'code': 'CET', 'name': 'Central European Time', 'offset': '+01:00', 'country': 'EU', 'is_default': False},
            {'code': 'JST', 'name': 'Japan Standard Time', 'offset': '+09:00', 'country': 'Japan', 'is_default': False}
        ]


def _get_available_currencies(tenant_id) -> List[Dict]:
    """Get available currencies."""
    try:
        from localization.models import Currency
        currencies = Currency.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        ).order_by('name')
        
        return [
            {
                'code': currency.code,
                'name': currency.name,
                'symbol': currency.symbol,
                'decimal_places': currency.decimal_places,
                'is_default': currency.is_default
            }
            for currency in currencies
        ]
    except Exception:
        # Return common currencies
        return [
            {'code': 'USD', 'name': 'US Dollar', 'symbol': '$', 'decimal_places': 2, 'is_default': True},
            {'code': 'EUR', 'name': 'Euro', 'symbol': '€', 'decimal_places': 2, 'is_default': False},
            {'code': 'GBP', 'name': 'British Pound', 'symbol': '£', 'decimal_places': 2, 'is_default': False},
            {'code': 'JPY', 'name': 'Japanese Yen', 'symbol': '¥', 'decimal_places': 0, 'is_default': False},
            {'code': 'CNY', 'name': 'Chinese Yuan', 'symbol': '¥', 'decimal_places': 2, 'is_default': False}
        ]


def _get_available_date_formats() -> List[Dict]:
    """Get available date formats."""
    return [
        {'code': 'MM/DD/YYYY', 'name': 'Month/Day/Year', 'example': '12/31/2023'},
        {'code': 'DD/MM/YYYY', 'name': 'Day/Month/Year', 'example': '31/12/2023'},
        {'code': 'YYYY-MM-DD', 'name': 'Year-Month-Day', 'example': '2023-12-31'},
        {'code': 'DD.MM.YYYY', 'name': 'Day.Month.Year', 'example': '31.12.2023'},
        {'code': 'DD MMM YYYY', 'name': 'Day Month Year', 'example': '31 Dec 2023'},
        {'code': 'MMM DD, YYYY', 'name': 'Month Day, Year', 'example': 'Dec 31, 2023'}
    ]


def _get_available_time_formats() -> List[Dict]:
    """Get available time formats."""
    return [
        {'code': '12h', 'name': '12-hour', 'example': '2:30 PM'},
        {'code': '24h', 'name': '24-hour', 'example': '14:30'},
        {'code': '12h:am', 'name': '12-hour with AM/PM', 'example': '2:30:00 PM'},
        {'code': '24h:seconds', 'name': '24-hour with seconds', 'example': '14:30:00'}
    ]


def _get_available_number_formats() -> List[Dict]:
    """Get available number formats."""
    return [
        {'code': 'en-US', 'name': 'English (United States)', 'example': '1,234.56'},
        {'code': 'en-GB', 'name': 'English (United Kingdom)', 'example': '1,234.56'},
        {'code': 'de-DE', 'name': 'German (Germany)', 'example': '1.234,56'},
        {'code': 'fr-FR', 'name': 'French (France)', 'example': '1 234,56'},
        {'code': 'ja-JP', 'name': 'Japanese (Japan)', 'example': '1,234.56'},
        {'code': 'zh-CN', 'name': 'Chinese (China)', 'example': '1,234.56'}
    ]


def _detect_user_preferences(request) -> Dict:
    """Detect user preferences from request."""
    try:
        preferences = {}
        
        # Detect language from Accept-Language header
        accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        if accept_language:
            preferences['detected_language'] = accept_language.split(',')[0].split('-')[0]
        
        # Detect timezone from IP (simplified)
        ip_address = _get_client_ip(request)
        if ip_address:
            preferences['detected_timezone'] = _detect_timezone_from_ip(ip_address)
        
        # Detect currency from IP (simplified)
        if ip_address:
            preferences['detected_currency'] = _detect_currency_from_ip(ip_address)
        
        return preferences
    except Exception:
        return {}


def _get_localization_recommendations(user, user_localization, tenant_id) -> List[str]:
    """Get localization recommendations."""
    recommendations = []
    
    # Check if user has default settings
    if user_localization.language == 'en' and user_localization.timezone == 'UTC':
        recommendations.append('Consider setting your preferred language and timezone')
    
    # Check if auto-detect is disabled
    if not user_localization.auto_detect:
        recommendations.append('Enable auto-detection for better experience')
    
    # Check currency based on location
    detected_currency = _detect_currency_from_user(user, tenant_id)
    if detected_currency and detected_currency != user_localization.currency:
        recommendations.append(f'Consider using {detected_currency} as your currency')
    
    return recommendations


def _get_language_translations(language, tenant_id) -> Dict:
    """Get translations for a language."""
    try:
        from localization.models import Translation
        translations = Translation.objects.filter(
            tenant_id=tenant_id,
            language=language
        )
        
        result = {}
        for translation in translations:
            result[translation.key] = translation.value
        
        return result
    except Exception:
        return {}


def _get_currency_rates(base_currency, target_currencies, tenant_id) -> Dict:
    """Get currency exchange rates."""
    try:
        # In real implementation, this would call an exchange rate API
        # For now, return mock data
        rates = {}
        
        if not target_currencies:
            target_currencies = ['EUR', 'GBP', 'JPY', 'CNY']
        
        # Mock exchange rates
        mock_rates = {
            'USD': {'EUR': 0.85, 'GBP': 0.73, 'JPY': 110.5, 'CNY': 6.9},
            'EUR': {'USD': 1.18, 'GBP': 0.86, 'JPY': 130.2, 'CNY': 8.1},
            'GBP': {'USD': 1.37, 'EUR': 1.16, 'JPY': 151.3, 'CNY': 9.4},
            'JPY': {'USD': 0.0091, 'EUR': 0.0077, 'GBP': 0.0066, 'CNY': 0.062},
            'CNY': {'USD': 0.145, 'EUR': 0.123, 'GBP': 0.106, 'JPY': 16.1}
        }
        
        base_rates = mock_rates.get(base_currency, mock_rates['USD'])
        
        for currency in target_currencies:
            if currency in base_rates:
                rates[currency] = base_rates[currency]
        
        return rates
    except Exception:
        return {}


def _get_rates_last_updated(tenant_id) -> str:
    """Get last updated time for rates."""
    try:
        from localization.models import CurrencyRate
        last_update = CurrencyRate.objects.filter(
            tenant_id=tenant_id
        ).order_by('-updated_at').first()
        
        return last_update.updated_at.isoformat() if last_update else timezone.now().isoformat()
    except Exception:
        return timezone.now().isoformat()


def _is_rates_cached(tenant_id) -> bool:
    """Check if rates are cached."""
    try:
        cache_key = f'currency_rates_{tenant_id}'
        return cache.get(cache_key) is not None
    except Exception:
        return False


def _get_rates_cache_key(base_currency, tenant_id) -> str:
    """Get cache key for rates."""
    return f'currency_rates_{tenant_id}_{base_currency}'


def _get_rates_cache_expiry(tenant_id) -> str:
    """Get cache expiry time for rates."""
    return (timezone.now() + timedelta(hours=1)).isoformat()


def _is_translation_cached(language, namespace, tenant_id) -> bool:
    """Check if translations are cached."""
    try:
        cache_key = _get_translation_cache_key(language, namespace, tenant_id)
        return cache.get(cache_key) is not None
    except Exception:
        return False


def _get_translation_cache_key(language, namespace, tenant_id) -> str:
    """Get cache key for translations."""
    return f'translations_{tenant_id}_{language}_{namespace}'


def _get_translation_cache_expiry(language, namespace, tenant_id) -> str:
    """Get cache expiry time for translations."""
    return (timezone.now() + timedelta(hours=24)).isoformat()


def _clear_localization_cache(user, tenant_id):
    """Clear localization cache for user."""
    try:
        cache_keys = [
            f'user_localization_{user.id}',
            f'translations_*_{tenant_id}',
            f'currency_rates_{tenant_id}'
        ]
        
        for key in cache_keys:
            cache.delete(key)
    except Exception:
        pass


def _clear_translation_cache(language, namespace, tenant_id):
    """Clear translation cache."""
    try:
        cache_key = _get_translation_cache_key(language, namespace, tenant_id)
        cache.delete(cache_key)
    except Exception:
        pass


def _is_valid_language(language, tenant_id) -> bool:
    """Check if language is valid."""
    try:
        from localization.models import Language
        return Language.objects.filter(
            tenant_id=tenant_id,
            code=language,
            is_active=True
        ).exists()
    except Exception:
        return language in ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'zh', 'ko', 'ar']


def _get_default_language(tenant_id) -> str:
    """Get default language for tenant."""
    try:
        from localization.models import Language
        default_lang = Language.objects.filter(
            tenant_id=tenant_id,
            is_default=True,
            is_active=True
        ).first()
        
        return default_lang.code if default_lang else 'en'
    except Exception:
        return 'en'


def _get_translation_trends(translations, days) -> List[Dict]:
    """Get translation trends."""
    try:
        from django.db.models import TruncDay
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_trends = translations.filter(
            created_at__gte=start_date
        ).extra({
            'day': TruncDay('created_at')
        }).values('day').annotate(
            count=Count('id'),
            languages=Count('language', distinct=True)
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'translations_added': trend['count'],
                'active_languages': trend['languages']
            }
            for trend in daily_trends
        ]
    except Exception:
        return []


def _get_translation_cache_hits(tenant_id) -> int:
    """Get translation cache hits."""
    try:
        # In real implementation, this would track cache hits
        return 12500
    except Exception:
        return 0


def _get_translation_cache_misses(tenant_id) -> int:
    """Get translation cache misses."""
    try:
        # In real implementation, this would track cache misses
        return 1250
    except Exception:
        return 0


def _get_translation_cache_hit_rate(tenant_id) -> float:
    """Get translation cache hit rate."""
    try:
        hits = _get_translation_cache_hits(tenant_id)
        misses = _get_translation_cache_misses(tenant_id)
        total = hits + misses
        
        return round((hits / max(total, 1)) * 100, 2)
    except Exception:
        return 0


def _get_most_accessed_languages(tenant_id) -> List[Dict]:
    """Get most accessed languages."""
    try:
        # In real implementation, this would track language access
        return [
            {'language': 'en', 'access_count': 5000},
            {'language': 'es', 'access_count': 2500},
            {'language': 'fr', 'access_count': 1800},
            {'language': 'de', 'access_count': 1200},
            {'language': 'zh', 'access_count': 800}
        ]
    except Exception:
        return []


def _get_translation_requests_per_day(tenant_id, days) -> float:
    """Get translation requests per day."""
    try:
        # In real implementation, this would track requests
        return 1500.5
    except Exception:
        return 0


def _get_average_translation_load_time(tenant_id) -> float:
    """Get average translation load time."""
    try:
        # In real implementation, this would track load time
        return 15.7
    except Exception:
        return 0


def _get_translation_cache_performance(tenant_id) -> Dict:
    """Get translation cache performance."""
    try:
        return {
            'hit_rate': _get_translation_cache_hit_rate(tenant_id),
            'average_response_time_ms': _get_average_translation_load_time(tenant_id),
            'cache_size_mb': 25.6,
            'memory_efficiency': 85.2
        }
    except Exception:
        return {}


def _get_database_query_time(tenant_id) -> float:
    """Get database query time for translations."""
    try:
        # In real implementation, this would track query time
        return 8.3
    except Exception:
        return 0


def _get_localization_memory_usage(tenant_id) -> float:
    """Get memory usage for localization."""
    try:
        # In real implementation, this would track memory usage
        return 45.2
    except Exception:
        return 0


def _get_client_ip(request) -> str:
    """Get client IP address."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip
    
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


def _detect_timezone_from_ip(ip_address) -> str:
    """Detect timezone from IP address."""
    try:
        # In real implementation, this would use a geoip service
        # For now, return timezone based on common IP ranges
        if ip_address.startswith('192.168.') or ip_address.startswith('10.'):
            return 'UTC'
        elif ip_address.startswith('8.8.8'):
            return 'PST'
        elif ip_address.startswith('208.67'):
            return 'EST'
        else:
            return 'UTC'
    except Exception:
        return 'UTC'


def _detect_currency_from_ip(ip_address) -> str:
    """Detect currency from IP address."""
    try:
        # In real implementation, this would use a geoip service
        # For now, return currency based on common IP ranges
        if ip_address.startswith('192.168.') or ip_address.startswith('10.'):
            return 'USD'
        elif ip_address.startswith('8.8.8'):
            return 'USD'
        elif ip_address.startswith('208.67'):
            return 'USD'
        elif ip_address.startswith('82.'):
            return 'EUR'
        elif ip_address.startswith('203.'):
            return 'CNY'
        else:
            return 'USD'
    except Exception:
        return 'USD'


def _detect_currency_from_user(user, tenant_id) -> str:
    """Detect currency from user profile."""
    try:
        # In real implementation, this would analyze user behavior
        # For now, return default
        return 'USD'
    except Exception:
        return 'USD'
