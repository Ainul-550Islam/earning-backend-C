"""
PART 11: Rate Limit Enforcement Middleware

Implements per-endpoint, per-user rate limiting to prevent:
✓ Bot farms (100+ tasks/hour per user)
✓ API abuse (1000+ requests/hour)
✓ Withdrawal spam (5+ withdrawals/day)
✓ Offer click flooding (100+ clicks/hour)

Design Pattern:
✓ Redis-backed token bucket algorithm
✓ Configurable per endpoint
✓ Fallback to memory cache if Redis unavailable
✓ Audit trail in TaskEventLog for each violation

This module provides:
1. Rate limit middleware (Django middleware)
2. Decorator for view-level enforcement
3. Service for programmatic checks
4. Admin interface for rate limit config
"""

import logging
import time
from typing import Tuple, Optional
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.decorators import decorator_from_middleware_with_args
from django_redis import get_redis_connection

# import sys
# import os
# sys.path.insert(0, os.path.dirname(__file__))
# import models as root_models
# TaskEventLog = root_models.TaskEventLog
from .rate_limit_monitor import rate_limit_metrics
from .rate_limit_bypass import RateLimitBypass
from .rate_limit_circuit_breaker import circuit_breaker_manager
from .rate_limit_headers import RateLimitHeaders, RateLimitResponse
from .rate_limit_queue import burst_limiter
from api.tasks.models_base import TaskEventLog

logger = logging.getLogger(__name__)


class RateLimitViolationError(Exception):
    """User exceeded rate limit"""
    pass


# =========================================================================
# CONFIGURATION (Put in Django settings.py)
# =========================================================================

DEFAULT_RATE_LIMITS = {
    # Format: 'endpoint_name': {'limit': 1000, 'window': 3600}
    # Means: 1000 requests per 3600 seconds (1 hour)
    
    'api_general': {
        'limit': 1000,
        'window': 3600,  # 1 hour
        'scope': 'user'   # Per-user limit
    },
    'postback': {
        'limit': 10000,
        'window': 3600,
        'scope': 'global'  # Global limit
    },
    'withdrawal': {
        'limit': 5,
        'window': 86400,  # 1 day
        'scope': 'user'
    },
    'task_click': {
        'limit': 100,
        'window': 3600,
        'scope': 'user'
    },
    'survey_submit': {
        'limit': 20,
        'window': 3600,
        'scope': 'user'
    },
    'offer_click': {
        'limit': 100,
        'window': 3600,
        'scope': 'user'
    },
    'proof_submit': {
        'limit': 50,
        'window': 3600,
        'scope': 'user'
    },
}


class RateLimitService:
    """
    Service for rate limit enforcement.
    
    Usage:
        rate_limiter = RateLimitService()
        
        is_allowed, remaining = rate_limiter.check_limit(
            limit_type='task_click',
            identifier='user_123'
        )
        
        if not is_allowed:
            return Response(
                {'error': 'Rate limit exceeded'},
                status=429
            )
    """
    
    REDIS_KEY_PREFIX = 'rate_limit'
    
    def __init__(self):
        """Initialize rate limit service"""
        self.redis_client = self._get_redis_client()
        self.rate_limits = self._load_rate_limits()
    
    def _load_rate_limits(self):
        """Load rate limits from database, fallback to defaults"""
        try:
            from .models import RateLimitConfig
            configs = RateLimitConfig.objects.filter(is_active=True)
            limits = {}
            for config in configs:
                limits[config.limit_type] = {
                    'limit': config.limit,
                    'window': config.window_seconds,
                    'scope': config.scope
                }
            # Merge with defaults for any missing configs
            for key, default in DEFAULT_RATE_LIMITS.items():
                if key not in limits:
                    limits[key] = default
            return limits
        except Exception as e:
            logger.warning(f"Could not load rate limits from database: {e}")
            return DEFAULT_RATE_LIMITS
    
    def refresh_config(self):
        """Refresh rate limit configuration from database"""
        self.rate_limits = self._load_rate_limits()
        logger.info("Rate limit configuration refreshed")
    
    def _get_redis_client(self):
        """Get Redis connection with fallback to None"""
        try:
            return get_redis_connection('default')
        except Exception as e:
            logger.warning(f"Redis unavailable for rate limiting: {e}")
            return None
    
    # =========================================================================
    # MAIN ENFORCEMENT
    # =========================================================================
    
    def check_limit(
        self,
        limit_type: str,
        identifier: str,
        increment_by: int = 1
    ) -> Tuple[bool, int]:
        """
        Check if request is within rate limit.
        Increments counter if within limit.
        
        Args:
            limit_type: Rate limit config key (e.g. 'task_click')
            identifier: User ID or IP (e.g. 'user_123')
            increment_by: How many units to increment (default: 1)
        
        Returns:
            (is_allowed: bool, remaining: int)
            - (True, 50) if allowed and 50 requests remain
            - (False, 0) if rate limited
        """
        start_time = time.time()

        # Check for global bypass
        if RateLimitBypass.is_global_bypass_active():
            logger.info(f"[RATE_LIMIT] Global bypass active, allowing {limit_type}:{identifier}")
            rate_limit_metrics.record_hit(limit_type, identifier, time.time() - start_time)
            return True, -1

        # Check for user-specific bypass
        if identifier.startswith('user_') and RateLimitBypass.is_user_bypass_active(int(identifier[5:])):
            logger.info(f"[RATE_LIMIT] User bypass active, allowing {limit_type}:{identifier}")
            rate_limit_metrics.record_hit(limit_type, identifier, time.time() - start_time)
            return True, -1

        if limit_type not in self.rate_limits:
            logger.warning(f"Unknown rate limit type: {limit_type}")
            rate_limit_metrics.record_hit(limit_type, identifier, time.time() - start_time)
            return True, -1  # Allow if not configured
        
        config = self.rate_limits[limit_type]

        # Check endpoint-specific bypass
        if RateLimitBypass.is_endpoint_bypass_active(limit_type):
            logger.info(f"[RATE_LIMIT] Endpoint bypass active for {limit_type}, allowing {identifier}")
            rate_limit_metrics.record_hit(limit_type, identifier, time.time() - start_time)
            return True, -1

        cache_key = self._make_cache_key(limit_type, identifier)
        
        # Try circuit breaker protected Redis first
        try:
            result = circuit_breaker_manager.check_rate_limit_with_circuit_breaker(limit_type, identifier)
            is_allowed, remaining = result

            # Record metrics
            if is_allowed:
                rate_limit_metrics.record_hit(limit_type, identifier, time.time() - start_time)
            else:
                rate_limit_metrics.record_violation(limit_type, identifier)

            return is_allowed, remaining

        except Exception as e:
            logger.warning(f"Circuit breaker open for {limit_type}, falling back to cache: {e}")
            # Fallback to Django cache
            return self._check_limit_cache_fallback(
                cache_key,
                config,
                increment_by,
                limit_type,
                identifier,
                start_time
            )
    
    def _check_limit_cache_fallback(
        self,
        cache_key: str,
        config: dict,
        increment_by: int,
        limit_type: str,
        identifier: str,
        start_time: float
    ) -> Tuple[bool, int]:
        """
        Fallback: Check limit using Django cache when circuit breaker is open.
        """
        try:
            # Get current count
            current = cache.get(cache_key, 0)
            new_count = current + increment_by
            
            # Set with TTL
            cache.set(cache_key, new_count, config['window'])
            
            # Check if exceeded
            limit = config['limit']
            is_allowed = new_count <= limit
            remaining = max(0, limit - new_count)
            
            # Record metrics
            if is_allowed:
                rate_limit_metrics.record_hit(limit_type, identifier, time.time() - start_time)
            else:
                rate_limit_metrics.record_violation(limit_type, identifier)
            
            return is_allowed, remaining
        
        except Exception as e:
            logger.error(f"Error in cache rate limiting fallback: {e}")
            # Fail open but record violation
            rate_limit_metrics.record_violation(limit_type, identifier)
            return True, -1  # Fail open
    
    def _check_limit_redis(
        self,
        cache_key: str,
        config: dict,
        increment_by: int
    ) -> Tuple[bool, int]:
        """
        Check limit using Redis (preferred).
        Uses INCR + EXPIRE for atomic operation.
        """
        try:
            # Increment counter
            current = self.redis_client.incr(cache_key, increment_by)
            
            # Set expiry only on first request
            if current == increment_by:
                self.redis_client.expire(cache_key, config['window'])
            
            # Check if exceeded
            limit = config['limit']
            is_allowed = current <= limit
            remaining = max(0, limit - current)
            
            return is_allowed, remaining
        
        except Exception as e:
            logger.error(f"Error in Redis rate limiting: {e}")
            return True, -1  # Fail open
    
    def _check_limit_cache(
        self,
        cache_key: str,
        config: dict,
        increment_by: int
    ) -> Tuple[bool, int]:
        """
        Fallback: Check limit using Django cache.
        Less precise but works without Redis.
        """
        try:
            # Get current count
            current = cache.get(cache_key, 0)
            new_count = current + increment_by
            
            # Set with TTL
            cache.set(cache_key, new_count, config['window'])
            
            # Check if exceeded
            limit = config['limit']
            is_allowed = new_count <= limit
            remaining = max(0, limit - new_count)
            
            return is_allowed, remaining
        
        except Exception as e:
            logger.error(f"Error in cache rate limiting: {e}")
            return True, -1  # Fail open
    
    def _make_cache_key(self, limit_type: str, identifier: str) -> str:
        """Generate cache key for rate limit counter"""
        return f"{self.REDIS_KEY_PREFIX}:{limit_type}:{identifier}"
    
    # =========================================================================
    # RESET (Admin functions)
    # =========================================================================
    
    def reset_limit(self, limit_type: str, identifier: str) -> bool:
        """Reset rate limit for specific user/endpoint"""
        cache_key = self._make_cache_key(limit_type, identifier)
        
        if self.redis_client:
            self.redis_client.delete(cache_key)
        else:
            cache.delete(cache_key)
        
        return True
    
    def reset_all_user_limits(self, user_id: int) -> int:
        """Reset all rate limits for a user"""
        count = 0
        
        for limit_type in self.rate_limits.keys():
            identifier = f"user_{user_id}"
            if self.reset_limit(limit_type, identifier):
                count += 1
        
        logger.info(f"Reset {count} rate limits for user {user_id}")
        return count


# =========================================================================
# DJANGO MIDDLEWARE
# =========================================================================

class RateLimitMiddleware:
    """
    WSGI middleware for rate limiting.
    Enforces global rate limits on all requests.
    
    Installation in settings.py:
    MIDDLEWARE = [
        ...
        'tasks.middleware_rate_limit.RateLimitMiddleware',
    ]
    """
    
    # Endpoints to rate limit
    PROTECTED_ENDPOINTS = [
        '/api/tasks/',
        '/api/proof/',
        '/api/withdrawal/',
        '/api/postback/',
    ]
    
    def __init__(self, get_response):
        """Initialize middleware"""
        self.get_response = get_response
        self.rate_limiter = RateLimitService()
    
    def __call__(self, request):
        """Process request"""
        # Skip rate limiting for non-API endpoints
        if not any(request.path.startswith(ep) for ep in self.PROTECTED_ENDPOINTS):
            return self.get_response(request)
        
        # Skip authenticated admin users
        if hasattr(request, 'user') and request.user.is_staff:
            return self.get_response(request)
        
        # Determine limit type and identifier
        limit_type = self._get_limit_type(request)
        identifier = self._get_identifier(request)
        
        if not limit_type or not identifier:
            return self.get_response(request)
        
        # Check rate limit
        is_allowed, remaining = self.rate_limiter.check_limit(
            limit_type=limit_type,
            identifier=identifier
        )
        
        # Store rate limit info for header middleware
        request._rate_limit_info = {
            'limit': self.rate_limiter.rate_limits.get(limit_type, {}).get('limit', 100),
            'remaining': remaining,
            'window_seconds': self.rate_limiter.rate_limits.get(limit_type, {}).get('window', 3600),
            'scope': self.rate_limiter.rate_limits.get(limit_type, {}).get('scope', 'user'),
        }
        
        if not is_allowed:
            logger.warning(
                f"Rate limit exceeded: {limit_type} for {identifier} "
                f"({remaining} remaining)"
            )
            
            # Log violation
            self._log_rate_limit_violation(request, limit_type, identifier)
            
            # Return 429 with proper headers
            retry_after = self.rate_limiter.rate_limits.get(limit_type, {}).get('window', 3600) // 60
            return RateLimitResponse.too_many_requests(
                message=f'Max {request._rate_limit_info["limit"]} requests per hour',
                retry_after=retry_after,
                limit=request._rate_limit_info["limit"],
                scope=request._rate_limit_info["scope"]
            )
        
        # Process request
        response = self.get_response(request)
        
        # Add rate limit headers (handled by RateLimitHeaderMiddleware)
        
        return response
    
    def _get_limit_type(self, request) -> Optional[str]:
        """Determine rate limit type from request path"""
        if '/api/withdrawal/' in request.path:
            return 'withdrawal'
        elif '/api/postback/' in request.path:
            return 'postback'
        elif '/api/proof/' in request.path:
            return 'proof_submit'
        elif '/api/tasks/' in request.path and request.method == 'POST':
            return 'task_click'
        else:
            return 'api_general'
    
    def _get_identifier(self, request) -> Optional[str]:
        """Determine identifier (user ID or IP)"""
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"user_{request.user.id}"
        
        # Fallback to IP address
        ip = request.META.get('HTTP_X_FORWARDED_FOR')
        if ip:
            return f"ip_{ip.split(',')[0]}"
        
        return f"ip_{request.META.get('REMOTE_ADDR')}"
    
    def _log_rate_limit_violation(
        self,
        request,
        limit_type: str,
        identifier: str
    ):
        """Log rate limit violation to TaskEventLog"""
        try:
            user_id = None
            if hasattr(request, 'user') and request.user.is_authenticated:
                user_id = request.user.id
            
            TaskEventLog.objects.create(
                event_type=TaskEventLog.EventType.ADMIN_BLOCK,  # Reuse for rate limit
                actor_type=TaskEventLog.ActorType.SYSTEM,
                user_id=user_id,
                ip_address=request.META.get('REMOTE_ADDR'),
                event_data={
                    'violation_type': 'rate_limit',
                    'limit_type': limit_type,
                    'identifier': identifier,
                    'path': request.path,
                    'method': request.method
                }
            )
        except Exception as e:
            logger.error(f"Error logging rate limit violation: {e}")


# =========================================================================
# DECORATOR FOR VIEW-LEVEL ENFORCEMENT
# =========================================================================

def rate_limit(limit_type: str, identifier_func=None):
    """
    Decorator to enforce rate limits on specific views.
    
    Usage:
        @rate_limit('task_click', identifier_func=lambda r: f"user_{r.user.id}")
        def task_click_view(request):
            ...
    
    Args:
        limit_type: Rate limit config key
        identifier_func: Function(request) → identifier string
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            rate_limiter = RateLimitService()
            
            # Get identifier
            if identifier_func:
                identifier = identifier_func(request)
            else:
                # Default: use user ID or IP
                if hasattr(request, 'user') and request.user.is_authenticated:
                    identifier = f"user_{request.user.id}"
                else:
                    identifier = f"ip_{request.META.get('REMOTE_ADDR')}"
            
            # Check limit
            is_allowed, remaining = rate_limiter.check_limit(limit_type, identifier)
            
            if not is_allowed:
                return JsonResponse(
                    {
                        'error': 'Rate limit exceeded',
                        'remaining': remaining
                    },
                    status=429
                )
            
            # Call view
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator


# =========================================================================
# HELPER FUNCTION
# =========================================================================

def check_rate_limit(
    limit_type: str,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None
) -> Tuple[bool, int]:
    """
    Convenience function to check rate limit.
    
    Example:
        is_allowed, remaining = check_rate_limit(
            'task_click',
            user_id=request.user.id
        )
        
        if not is_allowed:
            return Response({'error': 'Rate limited'}, status=429)
    """
    rate_limiter = RateLimitService()
    
    if user_id:
        identifier = f"user_{user_id}"
    elif ip_address:
        identifier = f"ip_{ip_address}"
    else:
        raise ValueError("Must provide user_id or ip_address")
    
    return rate_limiter.check_limit(limit_type, identifier)


# =========================================================================
# SIGNAL RECEIVERS
# =========================================================================

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver([post_save, post_delete], sender='tasks.RateLimitConfig')
def refresh_rate_limit_config(sender, instance=None, **kwargs):
    """Refresh rate limit configuration when model changes"""
    try:
        # Get the global rate limiter instance if it exists
        # This assumes the middleware is loaded and has an instance
        from django.core.context_processors import request
        # For now, we'll create a new instance and refresh
        # In production, you might want to cache the service instance
        limiter = RateLimitService()
        limiter.refresh_config()
    except Exception as e:
        logger.error(f"Error refreshing rate limit config: {e}")
