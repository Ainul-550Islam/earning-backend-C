"""
Gamification Throttling — Rate limiting and access control for gamification APIs.

This module provides comprehensive rate limiting functionality for gamification
endpoints with different tiers, user-based limits, and burst handling.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from django.core.cache import cache
from django.conf import settings
from django.http import HttpRequest
from django.utils import timezone

from api.gamification.exceptions import GamificationServiceError

logger = logging.getLogger(__name__)


class GamificationRateThrottle:
    """
    Rate limiting for gamification API endpoints.
    
    Provides tiered rate limiting based on user roles and request types.
    """
    
    def __init__(self):
        # Default rate limits (requests per minute)
        self.default_limits = {
            'anonymous': 60,      # 60 requests per minute
            'authenticated': 120,  # 120 requests per minute
            'premium': 300,       # 300 requests per minute
            'admin': 600,         # 600 requests per minute
        }
        
        # Override with settings if available
        self.limits = getattr(settings, 'GAMIFICATION_RATE_LIMITS', self.default_limits)
        
        # Cache settings
        self.cache_timeout = getattr(settings, 'GAMIFICATION_CACHE_TIMEOUT', 60)
        self.cache_prefix = 'gamification_throttle:'
        
        # Burst settings
        self.burst_limit = getattr(settings, 'GAMIFICATION_BURST_LIMIT', 10)
        self.burst_window = getattr(settings, 'GAMIFICATION_BURST_WINDOW', 60)
        
        # Special endpoint limits
        self.endpoint_limits = {
            'badge_check_eligibility': 30,    # Lower limit for eligibility checks
            'badge_award_eligible': 10,       # Very low limit for awarding
            'streak_update_activity': 60,      # Moderate limit for streak updates
            'challenge_update_progress': 120,  # Higher limit for progress updates
            'level_get_user_level': 60,       # Moderate limit for level checks
        }
    
    def allow_request(self, request: HttpRequest) -> bool:
        """
        Check if request should be allowed based on rate limiting.
        
        Args:
            request: Django HTTP request object
            
        Returns:
            bool: True if request is allowed, False otherwise
        """
        try:
            # Get user and role
            user = getattr(request, 'user', None)
            role = self._get_user_role(user)
            
            # Get request identifier
            request_id = self._get_request_identifier(request)
            
            # Get endpoint-specific limit
            endpoint_limit = self._get_endpoint_limit(request)
            
            # Determine rate limit
            if endpoint_limit is not None:
                rate_limit = endpoint_limit
            else:
                rate_limit = self.limits.get(role, self.limits.get('anonymous', 100))
            
            # Check rate limit
            return self._check_rate_limit(request_id, rate_limit, role)
            
        except Exception as e:
            logger.error(f"Error in rate limiting: {e}")
            # Fail open - allow request if rate limiting fails
            return True
    
    def _get_user_role(self, user) -> str:
        """Get user role for rate limiting."""
        if not user or not user.is_authenticated:
            return 'anonymous'
        
        if user.is_staff or user.is_superuser:
            return 'admin'
        
        # Check for premium status (customize based on your user model)
        if hasattr(user, 'is_premium') and user.is_premium:
            return 'premium'
        
        return 'authenticated'
    
    def _get_request_identifier(self, request: HttpRequest) -> str:
        """Get unique identifier for request."""
        # Use IP address for anonymous users
        if not request.user.is_authenticated:
            ip_address = self._get_client_ip(request)
            return f"ip:{ip_address}"
        
        # Use user ID for authenticated users
        return f"user:{request.user.id}"
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return ip
    
    def _get_endpoint_limit(self, request: HttpRequest) -> Optional[int]:
        """Get endpoint-specific rate limit."""
        # Extract endpoint from request path
        path = request.path.strip('/')
        
        # Map paths to endpoint names
        endpoint_mapping = {
            'badges/check-eligibility': 'badge_check_eligibility',
            'badges/award-eligible': 'badge_award_eligible',
            'streaks/update': 'streak_update_activity',
            'challenges/update': 'challenge_update_progress',
            'levels/current': 'level_get_user_level',
        }
        
        # Check for exact match
        if path in endpoint_mapping:
            return self.endpoint_limits.get(endpoint_mapping[path])
        
        # Check for partial match
        for endpoint_pattern, endpoint_name in endpoint_mapping.items():
            if endpoint_pattern in path:
                return self.endpoint_limits.get(endpoint_name)
        
        return None
    
    def _check_rate_limit(self, request_id: str, rate_limit: int, role: str) -> bool:
        """Check if request is within rate limit."""
        now = timezone.now()
        window_start = now - timedelta(minutes=1)
        
        # Get cache key
        cache_key = f"{self.cache_prefix}{request_id}:{role}"
        
        # Get current request count
        request_data = cache.get(cache_key, {
            'count': 0,
            'window_start': window_start.isoformat(),
            'burst_count': 0,
            'burst_window_start': now.isoformat()
        })
        
        # Parse cached data
        try:
            if isinstance(request_data, str):
                # Handle legacy string format
                count = int(request_data)
                burst_count = 0
            else:
                count = request_data.get('count', 0)
                burst_count = request_data.get('burst_count', 0)
        except (ValueError, TypeError):
            count = 0
            burst_count = 0
        
        # Check burst limit first — fail fast if exceeded
        if not self._check_burst_limit(request_id, burst_count, role):
            logger.warning(f"Burst limit exceeded for {request_id} ({role})")
            return False

        # Check rate limit
        if count >= rate_limit:
            logger.warning(f"Rate limit exceeded for {request_id} ({role}): {count}/{rate_limit}")
            return False
        
        # Increment count
        count += 1
        
        # Update cache
        cache.set(cache_key, {
            'count': count,
            'window_start': window_start.isoformat(),
            'burst_count': burst_count,
            'burst_window_start': now.isoformat()
        }, timeout=self.cache_timeout)
        
        return True
    
    def _check_burst_limit(self, request_id: str, burst_count: int, role: str) -> bool:
        """Check burst limit for short-term requests."""
        now = timezone.now()
        burst_window_start = now - timedelta(seconds=self.burst_window)
        
        # Get burst cache key
        burst_cache_key = f"{self.cache_prefix}burst:{request_id}:{role}"
        
        # Get burst data
        burst_data = cache.get(burst_cache_key, {
            'count': 0,
            'window_start': burst_window_start.isoformat()
        })
        
        try:
            if isinstance(burst_data, str):
                # Handle legacy string format
                current_burst_count = int(burst_data)
            else:
                current_burst_count = burst_data.get('count', 0)
        except (ValueError, TypeError):
            current_burst_count = 0
        
        # Check if within burst window
        if current_burst_count >= self.burst_limit:
            return False
        
        # Update burst cache
        cache.set(burst_cache_key, {
            'count': current_burst_count + 1,
            'window_start': burst_window_start.isoformat()
        }, timeout=self.burst_window)
        
        return True
    
    def get_rate_limit_headers(self, request: HttpRequest) -> Dict[str, str]:
        """
        Get rate limit headers for response.
        
        Args:
            request: Django HTTP request object
            
        Returns:
            Dict[str, str]: Rate limit headers
        """
        try:
            user = getattr(request, 'user', None)
            role = self._get_user_role(user)
            request_id = self._get_request_identifier(request)
            
            # Get current limits
            endpoint_limit = self._get_endpoint_limit(request)
            rate_limit = endpoint_limit or self.limits.get(role, self.limits.get('anonymous', 100))
            
            # Get current usage
            cache_key = f"{self.cache_prefix}{request_id}:{role}"
            request_data = cache.get(cache_key, {'count': 0})
            
            try:
                if isinstance(request_data, str):
                    current_count = int(request_data)
                else:
                    current_count = request_data.get('count', 0)
            except (ValueError, TypeError):
                current_count = 0
            
            remaining = max(0, rate_limit - current_count)
            reset_time = timezone.now() + timedelta(minutes=1)
            
            return {
                'X-RateLimit-Limit': str(rate_limit),
                'X-RateLimit-Remaining': str(remaining),
                'X-RateLimit-Reset': str(int(reset_time.timestamp())),
                'X-RateLimit-Role': role,
            }
            
        except Exception as e:
            logger.error(f"Error getting rate limit headers: {e}")
            return {}
    
    def reset_rate_limit(self, request_id: str, role: str) -> bool:
        """
        Reset rate limit for a specific user/IP.
        
        Args:
            request_id: Request identifier
            role: User role
            
        Returns:
            bool: True if reset successful
        """
        try:
            cache_key = f"{self.cache_prefix}{request_id}:{role}"
            burst_cache_key = f"{self.cache_prefix}burst:{request_id}:{role}"
            
            # Delete cache entries
            cache.delete(cache_key)
            cache.delete(burst_cache_key)
            
            logger.info(f"Rate limit reset for {request_id} ({role})")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting rate limit: {e}")
            return False
    
    def get_rate_limit_stats(self, request_id: str, role: str) -> Dict[str, Any]:
        """
        Get rate limit statistics for a user/IP.
        
        Args:
            request_id: Request identifier
            role: User role
            
        Returns:
            Dict[str, Any]: Rate limit statistics
        """
        try:
            cache_key = f"{self.cache_prefix}{request_id}:{role}"
            request_data = cache.get(cache_key, {'count': 0})
            
            burst_cache_key = f"{self.cache_prefix}burst:{request_id}:{role}"
            burst_data = cache.get(burst_cache_key, {'count': 0})
            
            try:
                if isinstance(request_data, str):
                    current_count = int(request_data)
                else:
                    current_count = request_data.get('count', 0)
                
                if isinstance(burst_data, str):
                    burst_count = int(burst_data)
                else:
                    burst_count = burst_data.get('count', 0)
            except (ValueError, TypeError):
                current_count = 0
                burst_count = 0
            
            endpoint_limit = self.limits.get(role, self.limits.get('anonymous', 100))
            
            return {
                'request_id': request_id,
                'role': role,
                'current_requests': current_count,
                'limit': endpoint_limit,
                'remaining': max(0, endpoint_limit - current_count),
                'burst_requests': burst_count,
                'burst_limit': self.burst_limit,
                'burst_remaining': max(0, self.burst_limit - burst_count),
                'reset_time': (timezone.now() + timedelta(minutes=1)).isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error getting rate limit stats: {e}")
            return {}


class UserActionThrottle:
    """
    Specialized throttling for user actions (award badges, update streaks, etc.).
    
    Provides stricter limits for actions that modify game state.
    """
    
    def __init__(self):
        # Action-specific limits (requests per hour)
        self.action_limits = {
            'badge_award': 10,           # 10 badge awards per hour
            'streak_update': 60,         # 60 streak updates per hour
            'challenge_complete': 30,    # 30 challenge completions per hour
            'level_progress': 20,        # 20 level progress updates per hour
        }
        
        self.cache_timeout = 3600  # 1 hour
        self.cache_prefix = 'gamification_action_throttle:'
    
    def allow_action(self, user_id: str, action_type: str) -> bool:
        """
        Check if user action should be allowed.
        
        Args:
            user_id: User identifier
            action_type: Type of action
            
        Returns:
            bool: True if action is allowed, False otherwise
        """
        try:
            # Get limit for action type
            limit = self.action_limits.get(action_type, 30)
            
            # Get cache key
            cache_key = f"{self.cache_prefix}{user_id}:{action_type}"
            
            # Get current count
            current_count = cache.get(cache_key, 0)
            
            # Check limit
            if current_count >= limit:
                logger.warning(f"Action limit exceeded for user {user_id} ({action_type}): {current_count}/{limit}")
                return False
            
            # Increment count
            cache.set(cache_key, current_count + 1, timeout=self.cache_timeout)
            
            return True
            
        except Exception as e:
            logger.error(f"Error in action throttling: {e}")
            return True
    
    def get_action_stats(self, user_id: str, action_type: str) -> Dict[str, Any]:
        """
        Get action statistics for a user.
        
        Args:
            user_id: User identifier
            action_type: Type of action
            
        Returns:
            Dict[str, Any]: Action statistics
        """
        try:
            cache_key = f"{self.cache_prefix}{user_id}:{action_type}"
            current_count = cache.get(cache_key, 0)
            limit = self.action_limits.get(action_type, 30)
            
            return {
                'user_id': user_id,
                'action_type': action_type,
                'current_count': current_count,
                'limit': limit,
                'remaining': max(0, limit - current_count),
                'reset_time': (timezone.now() + timedelta(hours=1)).isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error getting action stats: {e}")
            return {}


class GlobalThrottle:
    """
    Global rate limiting for system-wide protection.
    
    Provides overall system limits to prevent abuse.
    """
    
    def __init__(self):
        # Global limits (requests per minute)
        self.global_limits = {
            'badge_operations': 1000,      # 1000 badge operations per minute
            'streak_operations': 2000,      # 2000 streak operations per minute
            'challenge_operations': 1500,   # 1500 challenge operations per minute
            'level_operations': 500,        # 500 level operations per minute
        }
        
        self.cache_timeout = 60
        self.cache_prefix = 'gamification_global_throttle:'
    
    def allow_operation(self, operation_type: str) -> bool:
        """
        Check if global operation should be allowed.
        
        Args:
            operation_type: Type of operation
            
        Returns:
            bool: True if operation is allowed, False otherwise
        """
        try:
            # Get limit for operation type
            limit = self.global_limits.get(operation_type, 1000)
            
            # Get cache key
            cache_key = f"{self.cache_prefix}{operation_type}"
            
            # Get current count
            current_count = cache.get(cache_key, 0)
            
            # Check limit
            if current_count >= limit:
                logger.warning(f"Global limit exceeded for {operation_type}: {current_count}/{limit}")
                return False
            
            # Increment count
            cache.set(cache_key, current_count + 1, timeout=self.cache_timeout)
            
            return True
            
        except Exception as e:
            logger.error(f"Error in global throttling: {e}")
            return True
    
    def get_global_stats(self) -> Dict[str, Any]:
        """
        Get global throttling statistics.
        
        Returns:
            Dict[str, Any]: Global statistics
        """
        try:
            stats = {}
            
            for operation_type, limit in self.global_limits.items():
                cache_key = f"{self.cache_prefix}{operation_type}"
                current_count = cache.get(cache_key, 0)
                
                stats[operation_type] = {
                    'current_count': current_count,
                    'limit': limit,
                    'remaining': max(0, limit - current_count),
                    'utilization': (current_count / limit) * 100 if limit > 0 else 0,
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting global stats: {e}")
            return {}


# Decorator for easy throttling application
def throttle_action(action_type: str):
    """
    Decorator for throttling user actions.
    
    Args:
        action_type: Type of action to throttle
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Try to get user_id from first argument (usually self.request.user.id)
            user_id = None
            if args and hasattr(args[0], 'request'):
                user_id = getattr(args[0].request.user, 'id', None)
            elif args and hasattr(args[0], 'user'):
                user_id = getattr(args[0].user, 'id', None)
            
            if user_id:
                throttle = UserActionThrottle()
                if not throttle.allow_action(str(user_id), action_type):
                    raise GamificationServiceError(f"Rate limit exceeded for action: {action_type}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Middleware for automatic throttling
class GamificationThrottleMiddleware:
    """
    Django middleware for automatic rate limiting.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.throttle = GamificationRateThrottle()
    
    def __call__(self, request):
        # Apply rate limiting
        if not self.throttle.allow_request(request):
            import json
            from django.http import HttpResponse
            return HttpResponse(
                json.dumps({'error': 'Rate limit exceeded'}),
                status=429,
                content_type='application/json'
            )
        
        response = self.get_response(request)
        
        # Add rate limit headers
        headers = self.throttle.get_rate_limit_headers(request)
        for key, value in headers.items():
            response[key] = value
        
        return response
