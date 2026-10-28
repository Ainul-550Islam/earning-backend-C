# api/rate_limit/throttling.py
"""
Throttling classes for rate limit module.

Provides Django REST Framework throttling classes.
"""
from django.conf import settings

import logging
from typing import Dict, Any, Optional
from django.core.cache import cache
from django.utils import timezone
from rest_framework.throttling import BaseThrottle, SimpleRateThrottle
from rest_framework import status
from rest_framework.response import Response

from api.rate_limit.services import RateLimitService
from api.rate_limit.models import RateLimitConfig, UserRateLimitProfile

logger = logging.getLogger(__name__)


class RateLimitThrottle(BaseThrottle):
    """
    Custom throttle class that integrates with the rate limit service.
    """
    
    def __init__(self):
        self.rate_limit_service = RateLimitService()
        super().__init__()
    
    def get_ident(self, request):
        """
        Get identifier for throttling.
        
        Args:
            request: HTTP request
            
        Returns:
            Identifier string
        """
        # Try user-based throttling first
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"user:{request.user.id}"
        
        # Fall back to IP-based throttling
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        
        return f"ip:{ip}"
    
    def allow_request(self, request, view):
        """
        Check if request should be allowed.
        
        Args:
            request: HTTP request
            view: DRF view
            
        Returns:
            True if request is allowed
        """
        # Get identifier
        ident = self.get_ident(request)
        
        # Get throttle rate from view
        throttle_rate = self.get_rate_limit(view)
        
        if throttle_rate is None:
            return True  # No throttling
        
        # Parse rate (e.g., "100/hour")
        num_requests, period = throttle_rate.split('/')
        num_requests = int(num_requests)
        
        # Convert period to seconds
        period_seconds = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400
        }.get(period, 3600)
        
        # Check rate limit using service
        try:
            is_limited, remaining, metadata = self.rate_limit_service.is_rate_limited(
                identifier=ident,
                limit_type='throttle',
                max_requests=num_requests,
                user=getattr(request, 'user', None),
                ip_address=self._get_client_ip(request),
                endpoint=request.path
            )
            
            if not is_limited:
                # Store throttle info for response headers
                request.throttle_info = {
                    'limit': num_requests,
                    'remaining': remaining,
                    'reset_time': metadata.get('reset_time'),
                }
                return True
            else:
                # Request is throttled
                self.wait = metadata.get('wait_time', period_seconds)
                return False
                
        except Exception as e:
            logger.error("Throttle check failed: %s", str(e), exc_info=True)
            return True  # Allow request if check fails
    
    def get_rate_limit(self, view) -> Optional[str]:
        """
        Get rate limit from view.
        
        Args:
            view: DRF view
            
        Returns:
            Rate limit string or None
        """
        # Check view-level throttle rate
        if hasattr(view, 'throttle_rate'):
            return view.throttle_rate
        
        # Check view class throttle rates
        if hasattr(view, 'throttle_rates'):
            # Get the first rate for this throttle class
            throttle_class_name = self.__class__.__name__
            if throttle_class_name in view.throttle_rates:
                return view.throttle_rates[throttle_class_name]
        
        # Default rate
        return getattr(settings, 'RATE_LIMIT_DEFAULT_THROTTLE', '100/hour')
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')
    
    def wait(self):
        """Get wait time for throttled request."""
        return getattr(self, 'wait', None)


class UserRateThrottle(SimpleRateThrottle):
    """
    Throttle based on user ID.
    """
    
    scope = 'user'
    
    def get_cache_key(self, request, view):
        """
        Get cache key for user-based throttling.
        
        Args:
            request: HTTP request
            view: DRF view
            
        Returns:
            Cache key string
        """
        if request.user.is_authenticated:
            ident = request.user.id
        else:
            # Use IP for anonymous users
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ident = x_forwarded_for.split(',')[0].strip()
            else:
                ident = request.META.get('REMOTE_ADDR', '127.0.0.1')
        
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }
    
    def get_rate(self):
        """Get rate based on user profile."""
        if not hasattr(self.request, 'user') or not self.request.user.is_authenticated:
            return '100/hour'  # Default for anonymous
        
        try:
            profile = UserRateLimitProfile.objects.get(user=self.request.user)
            
            # Use custom limits if available
            if profile.custom_hourly_limit:
                return f'{profile.custom_hourly_limit}/hour'
            
            # Premium users get higher limits
            if profile.is_premium:
                return '500/hour'
            
            # Standard users
            return '100/hour'
            
        except UserRateLimitProfile.DoesNotExist:
            return '100/hour'  # Default


class IPRateThrottle(SimpleRateThrottle):
    """
    Throttle based on IP address.
    """
    
    scope = 'ip'
    
    def get_cache_key(self, request, view):
        """Get cache key for IP-based throttling."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ident = x_forwarded_for.split(',')[0].strip()
        else:
            ident = request.META.get('REMOTE_ADDR', '127.0.0.1')
        
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class EndpointRateThrottle(SimpleRateThrottle):
    """
    Throttle based on endpoint.
    """
    
    scope = 'endpoint'
    
    def get_cache_key(self, request, view):
        """Get cache key for endpoint-based throttling."""
        ident = request.path
        
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }
    
    def get_rate(self):
        """Get rate based on endpoint configuration."""
        try:
            config = RateLimitConfig.objects.filter(
                endpoint=self.request.path,
                rate_limit_type='endpoint',
                is_active=True
            ).first()
            
            if config:
                return f'{config.requests_per_unit}/{config.time_unit}'
            
        except Exception as e:
            logger.error("Failed to get endpoint rate: %s", str(e), exc_info=True)
        
        # Default rate
        return '100/hour'


class PremiumUserThrottle(UserRateThrottle):
    """
    Throttle with higher limits for premium users.
    """
    
    def get_rate(self):
        """Get rate based on user premium status."""
        if not hasattr(self.request, 'user') or not self.request.user.is_authenticated:
            return '50/hour'  # Lower limit for anonymous
        
        try:
            profile = UserRateLimitProfile.objects.get(user=self.request.user)
            
            if profile.is_premium:
                return '1000/hour'  # Much higher for premium
            else:
                return '100/hour'  # Standard for regular users
                
        except UserRateLimitProfile.DoesNotExist:
            return '100/hour'


class BurstRateThrottle(BaseThrottle):
    """
    Throttle that allows bursts but limits sustained rate.
    """
    
    def __init__(self):
        self.burst_limit = getattr(settings, 'RATE_LIMIT_BURST_LIMIT', 10)
        self.sustained_limit = getattr(settings, 'RATE_LIMIT_SUSTAINED_LIMIT', 5)
        self.burst_window = getattr(settings, 'RATE_LIMIT_BURST_WINDOW', 60)  # seconds
        self.sustained_window = getattr(settings, 'RATE_LIMIT_SUSTAINED_WINDOW', 300)  # seconds
        super().__init__()
    
    def allow_request(self, request, view):
        """Check if request should be allowed with burst handling."""
        ident = self.get_ident(request)
        
        # Get current counts
        burst_key = f"burst_throttle:{ident}"
        sustained_key = f"sustained_throttle:{ident}"
        
        burst_count = cache.get(burst_key, 0)
        sustained_count = cache.get(sustained_key, 0)
        
        # Check burst limit first
        if burst_count < self.burst_limit:
            # Allow request
            cache.set(burst_key, burst_count + 1, self.burst_window)
            cache.set(sustained_key, sustained_count + 1, self.sustained_window)
            return True
        
        # Burst limit exceeded, check sustained limit
        if sustained_count < self.sustained_limit:
            # Allow request but update sustained count only
            cache.set(sustained_key, sustained_count + 1, self.sustained_window)
            return True
        
        # Both limits exceeded
        return False
    
    def get_ident(self, request):
        """Get identifier for throttling."""
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"user:{request.user.id}"
        
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return f"ip:{x_forwarded_for.split(',')[0].strip()}"
        
        return f"ip:{request.META.get('REMOTE_ADDR', '127.0.0.1')}"


class AdaptiveThrottle(BaseThrottle):
    """
    Throttle that adapts based on user behavior and system load.
    """
    
    def __init__(self):
        self.base_rate = getattr(settings, 'RATE_LIMIT_ADAPTIVE_BASE', 100)
        self.min_rate = getattr(settings, 'RATE_LIMIT_ADAPTIVE_MIN', 10)
        self.max_rate = getattr(settings, 'RATE_LIMIT_ADAPTIVE_MAX', 1000)
        super().__init__()
    
    def allow_request(self, request, view):
        """Check if request should be allowed with adaptive rate."""
        ident = self.get_ident(request)
        
        # Calculate adaptive rate
        adaptive_rate = self._calculate_adaptive_rate(request)
        
        # Get current count
        cache_key = f"adaptive_throttle:{ident}"
        current_count = cache.get(cache_key, 0)
        
        if current_count < adaptive_rate:
            # Allow request
            cache.set(cache_key, current_count + 1, 3600)  # 1 hour window
            return True
        
        return False
    
    def _calculate_adaptive_rate(self, request) -> int:
        """Calculate adaptive rate based on various factors."""
        rate = self.base_rate
        
        # Adjust based on user profile
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                profile = UserRateLimitProfile.objects.get(user=request.user)
                
                # Premium users get higher rates
                if profile.is_premium:
                    rate = int(rate * 2)
                
                # Users with good health scores get higher rates
                if profile.api_health_score > 80:
                    rate = int(rate * 1.5)
                elif profile.api_health_score < 50:
                    rate = int(rate * 0.5)
                
                # Users with high suspicion scores get lower rates
                if profile.suspicion_score > 70:
                    rate = int(rate * 0.3)
                
            except UserRateLimitProfile.DoesNotExist:
                pass
        
        # Adjust based on system load
        system_health = cache.get('rate_limit_system_health', {})
        health_score = system_health.get('health_score', 100)
        
        if health_score < 50:
            rate = int(rate * 0.7)  # Reduce rate during poor system health
        
        # Ensure rate is within bounds
        rate = max(self.min_rate, min(self.max_rate, rate))
        
        return rate
    
    def get_ident(self, request):
        """Get identifier for throttling."""
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"user:{request.user.id}"
        
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return f"ip:{x_forwarded_for.split(',')[0].strip()}"
        
        return f"ip:{request.META.get('REMOTE_ADDR', '127.0.0.1')}"


class ConditionalThrottle(BaseThrottle):
    """
    Throttle that applies only under certain conditions.
    """
    
    def __init__(self):
        self.conditions = getattr(settings, 'RATE_LIMIT_CONDITIONAL_THROTTLE_CONDITIONS', {})
        super().__init__()
    
    def allow_request(self, request, view):
        """Check if request should be allowed based on conditions."""
        # Check if any condition applies
        if not self._should_throttle(request, view):
            return True
        
        # Apply throttling
        ident = self.get_ident(request)
        cache_key = f"conditional_throttle:{ident}"
        
        current_count = cache.get(cache_key, 0)
        limit = self._get_limit_for_request(request, view)
        
        if current_count < limit:
            cache.set(cache_key, current_count + 1, 3600)
            return True
        
        return False
    
    def _should_throttle(self, request, view) -> bool:
        """Check if throttling should be applied."""
        # Check time-based conditions
        current_hour = timezone.now().hour
        if 'business_hours' in self.conditions:
            business_hours = self.conditions['business_hours']
            if business_hours['start'] <= current_hour <= business_hours['end']:
                return True
        
        # Check user-based conditions
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Check if user is in specific group
            if 'user_groups' in self.conditions:
                required_groups = self.conditions['user_groups']
                if request.user.groups.filter(name__in=required_groups).exists():
                    return True
        
        # Check endpoint-based conditions
        if 'endpoints' in self.conditions:
            endpoints = self.conditions['endpoints']
            if any(request.path.startswith(endpoint) for endpoint in endpoints):
                return True
        
        return False
    
    def _get_limit_for_request(self, request, view) -> int:
        """Get limit based on request context."""
        # Default limit
        limit = 100
        
        # Adjust based on conditions
        if 'limits' in self.conditions:
            limits = self.conditions['limits']
            
            # Time-based limits
            current_hour = timezone.now().hour
            if 'hourly' in limits and str(current_hour) in limits['hourly']:
                limit = limits['hourly'][str(current_hour)]
            
            # User-based limits
            if hasattr(request, 'user') and request.user.is_authenticated:
                if 'premium' in limits and request.user.groups.filter(name='premium').exists():
                    limit = limits['premium']
            
            # Endpoint-based limits
            if 'endpoints' in limits:
                for endpoint_pattern, endpoint_limit in limits['endpoints'].items():
                    if request.path.startswith(endpoint_pattern):
                        limit = endpoint_limit
                        break
        
        return limit
    
    def get_ident(self, request):
        """Get identifier for throttling."""
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"user:{request.user.id}"
        
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return f"ip:{x_forwarded_for.split(',')[0].strip()}"
        
        return f"ip:{request.META.get('REMOTE_ADDR', '127.0.0.1')}"


# Export throttle classes
__all__ = [
    'RateLimitThrottle',
    'UserRateThrottle',
    'IPRateThrottle',
    'EndpointRateThrottle',
    'PremiumUserThrottle',
    'BurstRateThrottle',
    'AdaptiveThrottle',
    'ConditionalThrottle'
]
