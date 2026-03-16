"""
Mixins for offerwall views and services
"""
import logging
from django.core.cache import cache
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status
from .constants import *
from .exceptions import *

logger = logging.getLogger(__name__)


class OfferFilterMixin:
    """Mixin for filtering offers"""
    
    def filter_by_status(self, queryset, status_filter=None):
        """Filter offers by status"""
        if status_filter:
            return queryset.filter(status=status_filter)
        return queryset.filter(status=STATUS_ACTIVE)
    
    def filter_by_platform(self, queryset, platform=None):
        """Filter offers by platform"""
        if not platform:
            return queryset
        
        return queryset.filter(
            models.Q(platform=platform) |
            models.Q(platform=PLATFORM_ALL)
        )
    
    def filter_by_country(self, queryset, country_code=None):
        """Filter offers by country"""
        if not country_code:
            return queryset
        
        from django.contrib.postgres.fields import ArrayField
        from django.db import models
        
        return queryset.filter(
            models.Q(countries__contains=[country_code]) |
            models.Q(countries=[])
        ).exclude(excluded_countries__contains=[country_code])
    
    def filter_by_category(self, queryset, category_id=None):
        """Filter offers by category"""
        if category_id:
            return queryset.filter(category_id=category_id)
        return queryset
    
    def filter_by_offer_type(self, queryset, offer_type=None):
        """Filter offers by type"""
        if offer_type:
            return queryset.filter(offer_type=offer_type)
        return queryset
    
    def filter_by_provider(self, queryset, provider_id=None):
        """Filter offers by provider"""
        if provider_id:
            return queryset.filter(provider_id=provider_id)
        return queryset
    
    def filter_by_payout_range(self, queryset, min_payout=None, max_payout=None):
        """Filter offers by payout range"""
        if min_payout:
            queryset = queryset.filter(payout__gte=min_payout)
        if max_payout:
            queryset = queryset.filter(payout__lte=max_payout)
        return queryset
    
    def filter_featured(self, queryset, featured=None):
        """Filter featured offers"""
        if featured is not None:
            return queryset.filter(is_featured=featured)
        return queryset
    
    def filter_available_for_user(self, queryset, user):
        """Filter offers available for specific user"""
        # Exclude offers user has completed
        from .models import OfferConversion
        
        completed_offers = OfferConversion.objects.filter(
            user=user,
            status__in=[CONVERSION_APPROVED]
        ).values_list('offer_id', flat=True)
        
        queryset = queryset.exclude(id__in=completed_offers)
        
        # Filter by active status and valid dates
        now = timezone.now()
        queryset = queryset.filter(status=STATUS_ACTIVE)
        queryset = queryset.filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=now)
        )
        queryset = queryset.filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
        )
        
        return queryset


class OfferSortMixin:
    """Mixin for sorting offers"""
    
    def sort_offers(self, queryset, sort_by=None):
        """Sort offers by specified field"""
        if not sort_by:
            sort_by = 'quality_score'
        
        sort_fields = {
            'payout': '-payout',
            'payout_asc': 'payout',
            'reward': '-reward_amount',
            'reward_asc': 'reward_amount',
            'quality': '-quality_score',
            'quality_asc': 'quality_score',
            'popularity': '-conversion_count',
            'newest': '-created_at',
            'oldest': 'created_at',
            'completion_rate': '-completion_rate',
            'time': 'estimated_time_minutes',
            'time_desc': '-estimated_time_minutes',
        }
        
        order_field = sort_fields.get(sort_by, '-quality_score')
        return queryset.order_by(order_field)


class CacheMixin:
    """Mixin for caching"""
    
    def get_cache_key(self, key_template, *args, **kwargs):
        """Generate cache key"""
        return key_template.format(*args, **kwargs)
    
    def get_cached_data(self, cache_key, default=None):
        """Get data from cache"""
        try:
            return cache.get(cache_key, default)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return default
    
    def set_cached_data(self, cache_key, data, timeout=None):
        """Set data in cache"""
        try:
            cache.set(cache_key, data, timeout)
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    def delete_cached_data(self, cache_key):
        """Delete data from cache"""
        try:
            cache.delete(cache_key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    def clear_offer_cache(self, offer_id=None):
        """Clear offer-related cache"""
        if offer_id:
            cache_keys = [
                CACHE_KEY_OFFER_DETAIL.format(offer_id),
            ]
            for key in cache_keys:
                self.delete_cached_data(key)
        
        # Clear list caches
        cache.delete_pattern('offers:list:*')
        cache.delete_pattern('offers:category:*')


class RateLimitMixin:
    """Mixin for rate limiting"""
    
    def check_rate_limit(self, user, action, limit, period):
        """
        Check if user has exceeded rate limit
        
        Args:
            user: User instance
            action: Action name
            limit: Maximum allowed requests
            period: Time period in seconds
        
        Returns:
            bool: True if within limit, False otherwise
        """
        cache_key = f'rate_limit:{user.id}:{action}'
        
        current_count = cache.get(cache_key, 0)
        
        if current_count >= limit:
            return False
        
        # Increment counter
        cache.set(cache_key, current_count + 1, period)
        return True
    
    def get_rate_limit_status(self, user, action):
        """Get current rate limit status"""
        cache_key = f'rate_limit:{user.id}:{action}'
        current_count = cache.get(cache_key, 0)
        
        return {
            'current': current_count,
            'key': cache_key
        }


class FraudCheckMixin:
    """Mixin for fraud detection"""
    
    def check_vpn_proxy(self, ip_address):
        """Check if IP is VPN/Proxy"""
        from api.fraud_detection.models import IPReputation
        
        try:
            ip_rep = IPReputation.objects.get(ip_address=ip_address)
            return ip_rep.fraud_score > FRAUD_THRESHOLD_HIGH
        except IPReputation.DoesNotExist:
            return False
    
    def check_device_fingerprint(self, user, device_data):
        """Check device fingerprint for fraud"""
        from api.fraud_detection.models import DeviceFingerprint
        
        try:
            fingerprints = DeviceFingerprint.objects.filter(
                user=user,
                device_hash=device_data.get('device_hash')
            )
            
            if fingerprints.exists():
                return fingerprints.first().trust_score < 50
            
            return False
        except Exception as e:
            logger.error(f"Device fingerprint check error: {e}")
            return False
    
    def check_user_risk_profile(self, user):
        """Check user's risk profile"""
        from api.fraud_detection.models import UserRiskProfile
        
        try:
            profile = UserRiskProfile.objects.get(user=user)
            return profile.overall_risk_score > FRAUD_THRESHOLD_HIGH
        except UserRiskProfile.DoesNotExist:
            return False


class AnalyticsMixin:
    """Mixin for analytics tracking"""
    
    def track_event(self, event_type, user, offer=None, data=None):
        """Track analytics event"""
        from api.analytics.models import AnalyticsEvent
        
        try:
            AnalyticsEvent.objects.create(
                event_type=event_type,
                user=user,
                metadata={
                    'offer_id': str(offer.id) if offer else None,
                    'offer_title': offer.title if offer else None,
                    **(data or {})
                }
            )
        except Exception as e:
            logger.error(f"Analytics tracking error: {e}")
    
    def track_offer_view(self, offer, user, request):
        """Track offer view"""
        self.track_event(
            EVENT_OFFER_VIEW,
            user,
            offer,
            {
                'ip_address': self.get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')
            }
        )
        
        # Increment offer view count
        offer.increment_view()
    
    def track_offer_click(self, offer, user, request):
        """Track offer click"""
        self.track_event(
            EVENT_OFFER_CLICK,
            user,
            offer,
            {
                'ip_address': self.get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')
            }
        )
        
        # Increment offer click count
        offer.increment_click()
    
    def get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class PaginationMixin:
    """Mixin for custom pagination"""
    
    def paginate_queryset(self, queryset, request, page_size=20):
        """Paginate queryset"""
        from rest_framework.pagination import PageNumberPagination
        
        paginator = PageNumberPagination()
        paginator.page_size = page_size
        
        return paginator.paginate_queryset(queryset, request)
    
    def get_paginated_response(self, data, request, queryset):
        """Get paginated response"""
        from rest_framework.pagination import PageNumberPagination
        
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        return paginator.get_paginated_response(data)


class ResponseMixin:
    """Mixin for standardized responses"""
    
    def success_response(self, data=None, message=None, status_code=CODE_SUCCESS):
        """Return success response"""
        response_data = {
            'success': True,
            'message': message or 'Success',
            'data': data
        }
        return Response(response_data, status=status_code)
    
    def error_response(self, message, code=None, status_code=CODE_BAD_REQUEST):
        """Return error response"""
        response_data = {
            'success': False,
            'message': message,
            'error_code': code
        }
        return Response(response_data, status=status_code)
    
    def paginated_response(self, data, pagination_data):
        """Return paginated response"""
        return Response({
            'success': True,
            'data': data,
            'pagination': pagination_data
        })


class ValidationMixin:
    """Mixin for validation"""
    
    def validate_required_fields(self, data, required_fields):
        """Validate required fields in data"""
        missing_fields = []
        
        for field in required_fields:
            if field not in data or data[field] is None:
                missing_fields.append(field)
        
        if missing_fields:
            raise MissingParameterException(
                f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        return True
    
    def validate_ip_address(self, ip_address):
        """Validate IP address format"""
        import ipaddress
        
        try:
            ipaddress.ip_address(ip_address)
            return True
        except ValueError:
            raise InvalidIPAddressException(f"Invalid IP address: {ip_address}")
    
    def validate_country_code(self, country_code):
        """Validate country code"""
        if not country_code or len(country_code) != 2:
            raise InvalidParameterException("Invalid country code")
        return True
    
    def validate_platform(self, platform):
        """Validate platform"""
        valid_platforms = [PLATFORM_ALL, PLATFORM_ANDROID, PLATFORM_IOS, PLATFORM_WEB, PLATFORM_MOBILE, PLATFORM_DESKTOP]
        
        if platform not in valid_platforms:
            raise InvalidParameterException(f"Invalid platform: {platform}")
        
        return True


class LoggingMixin:
    """Mixin for logging"""
    
    def log_info(self, message, **kwargs):
        """Log info message"""
        logger.info(message, extra=kwargs)
    
    def log_error(self, message, exception=None, **kwargs):
        """Log error message"""
        if exception:
            logger.error(f"{message}: {str(exception)}", exc_info=True, extra=kwargs)
        else:
            logger.error(message, extra=kwargs)
    
    def log_warning(self, message, **kwargs):
        """Log warning message"""
        logger.warning(message, extra=kwargs)
    
    def log_debug(self, message, **kwargs):
        """Log debug message"""
        logger.debug(message, extra=kwargs)


class PermissionMixin:
    """Mixin for permission checks"""
    
    def check_user_active(self, user):
        """Check if user is active"""
        if not user.is_active:
            raise AccountSuspendedException()
        return True
    
    def check_user_verified(self, user):
        """Check if user is verified"""
        if not getattr(user, 'is_verified', True):
            raise ValidationException("Please verify your account first")
        return True
    
    def check_age_requirement(self, user, min_age):
        """Check if user meets age requirement"""
        if hasattr(user, 'age') and user.age < min_age:
            raise ValidationException(f"You must be at least {min_age} years old")
        return True