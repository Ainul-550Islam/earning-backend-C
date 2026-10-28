# api/rate_limit/mixins.py
"""
Mixins for rate limit module.

Provides reusable mixins for Django views and models.
"""
from typing import List

import logging
from typing import Dict, Any, Optional
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import View
from rest_framework.response import Response
from rest_framework import status

from api.rate_limit.services import RateLimitService
from api.rate_limit.models import UserRateLimitProfile

logger = logging.getLogger(__name__)


class RateLimitMixin:
    """
    Mixin to add rate limiting to Django views.
    """
    
    rate_limit_config = None  # Override in subclasses
    rate_limit_requests = 100
    rate_limit_period = 'hour'
    rate_limit_period_value = 1
    
    def dispatch(self, request, *args, **kwargs):
        """
        Apply rate limiting before dispatching to view.
        """
        # Check rate limit
        if self.check_rate_limit(request):
            return super().dispatch(request, *args, **kwargs)
        else:
            return self.rate_limit_exceeded_response(request)
    
    def check_rate_limit(self, request: HttpRequest) -> bool:
        """
        Check if request is within rate limits.
        
        Args:
            request: HTTP request
            
        Returns:
            True if within limits, False otherwise
        """
        try:
            rate_limit_service = RateLimitService()
            
            # Get identifier for rate limiting
            identifier = self.get_rate_limit_identifier(request)
            
            # Check rate limit
            is_limited, remaining, metadata = rate_limit_service.is_rate_limited(
                identifier=identifier,
                limit_type=self.get_limit_type(),
                max_requests=self.rate_limit_requests,
                user=getattr(request, 'user', None),
                ip_address=self.get_client_ip(request),
                endpoint=request.path
            )
            
            # Store rate limit info in request
            request.rate_limit_info = {
                'is_limited': is_limited,
                'remaining': remaining,
                'metadata': metadata
            }
            
            return not is_limited
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {str(e)}")
            return True  # Allow request if check fails
    
    def get_rate_limit_identifier(self, request: HttpRequest) -> str:
        """
        Get identifier for rate limiting.
        
        Args:
            request: HTTP request
            
        Returns:
            Identifier string
        """
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            return f"user:{user.id}"
        else:
            return f"ip:{self.get_client_ip(request)}"
    
    def get_limit_type(self) -> str:
        """
        Get rate limit type.
        
        Returns:
            Limit type string
        """
        if self.rate_limit_config:
            return self.rate_limit_config
        return 'endpoint'
    
    def get_client_ip(self, request: HttpRequest) -> str:
        """
        Get client IP address.
        
        Args:
            request: HTTP request
            
        Returns:
            IP address string
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')
    
    def rate_limit_exceeded_response(self, request: HttpRequest) -> HttpResponse:
        """
        Return response when rate limit is exceeded.
        
        Args:
            request: HTTP request
            
        Returns:
            HTTP response
        """
        from django.http import JsonResponse
        
        return JsonResponse({
            'success': False,
            'error': 'rate_limit_exceeded',
            'message': 'Rate limit exceeded. Please try again later.',
            'retry_after': 60  # Default retry after
        }, status=429)


class APIRateLimitMixin:
    """
    Mixin to add rate limiting to DRF API views.
    """
    
    rate_limit_config = None
    rate_limit_requests = 100
    rate_limit_period = 'hour'
    rate_limit_period_value = 1
    
    def initial(self, request, *args, **kwargs):
        """
        Apply rate limiting before processing request.
        """
        super().initial(request, *args, **kwargs)
        
        # Check rate limit
        if not self.check_api_rate_limit(request):
            self.permission_denied(
                request, 
                message='Rate limit exceeded. Please try again later.',
                code='rate_limit_exceeded'
            )
    
    def check_api_rate_limit(self, request: HttpRequest) -> bool:
        """
        Check if API request is within rate limits.
        
        Args:
            request: HTTP request
            
        Returns:
            True if within limits, False otherwise
        """
        try:
            rate_limit_service = RateLimitService()
            
            # Get identifier for rate limiting
            identifier = self.get_api_rate_limit_identifier(request)
            
            # Check rate limit
            is_limited, remaining, metadata = rate_limit_service.is_rate_limited(
                identifier=identifier,
                limit_type=self.get_api_limit_type(),
                max_requests=self.rate_limit_requests,
                user=getattr(request, 'user', None),
                ip_address=self.get_api_client_ip(request),
                endpoint=request.path
            )
            
            # Store rate limit info
            request.rate_limit_info = {
                'is_limited': is_limited,
                'remaining': remaining,
                'metadata': metadata
            }
            
            # Add rate limit headers
            if not is_limited:
                self.add_rate_limit_headers(request, remaining, metadata)
            
            return not is_limited
            
        except Exception as e:
            logger.error(f"API rate limit check failed: {str(e)}")
            return True
    
    def get_api_rate_limit_identifier(self, request: HttpRequest) -> str:
        """Get identifier for API rate limiting."""
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            return f"api:user:{user.id}"
        else:
            return f"api:ip:{self.get_api_client_ip(request)}"
    
    def get_api_limit_type(self) -> str:
        """Get API rate limit type."""
        if self.rate_limit_config:
            return self.rate_limit_config
        return 'api'
    
    def get_api_client_ip(self, request: HttpRequest) -> str:
        """Get client IP for API requests."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')
    
    def add_rate_limit_headers(self, request: HttpRequest, remaining: int, metadata: Dict[str, Any]):
        """Add rate limit headers to response."""
        if hasattr(self, 'headers'):
            self.headers['X-RateLimit-Remaining'] = str(remaining)
            self.headers['X-RateLimit-Limit'] = str(self.rate_limit_requests)
            
            if 'reset_time' in metadata:
                self.headers['X-RateLimit-Reset'] = str(int(metadata['reset_time']))
    
    def handle_rate_limit_exceeded(self):
        """Handle rate limit exceeded for API."""
        response_data = {
            'success': False,
            'error': 'rate_limit_exceeded',
            'message': 'Rate limit exceeded. Please try again later.',
            'retry_after': 60
        }
        
        response = Response(response_data, status=status.HTTP_429_TOO_MANY_REQUESTS)
        response['Retry-After'] = '60'
        response['X-RateLimit-Remaining'] = '0'
        response['X-RateLimit-Limit'] = str(self.rate_limit_requests)
        
        return response


class UserRateLimitMixin:
    """
    Mixin to add user-specific rate limiting.
    """
    
    def get_user_rate_limit_profile(self, user) -> Optional[UserRateLimitProfile]:
        """
        Get or create user rate limit profile.
        
        Args:
            user: User object
            
        Returns:
            UserRateLimitProfile or None
        """
        try:
            profile, created = UserRateLimitProfile.objects.get_or_create(
                user=user,
                defaults={
                    'api_health_score': 100,
                    'suspicion_score': 0,
                    'custom_daily_limit': 1000,
                    'custom_hourly_limit': 100,
                }
            )
            
            if created:
                logger.info(f"Created rate limit profile for user: {user.username}")
            
            return profile
            
        except Exception as e:
            logger.error(f"Failed to get user rate limit profile: {str(e)}")
            return None
    
    def get_user_rate_limit_multiplier(self, user) -> float:
        """
        Get rate limit multiplier for user based on profile.
        
        Args:
            user: User object
            
        Returns:
            Multiplier value
        """
        profile = self.get_user_rate_limit_profile(user)
        if not profile:
            return 1.0
        
        # Premium users get higher limits
        if profile.is_premium:
            return 2.0
        
        # Users with high suspicion score get lower limits
        if profile.suspicion_score > 70:
            return 0.5
        
        # Users with good API health get normal limits
        if profile.api_health_score > 80:
            return 1.0
        
        return 1.0


class PremiumUserMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin to restrict access to premium users only.
    """
    
    def test_func(self) -> bool:
        """
        Test if user is premium.
        
        Returns:
            True if user is premium, False otherwise
        """
        user = self.request.user
        if not user.is_authenticated:
            return False
        
        try:
            profile = UserRateLimitProfile.objects.get(user=user)
            return profile.is_premium and (
                not profile.premium_until or 
                profile.premium_until > timezone.now()
            )
        except UserRateLimitProfile.DoesNotExist:
            return False
    
    def handle_no_permission(self):
        """
        Handle unauthorized access.
        
        Returns:
            HTTP response
        """
        from django.http import JsonResponse
        
        return JsonResponse({
            'success': False,
            'error': 'premium_required',
            'message': 'This feature is only available to premium users.'
        }, status=403)


class LowSuspicionMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin to restrict access to users with low suspicion scores.
    """
    
    max_suspicion_score = 50
    
    def test_func(self) -> bool:
        """
        Test if user has low suspicion score.
        
        Returns:
            True if user has low suspicion score, False otherwise
        """
        user = self.request.user
        if not user.is_authenticated:
            return False
        
        try:
            profile = UserRateLimitProfile.objects.get(user=user)
            return profile.suspicion_score <= self.max_suspicion_score
        except UserRateLimitProfile.DoesNotExist:
            return True  # No profile means no suspicion score
    
    def handle_no_permission(self):
        """
        Handle unauthorized access.
        
        Returns:
            HTTP response
        """
        from django.http import JsonResponse
        
        return JsonResponse({
            'success': False,
            'error': 'high_suspicion',
            'message': 'Access restricted due to high suspicion score.'
        }, status=403)


class RateLimitStatsMixin:
    """
    Mixin to add rate limit statistics to views.
    """
    
    def get_rate_limit_stats(self, user=None, ip_address=None) -> Dict[str, Any]:
        """
        Get rate limit statistics.
        
        Args:
            user: User object (optional)
            ip_address: IP address (optional)
            
        Returns:
            Statistics dictionary
        """
        try:
            rate_limit_service = RateLimitService()
            
            if user:
                return rate_limit_service.get_user_rate_limit_stats(user)
            elif ip_address:
                # Get IP-based stats
                return self.get_ip_rate_limit_stats(ip_address)
            else:
                # Get global stats
                return rate_limit_service.check_global_health()
                
        except Exception as e:
            logger.error(f"Failed to get rate limit stats: {str(e)}")
            return {'error': str(e)}
    
    def get_ip_rate_limit_stats(self, ip_address: str) -> Dict[str, Any]:
        """
        Get IP-based rate limit statistics.
        
        Args:
            ip_address: IP address
            
        Returns:
            Statistics dictionary
        """
        try:
            from api.rate_limit.models import RateLimitLog
            from datetime import timedelta
            
            # Get recent logs for this IP
            one_hour_ago = timezone.now() - timedelta(hours=1)
            one_day_ago = timezone.now() - timedelta(days=1)
            
            hourly_logs = RateLimitLog.objects.filter(
                ip_address=ip_address,
                timestamp__gte=one_hour_ago
            )
            
            daily_logs = RateLimitLog.objects.filter(
                ip_address=ip_address,
                timestamp__gte=one_day_ago
            )
            
            return {
                'ip_address': ip_address,
                'hourly_requests': hourly_logs.count(),
                'hourly_blocked': hourly_logs.filter(status='blocked').count(),
                'daily_requests': daily_logs.count(),
                'daily_blocked': daily_logs.filter(status='blocked').count(),
                'unique_endpoints': daily_logs.values('endpoint').distinct().count(),
                'last_request': daily_logs.order_by('-timestamp').first().timestamp if daily_logs.exists() else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get IP rate limit stats: {str(e)}")
            return {'error': str(e)}


class RateLimitCacheMixin:
    """
    Mixin for rate limit caching operations.
    """
    
    cache_prefix = 'rate_limit'
    cache_timeout = 3600  # 1 hour
    
    def get_cache_key(self, identifier: str, suffix: str = '') -> str:
        """
        Generate cache key for rate limiting.
        
        Args:
            identifier: Unique identifier
            suffix: Optional suffix
            
        Returns:
            Cache key string
        """
        key = f"{self.cache_prefix}:{identifier}"
        if suffix:
            key += f":{suffix}"
        return key
    
    def get_cached_data(self, identifier: str, suffix: str = '') -> Any:
        """
        Get cached data.
        
        Args:
            identifier: Unique identifier
            suffix: Optional suffix
            
        Returns:
            Cached data or None
        """
        cache_key = self.get_cache_key(identifier, suffix)
        return cache.get(cache_key)
    
    def set_cached_data(self, identifier: str, data: Any, suffix: str = '', timeout: int = None) -> bool:
        """
        Set cached data.
        
        Args:
            identifier: Unique identifier
            data: Data to cache
            suffix: Optional suffix
            timeout: Cache timeout (optional)
            
        Returns:
            True if successful, False otherwise
        """
        cache_key = self.get_cache_key(identifier, suffix)
        timeout = timeout or self.cache_timeout
        return cache.set(cache_key, data, timeout)
    
    def delete_cached_data(self, identifier: str, suffix: str = '') -> bool:
        """
        Delete cached data.
        
        Args:
            identifier: Unique identifier
            suffix: Optional suffix
            
        Returns:
            True if successful, False otherwise
        """
        cache_key = self.get_cache_key(identifier, suffix)
        return cache.delete(cache_key)


class RateLimitLoggingMixin:
    """
    Mixin for rate limit logging operations.
    """
    
    def log_rate_limit_event(self, event_type: str, data: Dict[str, Any]):
        """
        Log rate limit event.
        
        Args:
            event_type: Type of event
            data: Event data
        """
        try:
            logger.info(f"Rate limit event: {event_type} - {data}")
            
            # Store in cache for recent events
            cache_key = f"rate_limit_events:{event_type}"
            recent_events = cache.get(cache_key, [])
            
            recent_events.append({
                'event_type': event_type,
                'data': data,
                'timestamp': timezone.now().isoformat()
            })
            
            # Keep only last 100 events
            if len(recent_events) > 100:
                recent_events = recent_events[-100:]
            
            cache.set(cache_key, recent_events, timeout=3600)
            
        except Exception as e:
            logger.error(f"Failed to log rate limit event: {str(e)}")
    
    def get_recent_events(self, event_type: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent rate limit events.
        
        Args:
            event_type: Specific event type (optional)
            limit: Maximum number of events
            
        Returns:
            List of events
        """
        try:
            if event_type:
                cache_key = f"rate_limit_events:{event_type}"
                events = cache.get(cache_key, [])
            else:
                # Get all events
                all_events = []
                for key in cache.keys('rate_limit_events:*'):
                    all_events.extend(cache.get(key, []))
                events = all_events
            
            # Sort by timestamp and limit
            events.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return events[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get recent events: {str(e)}")
            return []


# Export mixins
__all__ = [
    'RateLimitMixin',
    'APIRateLimitMixin',
    'UserRateLimitMixin',
    'PremiumUserMixin',
    'LowSuspicionMixin',
    'RateLimitStatsMixin',
    'RateLimitCacheMixin',
    'RateLimitLoggingMixin'
]
