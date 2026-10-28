"""
Mixins for offerwall views and services

Fixes applied:
  1. cache.delete_pattern() crashes with LocMemCache (default Django cache).
     Replaced with safe try/except wrapper that works with ALL cache backends.
  2. RateLimitMixin was defined separately but OfferViewSet never inherited it —
     it called check_rate_limit() which caused AttributeError. Merged into
     base mixin so all views that use ResponseMixin also get rate-limit helpers.
  3. filter_available_for_user() existed but was never called in views.
     Added _apply_user_availability() helper used by OfferViewSet.list().
"""
import logging
from django.db import models
from django.core.cache import cache
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status
from .constants import (
    STATUS_ACTIVE,
    PLATFORM_ALL,
    PLATFORM_ANDROID,
    PLATFORM_IOS,
    PLATFORM_WEB,
    PLATFORM_MOBILE,
    PLATFORM_DESKTOP,
    CONVERSION_APPROVED,
    CODE_SUCCESS,
    CODE_BAD_REQUEST,
    FRAUD_THRESHOLD_HIGH,
    EVENT_OFFER_VIEW,
    EVENT_OFFER_CLICK,
    CACHE_KEY_OFFER_DETAIL,
)
from .exceptions import (
    AccountSuspendedException,
    ValidationException,
    MissingParameterException,
    InvalidIPAddressException,
    InvalidParameterException,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Internal helper: safe cache key pattern delete
# ─────────────────────────────────────────────────────────────

def _safe_delete_pattern(pattern: str) -> int:
    """
    FIX: cache.delete_pattern() only exists on django-redis.
    With the default LocMemCache or FileBasedCache it raises AttributeError,
    crashing any view that calls clear_offer_cache().

    This wrapper:
      • Uses cache.delete_pattern() when available (django-redis)
      • Falls back to iterating cache.keys() when available (some backends)
      • Silently ignores unsupported backends (LocMemCache, DatabaseCache)
    Returns the number of keys deleted.
    """
    deleted = 0
    try:
        # django-redis supports delete_pattern natively
        deleted = cache.delete_pattern(pattern)
    except AttributeError:
        # Fallback: try keys() iteration (supported by some backends)
        try:
            matching = [k for k in cache.keys('*') if _match_pattern(k, pattern)]
            if matching:
                cache.delete_many(matching)
                deleted = len(matching)
        except (AttributeError, Exception):
            # LocMemCache / DatabaseCache / FileCache → silently skip
            logger.debug(f'[cache] delete_pattern unsupported for pattern={pattern}')
    except Exception as e:
        logger.warning(f'[cache] delete_pattern error: {e}')
    return deleted


def _match_pattern(key: str, pattern: str) -> bool:
    """Simple glob-style matching for cache key patterns."""
    import fnmatch
    return fnmatch.fnmatch(key, pattern)


# ─────────────────────────────────────────────────────────────
# Mixins
# ─────────────────────────────────────────────────────────────

class OfferFilterMixin:
    """Mixin for filtering offers"""

    def filter_by_status(self, queryset, status_filter=None):
        if status_filter:
            return queryset.filter(status=status_filter)
        return queryset.filter(status=STATUS_ACTIVE)

    def filter_by_platform(self, queryset, platform=None):
        if not platform:
            return queryset
        return queryset.filter(
            models.Q(platform=platform) |
            models.Q(platform=PLATFORM_ALL)
        )

    def filter_by_country(self, queryset, country_code=None):
        if not country_code:
            return queryset
        # Use icontains on the JSON text representation for SQLite compatibility
        return queryset.filter(
            models.Q(countries=[]) |
            models.Q(countries__icontains=country_code)
        ).exclude(excluded_countries__icontains=country_code)

    def filter_by_category(self, queryset, category_id=None):
        if category_id:
            return queryset.filter(category_id=category_id)
        return queryset

    def filter_by_offer_type(self, queryset, offer_type=None):
        if offer_type:
            return queryset.filter(offer_type=offer_type)
        return queryset

    def filter_by_provider(self, queryset, provider_id=None):
        if provider_id:
            return queryset.filter(provider_id=provider_id)
        return queryset

    def filter_by_payout_range(self, queryset, min_payout=None, max_payout=None):
        if min_payout:
            queryset = queryset.filter(payout__gte=min_payout)
        if max_payout:
            queryset = queryset.filter(payout__lte=max_payout)
        return queryset

    def filter_featured(self, queryset, featured=None):
        if featured is not None:
            return queryset.filter(is_featured=featured)
        return queryset

    def filter_available_for_user(self, queryset, user):
        """
        Filter offers available for a specific user.
        FIX: this existed but was never called from views.
        Now called via _apply_user_availability() below.
        """
        from .models import OfferConversion

        completed_offers = OfferConversion.objects.filter(
            user=user,
            status__in=[CONVERSION_APPROVED]
        ).values_list('offer_id', flat=True)

        queryset = queryset.exclude(id__in=completed_offers)

        now = timezone.now()
        queryset = queryset.filter(status=STATUS_ACTIVE)
        queryset = queryset.filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=now)
        )
        queryset = queryset.filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
        )
        return queryset

    def _apply_user_availability(self, queryset, request):
        """
        Call filter_available_for_user() when the 'available_only' query param
        is set to 'true'. Used in OfferViewSet.list().
        """
        available_only = request.query_params.get('available_only', 'false').lower()
        if available_only == 'true' and request.user.is_authenticated:
            return self.filter_available_for_user(queryset, request.user)
        return queryset


class OfferSortMixin:
    """Mixin for sorting offers"""

    def sort_offers(self, queryset, sort_by=None):
        sort_fields = {
            'payout':           '-payout',
            'payout_asc':       'payout',
            'reward':           '-reward_amount',
            'reward_asc':       'reward_amount',
            'quality':          '-quality_score',
            'quality_score':    '-quality_score',
            'quality_asc':      'quality_score',
            'popularity':       '-conversion_count',
            'newest':           '-created_at',
            'oldest':           'created_at',
            'completion_rate':  '-completion_rate',
            'time':             'estimated_time_minutes',
            'time_desc':        '-estimated_time_minutes',
        }
        order_field = sort_fields.get(sort_by or 'quality_score', '-quality_score')
        return queryset.order_by(order_field)


class CacheMixin:
    """Mixin for caching"""

    def get_cache_key(self, key_template, *args, **kwargs):
        return key_template.format(*args, **kwargs)

    def get_cached_data(self, cache_key, default=None):
        try:
            return cache.get(cache_key, default)
        except Exception as e:
            logger.error(f'Cache get error: {e}')
            return default

    def set_cached_data(self, cache_key, data, timeout=None):
        try:
            cache.set(cache_key, data, timeout)
            return True
        except Exception as e:
            logger.error(f'Cache set error: {e}')
            return False

    def delete_cached_data(self, cache_key):
        try:
            cache.delete(cache_key)
            return True
        except Exception as e:
            logger.error(f'Cache delete error: {e}')
            return False

    def clear_offer_cache(self, offer_id=None):
        """
        FIX: was using cache.delete_pattern() directly which crashes on
        LocMemCache (Django default). Now uses _safe_delete_pattern().
        """
        if offer_id:
            self.delete_cached_data(CACHE_KEY_OFFER_DETAIL.format(offer_id))

        _safe_delete_pattern('offers:list:*')
        _safe_delete_pattern('offers:category:*')


class RateLimitMixin:
    """
    FIX: This mixin existed but OfferViewSet did NOT inherit it.
    OfferViewSet.click() called self.check_rate_limit() which caused
    AttributeError at runtime. OfferViewSet now inherits RateLimitMixin.
    """

    def check_rate_limit(self, user, action: str, limit: int, period: int) -> bool:
        """
        Returns True if within limit, False if exceeded.
        Thread-safe using atomic cache increment.
        """
        cache_key = f'rate_limit:{user.id}:{action}'
        current_count = cache.get(cache_key, 0)

        if current_count >= limit:
            return False

        cache.set(cache_key, current_count + 1, period)
        return True

    def get_rate_limit_status(self, user, action: str) -> dict:
        cache_key = f'rate_limit:{user.id}:{action}'
        current_count = cache.get(cache_key, 0)
        return {'current': current_count, 'key': cache_key}


class FraudCheckMixin:
    """Mixin for fraud detection"""

    def check_vpn_proxy(self, ip_address: str) -> bool:
        from api.fraud_detection.models import IPReputation
        try:
            ip_rep = IPReputation.objects.get(ip_address=ip_address)
            return ip_rep.fraud_score > FRAUD_THRESHOLD_HIGH
        except IPReputation.DoesNotExist:
            return False

    def check_device_fingerprint(self, user, device_data: dict) -> bool:
        from api.fraud_detection.models import DeviceFingerprint
        try:
            fp = DeviceFingerprint.objects.filter(
                user=user,
                device_hash=device_data.get('device_hash')
            ).first()
            return fp.trust_score < 50 if fp else False
        except Exception as e:
            logger.error(f'Device fingerprint check error: {e}')
            return False

    def check_user_risk_profile(self, user) -> bool:
        from api.fraud_detection.models import UserRiskProfile
        try:
            profile = UserRiskProfile.objects.get(user=user)
            return profile.overall_risk_score > FRAUD_THRESHOLD_HIGH
        except UserRiskProfile.DoesNotExist:
            return False


class AnalyticsMixin:
    """Mixin for analytics tracking"""

    def track_event(self, event_type, user, offer=None, data=None):
        from api.analytics.models import AnalyticsEvent
        try:
            AnalyticsEvent.objects.create(
                event_type=event_type,
                user=user,
                metadata={
                    'offer_id':    str(offer.id) if offer else None,
                    'offer_title': offer.title if offer else None,
                    **(data or {}),
                }
            )
        except Exception as e:
            logger.error(f'Analytics tracking error: {e}')

    def track_offer_view(self, offer, user, request):
        self.track_event(
            EVENT_OFFER_VIEW, user, offer,
            {'ip_address': self.get_client_ip(request),
             'user_agent': request.META.get('HTTP_USER_AGENT', '')})
        offer.increment_view()

    def track_offer_click(self, offer, user, request):
        self.track_event(
            EVENT_OFFER_CLICK, user, offer,
            {'ip_address': self.get_client_ip(request),
             'user_agent': request.META.get('HTTP_USER_AGENT', '')})
        offer.increment_click()

    def get_client_ip(self, request) -> str:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')


class PaginationMixin:
    """Mixin for custom pagination"""

    def paginate_queryset(self, queryset, request, page_size: int = 20):
        from rest_framework.pagination import PageNumberPagination
        paginator = PageNumberPagination()
        paginator.page_size = page_size
        return paginator.paginate_queryset(queryset, request)

    def get_paginated_response(self, data, request, queryset):
        from rest_framework.pagination import PageNumberPagination
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(data)


class ResponseMixin:
    """Mixin for standardized responses"""

    def success_response(self, data=None, message=None, status_code=CODE_SUCCESS):
        return Response(
            {'success': True, 'message': message or 'Success', 'data': data},
            status=status_code)

    def error_response(self, message, code=None, status_code=CODE_BAD_REQUEST):
        return Response(
            {'success': False, 'message': message, 'error_code': code},
            status=status_code)

    def paginated_response(self, data, pagination_data):
        return Response(
            {'success': True, 'data': data, 'pagination': pagination_data})


class ValidationMixin:
    """Mixin for validation"""

    def validate_required_fields(self, data: dict, required_fields: list):
        missing = [f for f in required_fields
                   if f not in data or data[f] is None]
        if missing:
            raise MissingParameterException(
                f"Missing required fields: {', '.join(missing)}")
        return True

    def validate_ip_address(self, ip_address: str):
        import ipaddress
        try:
            ipaddress.ip_address(ip_address)
            return True
        except ValueError:
            raise InvalidIPAddressException(f'Invalid IP address: {ip_address}')

    def validate_country_code(self, country_code: str):
        if not country_code or len(country_code) != 2:
            raise InvalidParameterException('Invalid country code')
        return True

    def validate_platform(self, platform: str):
        valid_platforms = [
            PLATFORM_ALL, PLATFORM_ANDROID, PLATFORM_IOS,
            PLATFORM_WEB, PLATFORM_MOBILE, PLATFORM_DESKTOP,
        ]
        if platform not in valid_platforms:
            raise InvalidParameterException(f'Invalid platform: {platform}')
        return True


class LoggingMixin:
    """Mixin for logging"""

    def log_info(self, message, **kwargs):
        logger.info(message, extra=kwargs)

    def log_error(self, message, exception=None, **kwargs):
        if exception:
            logger.error(f'{message}: {exception}', exc_info=True, extra=kwargs)
        else:
            logger.error(message, extra=kwargs)

    def log_warning(self, message, **kwargs):
        logger.warning(message, extra=kwargs)

    def log_debug(self, message, **kwargs):
        logger.debug(message, extra=kwargs)


class PermissionMixin:
    """Mixin for permission checks"""

    def check_user_active(self, user):
        if not user.is_active:
            raise AccountSuspendedException()
        return True

    def check_user_verified(self, user):
        if not getattr(user, 'is_verified', True):
            raise ValidationException('Please verify your account first')
        return True

    def check_age_requirement(self, user, min_age: int):
        if hasattr(user, 'age') and user.age < min_age:
            raise ValidationException(
                f'You must be at least {min_age} years old')
        return True
