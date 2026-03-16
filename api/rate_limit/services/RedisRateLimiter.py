import time
import redis
import json
from typing import Optional, Dict, Any, List, Tuple
from django.conf import settings
from django.core.cache import cache
from .TokenBucket import TokenBucket, LeakyBucket, FixedWindowCounter


class RedisRateLimiter:
    """Redis-based rate limiter for earning application"""
    
    def __init__(self):
        self.redis_client = self._get_redis_client()
    
    def _get_redis_client(self):
        """Get Redis client connection"""
        try:
            # Try to get from Django cache first
            if hasattr(cache, 'client'):
                return cache.client.get_client()
            
            # Use REDIS_URL if available
            redis_url = getattr(settings, 'REDIS_URL', None)
            if redis_url:
                return redis.from_url(redis_url, decode_responses=True)
            return redis.Redis(
                host=getattr(settings, 'REDIS_HOST', 'localhost'),
                port=getattr(settings, 'REDIS_PORT', 6379),
                db=getattr(settings, 'REDIS_DB', 0),
                password=getattr(settings, 'REDIS_PASSWORD', None),
                decode_responses=True
            )
        except:
            # Fallback to Django cache
            return cache
    
    def _get_identifier(self, request, config) -> str:
        """Get unique identifier for rate limiting"""
        identifiers = []
        
        if config.rate_limit_type == 'user' and request.user.is_authenticated:
            identifiers.append(f"user:{request.user.id}")
        
        if config.rate_limit_type == 'ip':
            identifiers.append(f"ip:{self._get_client_ip(request)}")
        
        if config.rate_limit_type == 'endpoint' and config.endpoint:
            identifiers.append(f"endpoint:{config.endpoint}")
        
        if config.rate_limit_type == 'global':
            identifiers.append("global")
        
        if config.rate_limit_type == 'referral':
            identifiers.append(f"referral:{request.user.referral_code}")
        
        if config.rate_limit_type == 'task' and config.task_type:
            identifiers.append(f"task:{config.task_type}")
        
        # Add additional context for earning app
        if hasattr(request, 'task_id'):
            identifiers.append(f"task_id:{request.task_id}")
        
        if hasattr(request, 'offer_id'):
            identifiers.append(f"offer_id:{request.offer_id}")
        
        return ":".join(identifiers)
    
    def _get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def sliding_window_log(self, identifier: str, window_seconds: int, limit: int) -> tuple[bool, dict]:
        """
        Sliding window log algorithm implementation
        
        Args:
            identifier: Unique identifier for the window
            window_seconds: Window size in seconds
            limit: Maximum requests in the window
            
        Returns:
            tuple: (is_allowed, metadata)
        """
        current_time = time.time()
        window_key = f"sliding_window:{identifier}"
        
        # Get existing timestamps
        timestamps = self.redis_client.lrange(window_key, 0, -1)
        timestamps = [float(ts) for ts in timestamps]
        
        # Remove timestamps outside the window
        cutoff = current_time - window_seconds
        valid_timestamps = [ts for ts in timestamps if ts > cutoff]
        
        # Check if under limit
        if len(valid_timestamps) < limit:
            # Add current timestamp
            self.redis_client.lpush(window_key, current_time)
            # Trim list and set expiration
            self.redis_client.ltrim(window_key, 0, limit - 1)
            self.redis_client.expire(window_key, window_seconds)
            
            return True, {
                'current_count': len(valid_timestamps) + 1,
                'limit': limit,
                'remaining': limit - (len(valid_timestamps) + 1),
                'reset_time': min(valid_timestamps) + window_seconds if valid_timestamps else current_time + window_seconds
            }
        
        return False, {
            'current_count': len(valid_timestamps),
            'limit': limit,
            'remaining': 0,
            'reset_time': min(valid_timestamps) + window_seconds
        }
    
    def check_rate_limit(self, request, config) -> tuple[bool, dict]:
        """
        Check rate limit for a request
        
        Args:
            request: Django request object
            config: RateLimitConfig object
            
        Returns:
            tuple: (is_allowed, metadata)
        """
        identifier = self._get_identifier(request, config)
        
        if not identifier:
            return True, {'reason': 'no_identifier'}
        
        # Convert time unit to seconds
        TIME_MAP = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
        window_seconds = TIME_MAP.get(config.time_unit, 3600) * config.time_value
        limit = config.requests_per_unit
        
        # Use sliding window algorithm
        return self.sliding_window_log(
            identifier=f"{identifier}:{config.id}",
            window_seconds=window_seconds,
            limit=limit
        )
    
    def check_multiple_limits(self, request, configs: List) -> tuple[bool, list]:
        """
        Check multiple rate limits
        
        Args:
            request: Django request object
            configs: List of RateLimitConfig objects
            
        Returns:
            tuple: (is_allowed, failed_configs)
        """
        failed_configs = []
        
        for config in configs:
            if config.is_active:
                is_allowed, metadata = self.check_rate_limit(request, config)
                if not is_allowed:
                    failed_configs.append({
                        'config': config,
                        'metadata': metadata
                    })
        
        is_allowed = len(failed_configs) == 0
        return is_allowed, failed_configs
    
    def get_rate_limit_info(self, identifier: str, config) -> dict:
        """Get current rate limit information"""
        TIME_MAP = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
        window_seconds = TIME_MAP.get(config.time_unit, 3600) * config.time_value
        limit = config.requests_per_unit
        
        full_identifier = f"{identifier}:{config.id}"
        window_key = f"sliding_window:{full_identifier}"
        
        current_time = time.time()
        cutoff = current_time - window_seconds
        
        timestamps = self.redis_client.lrange(window_key, 0, -1)
        timestamps = [float(ts) for ts in timestamps]
        valid_timestamps = [ts for ts in timestamps if ts > cutoff]
        
        return {
            'current': len(valid_timestamps),
            'limit': limit,
            'remaining': max(0, limit - len(valid_timestamps)),
            'reset_time': min(valid_timestamps) + window_seconds if valid_timestamps else current_time,
            'window_size': window_seconds
        }
    
    def reset_rate_limit(self, identifier: str, config):
        """Reset rate limit for an identifier"""
        full_identifier = f"{identifier}:{config.id}"
        window_key = f"sliding_window:{full_identifier}"
        self.redis_client.delete(window_key)
    
    # Earning app specific methods
    def check_task_rate_limit(self, user_id: int, task_type: str, daily_limit: int) -> tuple[bool, dict]:
        """Check daily task completion limit"""
        today = time.strftime("%Y-%m-%d")
        key = f"task_limit:{user_id}:{task_type}:{today}"
        
        current_count = self.redis_client.incr(key)
        if current_count == 1:
            # Set expiration to end of day
            remaining_seconds = self._seconds_until_midnight()
            self.redis_client.expire(key, remaining_seconds)
        
        is_allowed = current_count <= daily_limit
        
        return is_allowed, {
            'current': current_count,
            'limit': daily_limit,
            'remaining': max(0, daily_limit - current_count),
            'reset_time': self._get_midnight_timestamp()
        }
    
    def check_offer_wall_limit(self, user_id: int, offer_wall: str, hourly_limit: int) -> tuple[bool, dict]:
        """Check offer wall access limit"""
        current_hour = int(time.time() // 3600)
        key = f"offer_wall:{user_id}:{offer_wall}:{current_hour}"
        
        current_count = self.redis_client.incr(key)
        if current_count == 1:
            self.redis_client.expire(key, 3600)  # 1 hour
        
        is_allowed = current_count <= hourly_limit
        
        return is_allowed, {
            'current': current_count,
            'limit': hourly_limit,
            'remaining': max(0, hourly_limit - current_count),
            'reset_time': (current_hour + 1) * 3600
        }
    
    def check_referral_click_limit(self, ip_address: str, daily_limit: int = 50) -> tuple[bool, dict]:
        """Check daily referral click limit per IP"""
        today = time.strftime("%Y-%m-%d")
        key = f"referral_clicks:{ip_address}:{today}"
        
        current_count = self.redis_client.incr(key)
        if current_count == 1:
            remaining_seconds = self._seconds_until_midnight()
            self.redis_client.expire(key, remaining_seconds)
        
        is_allowed = current_count <= daily_limit
        
        return is_allowed, {
            'current': current_count,
            'limit': daily_limit,
            'remaining': max(0, daily_limit - current_count),
            'reset_time': self._get_midnight_timestamp()
        }
    
    # Helper methods
    def _seconds_until_midnight(self) -> int:
        """Calculate seconds until midnight"""
        from datetime import datetime, timedelta
        now = datetime.now()
        midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        return int((midnight - now).total_seconds())
    
    def _get_midnight_timestamp(self) -> int:
        """Get timestamp for next midnight"""
        from datetime import datetime, timedelta
        now = datetime.now()
        midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        return int(midnight.timestamp())