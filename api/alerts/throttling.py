"""
Throttling and rate limiting for alerts app
"""
from rest_framework.throttling import SimpleRateThrottle, ScopedRateThrottle
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from django.utils import timezone
from django.http import HttpResponse
from typing import Dict, Any, Optional
import logging
import time
import json

logger = logging.getLogger(__name__)


class AlertRateThrottle(SimpleRateThrottle):
    """Custom rate throttle for alert operations"""
    
    def __init__(self):
        if not getattr(self, 'scope', None):
            self.scope = 'alert'
        super().__init__()
    
    def get_cache_key(self, request, view):
        """Generate cache key for throttling"""
        if hasattr(request, 'user') and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        
        return f'{self.scope}_throttle_{ident}'
    
    def throttle_failure(self, request, response):
        """Handle throttle failure"""
        response.data = {
            'error': 'Rate limit exceeded',
            'detail': f'Rate limit exceeded: {self.wait()} seconds remaining',
            'retry_after': self.wait()
        }
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        return response


class AlertCreateRateThrottle(AlertRateThrottle):
    """Rate throttle for alert creation"""
    scope = 'alert_create'
    
    def __init__(self):
        super().__init__()
        self.rate = '10/h'  # 10 alerts per hour
        self.duration = 3600  # 1 hour


class NotificationRateThrottle(AlertRateThrottle):
    """Rate throttle for notification sending"""
    scope = 'notification_send'
    
    def __init__(self):
        super().__init__()
        self.rate = '100/h'  # 100 notifications per hour
        self.duration = 3600  # 1 hour


class WebhookRateThrottle(AlertRateThrottle):
    """Rate throttle for webhook calls"""
    scope = 'webhook'
    
    def __init__(self):
        super().__init__()
        self.rate = '1000/h'  # 1000 webhook calls per hour
        self.duration = 3600  # 1 hour


class ExportRateThrottle(AlertRateThrottle):
    """Rate throttle for data export"""
    scope = 'export'
    
    def __init__(self):
        super().__init__()
        self.rate = '5/h'  # 5 exports per hour
        self.duration = 3600  # 1 hour


class APIRateThrottle(AlertRateThrottle):
    """General API rate throttle"""
    scope = 'api'
    
    def __init__(self):
        super().__init__()
        self.rate = '1000/h'  # 1000 API calls per hour
        self.duration = 3600  # 1 hour


class BurstRateThrottle(AlertRateThrottle):
    """Burst rate throttle for high-frequency operations"""
    scope = 'burst'
    
    def __init__(self):
        super().__init__()
        self.rate = '100/m'  # 100 requests per minute
        self.duration = 60  # 1 minute


class ScopedAlertThrottle(ScopedRateThrottle):
    """Scoped rate throttle for different alert operations"""
    
    THROTTLE_RATES = {
        'create': '10/h',
        'resolve': '50/h',
        'escalate': '20/h',
        'notify': '100/h',
        'export': '5/h',
        'webhook': '1000/h',
        'search': '200/m',
        'analytics': '50/h'
    }
    
    def get_cache_key(self, request, view):
        """Generate scoped cache key"""
        if hasattr(request, 'user') and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        
        scope = getattr(view, 'throttle_scope', 'default')
        return f'alert_throttle_{scope}_{ident}'
    
    def get_rate(self):
        """Get rate based on scope"""
        scope = getattr(self, 'scope', 'default')
        return self.THROTTLE_RATES.get(scope, '100/h')


class AlertThrottleMiddleware:
    """Middleware for advanced throttling logic"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limiter = AdvancedRateLimiter()
    
    def __call__(self, request):
        """Process request with throttling"""
        # Check request rate limits
        if self.rate_limiter.is_rate_limited(request):
            return self._rate_limited_response(request)
        
        response = self.get_response(request)
        
        # Add rate limit headers
        self._add_rate_limit_headers(request, response)
        
        return response
    
    def _rate_limited_response(self, request):
        """Generate rate limited response"""
        limit_info = self.rate_limiter.get_limit_info(request)
        
        response = HttpResponse(
            content_type='application/json',
            status=429
        )
        response.content = json.dumps({
            'error': 'Rate limit exceeded',
            'message': limit_info['message'],
            'retry_after': limit_info['retry_after'],
            'limit': limit_info['limit'],
            'remaining': limit_info['remaining'],
            'reset_time': limit_info['reset_time']
        })
        
        response['Retry-After'] = str(limit_info['retry_after'])
        response['X-RateLimit-Limit'] = str(limit_info['limit'])
        response['X-RateLimit-Remaining'] = str(limit_info['remaining'])
        response['X-RateLimit-Reset'] = str(limit_info['reset_time'])
        
        return response
    
    def _add_rate_limit_headers(self, request, response):
        """Add rate limit headers to response"""
        limit_info = self.rate_limiter.get_limit_info(request)
        
        if limit_info:
            response['X-RateLimit-Limit'] = str(limit_info['limit'])
            response['X-RateLimit-Remaining'] = str(limit_info['remaining'])
            response['X-RateLimit-Reset'] = str(limit_info['reset_time'])


class AdvancedRateLimiter:
    """Advanced rate limiting with multiple strategies"""
    
    def __init__(self):
        self.strategies = {
            'sliding_window': SlidingWindowLimiter(),
            'token_bucket': TokenBucketLimiter(),
            'fixed_window': FixedWindowLimiter()
        }
        self.default_strategy = 'sliding_window'
    
    def is_rate_limited(self, request) -> bool:
        """Check if request is rate limited"""
        strategy_name = self._get_strategy_for_request(request)
        strategy = self.strategies.get(strategy_name)
        
        if not strategy:
            return False
        
        return strategy.is_limited(request)
    
    def get_limit_info(self, request) -> Optional[Dict[str, Any]]:
        """Get rate limit information"""
        strategy_name = self._get_strategy_for_request(request)
        strategy = self.strategies.get(strategy_name)
        
        if not strategy:
            return None
        
        return strategy.get_limit_info(request)
    
    def _get_strategy_for_request(self, request) -> str:
        """Determine which strategy to use based on request"""
        path = request.path
        
        # Use different strategies for different endpoints
        if '/api/v1/trigger' in path:
            return 'token_bucket'  # Strict for alert creation
        elif '/api/v1/export' in path:
            return 'fixed_window'  # Fixed window for exports
        else:
            return self.default_strategy


class SlidingWindowLimiter:
    """Sliding window rate limiter"""
    
    def __init__(self, window_size: int = 3600, limit: int = 1000):
        self.window_size = window_size  # 1 hour
        self.limit = limit
    
    def is_limited(self, request) -> bool:
        """Check if request is limited"""
        key = self._get_key(request)
        now = int(time.time())
        
        # Get existing requests from cache
        requests = cache.get(key, [])
        
        # Remove old requests outside the window
        requests = [req_time for req_time in requests if now - req_time < self.window_size]
        
        # Add current request
        requests.append(now)
        
        # Store back in cache
        cache.set(key, requests, timeout=self.window_size)
        
        return len(requests) > self.limit
    
    def get_limit_info(self, request) -> Dict[str, Any]:
        """Get limit information"""
        key = self._get_key(request)
        now = int(time.time())
        
        requests = cache.get(key, [])
        requests = [req_time for req_time in requests if now - req_time < self.window_size]
        
        remaining = max(0, self.limit - len(requests))
        reset_time = now + self.window_size
        
        return {
            'limit': self.limit,
            'remaining': remaining,
            'reset_time': reset_time,
            'retry_after': max(0, reset_time - now),
            'message': f'Rate limit: {self.limit} requests per {self.window_size} seconds'
        }
    
    def _get_key(self, request) -> str:
        """Get cache key for request"""
        if hasattr(request, 'user') and request.user.is_authenticated:
            ident = f'user_{request.user.pk}'
        else:
            ident = f'ip_{self._get_client_ip(request)}'
        
        return f'sliding_window_{ident}'
    
    @staticmethod
    def _get_client_ip(request) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip or 'unknown'


class TokenBucketLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, capacity: int = 1000, refill_rate: float = 0.28):
        self.capacity = capacity  # Maximum tokens
        self.refill_rate = refill_rate  # Tokens per second (1000/hour)
    
    def is_limited(self, request) -> bool:
        """Check if request is limited"""
        key = self._get_key(request)
        now = time.time()
        
        # Get current bucket state
        bucket = cache.get(key, {
            'tokens': self.capacity,
            'last_refill': now
        })
        
        # Refill tokens
        time_passed = now - bucket['last_refill']
        tokens_to_add = time_passed * self.refill_rate
        bucket['tokens'] = min(self.capacity, bucket['tokens'] + tokens_to_add)
        bucket['last_refill'] = now
        
        # Check if request can be processed
        if bucket['tokens'] >= 1:
            bucket['tokens'] -= 1
        else:
            # No tokens available
            cache.set(key, bucket, timeout=3600)
            return True
        
        # Store updated bucket
        cache.set(key, bucket, timeout=3600)
        return False
    
    def get_limit_info(self, request) -> Dict[str, Any]:
        """Get limit information"""
        key = self._get_key(request)
        now = time.time()
        bucket = cache.get(key, {
            'tokens': self.capacity,
            'last_refill': now
        })
        
        now = time.time()
        time_passed = now - bucket['last_refill']
        tokens_to_add = time_passed * self.refill_rate
        current_tokens = min(self.capacity, bucket['tokens'] + tokens_to_add)
        
        # Calculate time to next token
        if current_tokens >= 1:
            retry_after = 0
        else:
            retry_after = (1 - current_tokens) / self.refill_rate
        
        return {
            'limit': self.capacity,
            'remaining': max(0, int(current_tokens)),
            'retry_after': max(0, int(retry_after)),
            'reset_time': now + (self.capacity - current_tokens) / self.refill_rate,
            'message': f'Token bucket: {self.capacity} capacity, {self.refill_rate:.2f} tokens/second'
        }
    
    def _get_key(self, request) -> str:
        """Get cache key for request"""
        if hasattr(request, 'user') and request.user.is_authenticated:
            ident = f'user_{request.user.pk}'
        else:
            ident = f'ip_{self._get_client_ip(request)}'
        
        return f'token_bucket_{ident}'

    @staticmethod
    def _get_client_ip(request) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip or 'unknown'


class FixedWindowLimiter:
    """Fixed window rate limiter"""
    
    def __init__(self, window_size: int = 3600, limit: int = 1000):
        self.window_size = window_size  # 1 hour
        self.limit = limit
    
    def is_limited(self, request) -> bool:
        """Check if request is limited"""
        key = self._get_key(request)
        now = int(time.time())
        window_start = now - (now % self.window_size)
        
        # Get current window count
        window_data = cache.get(key, {
            'count': 0,
            'window_start': window_start
        })
        
        # Reset if new window
        if window_data['window_start'] != window_start:
            window_data['count'] = 0
            window_data['window_start'] = window_start
        
        # Check limit
        if window_data['count'] >= self.limit:
            cache.set(key, window_data, timeout=self.window_size)
            return True
        
        # Increment count
        window_data['count'] += 1
        cache.set(key, window_data, timeout=self.window_size)
        
        return False
    
    def get_limit_info(self, request) -> Dict[str, Any]:
        """Get limit information"""
        key = self._get_key(request)
        now = int(time.time())
        window_start = now - (now % self.window_size)
        window_end = window_start + self.window_size
        
        window_data = cache.get(key, {
            'count': 0,
            'window_start': window_start
        })
        
        # Adjust for current window
        if window_data['window_start'] != window_start:
            window_data['count'] = 0
            window_data['window_start'] = window_start
        
        remaining = max(0, self.limit - window_data['count'])
        
        return {
            'limit': self.limit,
            'remaining': remaining,
            'reset_time': window_end,
            'retry_after': max(0, window_end - now),
            'message': f'Fixed window: {self.limit} requests per {self.window_size} seconds'
        }
    
    def _get_key(self, request) -> str:
        """Get cache key for request"""
        if hasattr(request, 'user') and request.user.is_authenticated:
            ident = f'user_{request.user.pk}'
        else:
            ident = f'ip_{self._get_client_ip(request)}'
        
        return f'fixed_window_{ident}'
    
    @staticmethod
    def _get_client_ip(request) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip or 'unknown'


class AdaptiveThrottle:
    """Adaptive throttling based on system load"""
    
    def __init__(self):
        self.base_limiter = SlidingWindowLimiter()
        self.load_multiplier = 1.0
    
    def is_limited(self, request) -> bool:
        """Check if request is limited with adaptive logic"""
        # Adjust limits based on system load
        self._update_load_multiplier()
        
        # Temporarily modify the limiter's limit
        original_limit = self.base_limiter.limit
        self.base_limiter.limit = int(original_limit * self.load_multiplier)
        
        try:
            return self.base_limiter.is_limited(request)
        finally:
            # Restore original limit
            self.base_limiter.limit = original_limit
    
    def _update_load_multiplier(self):
        """Update load multiplier based on system metrics"""
        try:
            from .models import SystemMetrics
            latest_metrics = SystemMetrics.objects.order_by('-timestamp').first()
            
            if latest_metrics:
                cpu_usage = latest_metrics.cpu_usage_percent / 100
                memory_usage = latest_metrics.memory_usage_percent / 100
                
                # Reduce limits under high load
                avg_load = (cpu_usage + memory_usage) / 2
                
                if avg_load > 0.8:  # > 80% load
                    self.load_multiplier = 0.5  # Halve limits
                elif avg_load > 0.6:  # > 60% load
                    self.load_multiplier = 0.7  # Reduce by 30%
                elif avg_load > 0.4:  # > 40% load
                    self.load_multiplier = 0.9  # Reduce by 10%
                else:
                    self.load_multiplier = 1.0  # Full limits
        
        except Exception as e:
            logger.error(f"Error updating load multiplier: {e}")
            self.load_multiplier = 1.0


# Utility functions
def get_throttle_class_for_endpoint(endpoint_type: str):
    """Get appropriate throttle class for endpoint type"""
    throttle_classes = {
        'alert_create': AlertCreateRateThrottle,
        'notification_send': NotificationRateThrottle,
        'webhook': WebhookRateThrottle,
        'export': ExportRateThrottle,
        'api': APIRateThrottle,
        'burst': BurstRateThrottle
    }
    
    return throttle_classes.get(endpoint_type, APIRateThrottle)


def create_custom_throttle(rate: str, scope: str = 'custom'):
    """Create a custom throttle class"""
    class CustomThrottle(AlertRateThrottle):
        def __init__(self):
            super().__init__()
            self.rate = rate
            self.scope = scope
    
    return CustomThrottle


def check_rate_limit_status(request) -> Dict[str, Any]:
    """Check current rate limit status for request"""
    limiter = AdvancedRateLimiter()
    return limiter.get_limit_info(request) or {}
