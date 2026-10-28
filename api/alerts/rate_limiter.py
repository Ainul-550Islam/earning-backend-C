"""
Rate Limiter for alerts app - Advanced rate limiting system
"""
from typing import Dict, List, Any, Optional, Union
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
import logging
import time
import json
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class RateLimitType(Enum):
    """Rate limit type enumeration"""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"


class RateLimitPeriod(Enum):
    """Rate limit period enumeration"""
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class RateLimitResult:
    """Represents rate limit check result"""
    
    def __init__(self, allowed: bool, limit: int, remaining: int, 
                 reset_time: datetime, retry_after: int = None):
        self.allowed = allowed
        self.limit = limit
        self.remaining = remaining
        self.reset_time = reset_time
        self.retry_after = retry_after
        self.timestamp = timezone.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'allowed': self.allowed,
            'limit': self.limit,
            'remaining': self.remaining,
            'reset_time': self.reset_time.isoformat(),
            'retry_after': self.retry_after,
            'timestamp': self.timestamp.isoformat()
        }


class FixedWindowRateLimiter:
    """Fixed window rate limiter"""
    
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        
    def check_limit(self, key: str) -> RateLimitResult:
        """Check rate limit for key"""
        try:
            current_time = int(time.time())
            window_start = current_time - (current_time % self.window_seconds)
            window_end = window_start + self.window_seconds
            
            # Get current count
            cache_key = f"rate_limit:fixed:{key}:{window_start}"
            current_count = cache.get(cache_key, 0)
            
            # Check if limit exceeded
            if current_count >= self.limit:
                return RateLimitResult(
                    allowed=False,
                    limit=self.limit,
                    remaining=0,
                    reset_time=timezone.datetime.fromtimestamp(window_end),
                    retry_after=window_end - current_time
                )
            
            # Increment counter
            cache.set(cache_key, current_count + 1, timeout=self.window_seconds)
            
            return RateLimitResult(
                allowed=True,
                limit=self.limit,
                remaining=self.limit - current_count - 1,
                reset_time=timezone.datetime.fromtimestamp(window_end)
            )
            
        except Exception as e:
            logger.error(f"Fixed window rate limit error: {e}")
            return RateLimitResult(
                allowed=True,
                limit=self.limit,
                remaining=self.limit,
                reset_time=timezone.now() + timedelta(seconds=self.window_seconds)
            )


class SlidingWindowRateLimiter:
    """Sliding window rate limiter"""
    
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        
    def check_limit(self, key: str) -> RateLimitResult:
        """Check rate limit for key"""
        try:
            current_time = int(time.time())
            
            # Get all timestamps in window
            cache_key = f"rate_limit:sliding:{key}"
            timestamps = cache.get(cache_key, [])
            
            # Filter to current window
            window_start = current_time - self.window_seconds
            timestamps = [ts for ts in timestamps if ts > window_start]
            
            # Check if limit exceeded
            if len(timestamps) >= self.limit:
                # Find oldest timestamp to calculate reset time
                oldest_timestamp = min(timestamps)
                reset_time = oldest_timestamp + self.window_seconds
                
                return RateLimitResult(
                    allowed=False,
                    limit=self.limit,
                    remaining=0,
                    reset_time=timezone.datetime.fromtimestamp(reset_time),
                    retry_after=reset_time - current_time
                )
            
            # Add current timestamp
            timestamps.append(current_time)
            cache.set(cache_key, timestamps, timeout=self.window_seconds)
            
            return RateLimitResult(
                allowed=True,
                limit=self.limit,
                remaining=self.limit - len(timestamps),
                reset_time=timezone.datetime.fromtimestamp(window_start + self.window_seconds)
            )
            
        except Exception as e:
            logger.error(f"Sliding window rate limit error: {e}")
            return RateLimitResult(
                allowed=True,
                limit=self.limit,
                remaining=self.limit,
                reset_time=timezone.now() + timedelta(seconds=self.window_seconds)
            )


class TokenBucketRateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, capacity: int, refill_rate: float, refill_period: int = 1):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.refill_period = refill_period  # seconds
        
    def check_limit(self, key: str) -> RateLimitResult:
        """Check rate limit for key"""
        try:
            current_time = int(time.time())
            cache_key = f"rate_limit:token_bucket:{key}"
            
            # Get current bucket state
            bucket_data = cache.get(cache_key, {
                'tokens': self.capacity,
                'last_refill': current_time
            })
            
            # Calculate tokens to add
            time_passed = current_time - bucket_data['last_refill']
            tokens_to_add = (time_passed // self.refill_period) * self.refill_rate
            
            # Update tokens
            new_tokens = min(bucket_data['tokens'] + tokens_to_add, self.capacity)
            last_refill = bucket_data['last_refill'] + (time_passed // self.refill_period) * self.refill_period
            
            # Check if we have tokens
            if new_tokens < 1:
                # Calculate when next token will be available
                time_to_next_token = self.refill_period / self.refill_rate
                next_available = current_time + time_to_next_token
                
                return RateLimitResult(
                    allowed=False,
                    limit=self.capacity,
                    remaining=0,
                    reset_time=timezone.datetime.fromtimestamp(next_available),
                    retry_after=int(time_to_next_token)
                )
            
            # Consume one token
            new_tokens -= 1
            
            # Update bucket
            bucket_data = {
                'tokens': new_tokens,
                'last_refill': last_refill
            }
            cache.set(cache_key, bucket_data, timeout=3600)  # 1 hour timeout
            
            return RateLimitResult(
                allowed=True,
                limit=self.capacity,
                remaining=int(new_tokens),
                reset_time=timezone.datetime.fromtimestamp(last_refill + self.refill_period)
            )
            
        except Exception as e:
            logger.error(f"Token bucket rate limit error: {e}")
            return RateLimitResult(
                allowed=True,
                limit=self.capacity,
                remaining=self.capacity,
                reset_time=timezone.now() + timedelta(seconds=self.refill_period)
            )


class LeakyBucketRateLimiter:
    """Leaky bucket rate limiter"""
    
    def __init__(self, capacity: int, leak_rate: float):
        self.capacity = capacity
        self.leak_rate = leak_rate  # tokens per second
        
    def check_limit(self, key: str) -> RateLimitResult:
        """Check rate limit for key"""
        try:
            current_time = int(time.time())
            cache_key = f"rate_limit:leaky_bucket:{key}"
            
            # Get current bucket state
            bucket_data = cache.get(cache_key, {
                'volume': 0,
                'last_leak': current_time
            })
            
            # Calculate leak
            time_passed = current_time - bucket_data['last_leak']
            leaked = time_passed * self.leak_rate
            
            # Update volume
            new_volume = max(0, bucket_data['volume'] - leaked)
            
            # Check if bucket is full
            if new_volume >= self.capacity:
                # Calculate when bucket will have space
                time_to_space = (new_volume - self.capacity + 1) / self.leak_rate
                next_available = current_time + time_to_space
                
                return RateLimitResult(
                    allowed=False,
                    limit=self.capacity,
                    remaining=0,
                    reset_time=timezone.datetime.fromtimestamp(next_available),
                    retry_after=int(time_to_space)
                )
            
            # Add to bucket
            new_volume += 1
            
            # Update bucket
            bucket_data = {
                'volume': new_volume,
                'last_leak': current_time
            }
            cache.set(cache_key, bucket_data, timeout=3600)
            
            return RateLimitResult(
                allowed=True,
                limit=self.capacity,
                remaining=max(0, self.capacity - new_volume),
                reset_time=timezone.datetime.fromtimestamp(current_time + 60)  # Approximate
            )
            
        except Exception as e:
            logger.error(f"Leaky bucket rate limit error: {e}")
            return RateLimitResult(
                allowed=True,
                limit=self.capacity,
                remaining=self.capacity,
                reset_time=timezone.now() + timedelta(seconds=60)
            )


class RateLimiter:
    """Main rate limiting system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', True)
        self.default_type = RateLimitType(config.get('default_type', 'sliding_window'))
        self.global_limits = config.get('global_limits', {})
        self.user_limits = config.get('user_limits', {})
        self.ip_limits = config.get('ip_limits', {})
        self.endpoint_limits = config.get('endpoint_limits', {})
        
        # Initialize limiters
        self.limiters = {}
        self._initialize_limiters()
        
    def _initialize_limiters(self):
        """Initialize rate limiters"""
        limiter_configs = self.config.get('limiters', {})
        
        for name, limiter_config in limiter_configs.items():
            limiter_type = RateLimitType(limiter_config.get('type', 'sliding_window'))
            limit = limiter_config.get('limit', 100)
            window = limiter_config.get('window_seconds', 3600)
            
            if limiter_type == RateLimitType.FIXED_WINDOW:
                limiter = FixedWindowRateLimiter(limit, window)
            elif limiter_type == RateLimitType.SLIDING_WINDOW:
                limiter = SlidingWindowRateLimiter(limit, window)
            elif limiter_type == RateLimitType.TOKEN_BUCKET:
                capacity = limiter_config.get('capacity', limit)
                refill_rate = limiter_config.get('refill_rate', limit / window)
                limiter = TokenBucketRateLimiter(capacity, refill_rate)
            elif limiter_type == RateLimitType.LEAKY_BUCKET:
                capacity = limiter_config.get('capacity', limit)
                leak_rate = limiter_config.get('leak_rate', limit / window)
                limiter = LeakyBucketRateLimiter(capacity, leak_rate)
            else:
                logger.error(f"Unknown rate limiter type: {limiter_type}")
                continue
            
            self.limiters[name] = limiter
            logger.info(f"Initialized rate limiter: {name}")
    
    def check_rate_limit(self, key: str, limiter_name: str = None, 
                        user_id: str = None, ip_address: str = None,
                        endpoint: str = None) -> RateLimitResult:
        """Check rate limit for request"""
        if not self.enabled:
            return RateLimitResult(
                allowed=True,
                limit=float('inf'),
                remaining=float('inf'),
                reset_time=timezone.now()
            )
        
        try:
            # Determine which limiter to use
            limiter_name = limiter_name or self._get_limiter_name(user_id, ip_address, endpoint)
            limiter = self.limiters.get(limiter_name)
            
            if not limiter:
                logger.warning(f"Rate limiter {limiter_name} not found")
                return RateLimitResult(
                    allowed=True,
                    limit=float('inf'),
                    remaining=float('inf'),
                    reset_time=timezone.now()
                )
            
            # Create cache key
            cache_key = self._make_cache_key(key, user_id, ip_address, endpoint)
            
            # Check rate limit
            result = limiter.check_limit(cache_key)
            
            # Add metadata
            result.metadata = {
                'limiter_name': limiter_name,
                'cache_key': cache_key,
                'user_id': user_id,
                'ip_address': ip_address,
                'endpoint': endpoint
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            return RateLimitResult(
                allowed=True,
                limit=float('inf'),
                remaining=float('inf'),
                reset_time=timezone.now()
            )
    
    def _get_limiter_name(self, user_id: str = None, ip_address: str = None,
                         endpoint: str = None) -> str:
        """Determine which limiter to use"""
        # Check endpoint-specific limits
        if endpoint and endpoint in self.endpoint_limits:
            return self.endpoint_limits[endpoint]
        
        # Check user-specific limits
        if user_id and user_id in self.user_limits:
            return self.user_limits[user_id]
        
        # Check IP-specific limits
        if ip_address and ip_address in self.ip_limits:
            return self.ip_limits[ip_address]
        
        # Use default
        return self.default_type.value
    
    def _make_cache_key(self, key: str, user_id: str = None, 
                      ip_address: str = None, endpoint: str = None) -> str:
        """Create cache key for rate limiting"""
        parts = [key]
        
        if user_id:
            parts.append(f"user:{user_id}")
        
        if ip_address:
            parts.append(f"ip:{ip_address}")
        
        if endpoint:
            parts.append(f"endpoint:{endpoint}")
        
        return ":".join(parts)
    
    def add_limiter(self, name: str, limiter: Union[FixedWindowRateLimiter, SlidingWindowRateLimiter, 
                                                   TokenBucketRateLimiter, LeakyBucketRateLimiter]):
        """Add custom rate limiter"""
        self.limiters[name] = limiter
        logger.info(f"Added rate limiter: {name}")
    
    def remove_limiter(self, name: str):
        """Remove rate limiter"""
        if name in self.limiters:
            del self.limiters[name]
            logger.info(f"Removed rate limiter: {name}")
    
    def get_limiter_stats(self, limiter_name: str) -> Dict[str, Any]:
        """Get statistics for specific limiter"""
        limiter = self.limiters.get(limiter_name)
        if not limiter:
            return {'error': f'Limiter {limiter_name} not found'}
        
        # This would need to be implemented by each limiter type
        # For now, return basic info
        return {
            'limiter_name': limiter_name,
            'type': type(limiter).__name__,
            'config': getattr(limiter, '__dict__', {})
        }
    
    def clear_rate_limits(self, key: str = None, user_id: str = None,
                        ip_address: str = None, endpoint: str = None):
        """Clear rate limits"""
        try:
            if key:
                # Clear specific key
                cache_key = self._make_cache_key(key, user_id, ip_address, endpoint)
                cache.delete(cache_key)
            else:
                # Clear all rate limits (be careful!)
                keys_to_delete = []
                
                # This is backend-dependent
                # For now, just log
                logger.warning("Clearing all rate limits - this may not work with all backends")
                
        except Exception as e:
            logger.error(f"Error clearing rate limits: {e}")
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get rate limiting system statistics"""
        return {
            'enabled': self.enabled,
            'default_type': self.default_type.value,
            'total_limiters': len(self.limiters),
            'limiter_names': list(self.limiters.keys()),
            'global_limits': self.global_limits,
            'user_limits_count': len(self.user_limits),
            'ip_limits_count': len(self.ip_limits),
            'endpoint_limits_count': len(self.endpoint_limits),
            'timestamp': timezone.now().isoformat()
        }


# Global rate limiter
rate_limiter = None


def get_rate_limiter() -> Optional[RateLimiter]:
    """Get the global rate limiter"""
    return rate_limiter


def initialize_rate_limiter():
    """Initialize rate limiter from settings"""
    from django.conf import settings
    
    global rate_limiter
    
    config = getattr(settings, 'RATE_LIMITER_CONFIG', {
        'enabled': True,
        'default_type': 'sliding_window',
        'global_limits': {
            'default': {'limit': 1000, 'window_seconds': 3600},
            'critical': {'limit': 100, 'window_seconds': 300},
            'emergency': {'limit': 50, 'window_seconds': 60}
        },
        'user_limits': {
            'premium': 'premium_limiter',
            'basic': 'basic_limiter'
        },
        'limiters': {
            'default': {
                'type': 'sliding_window',
                'limit': 1000,
                'window_seconds': 3600
            },
            'premium_limiter': {
                'type': 'token_bucket',
                'capacity': 5000,
                'refill_rate': 1.4  # ~5000 per hour
            },
            'basic_limiter': {
                'type': 'fixed_window',
                'limit': 500,
                'window_seconds': 3600
            },
            'critical_limiter': {
                'type': 'sliding_window',
                'limit': 100,
                'window_seconds': 300
            },
            'emergency_limiter': {
                'type': 'token_bucket',
                'capacity': 50,
                'refill_rate': 0.83  # ~50 per minute
            }
        }
    })
    
    try:
        rate_limiter = RateLimiter(config)
        logger.info("Rate limiter initialized")
    except Exception as e:
        logger.error(f"Error initializing rate limiter: {e}")


# Decorator for rate limiting
def rate_limit(limiter_name: str = None, key_func: callable = None):
    """Decorator for rate limiting function calls"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get rate limiter
            rl = get_rate_limiter()
            if not rl:
                return func(*args, **kwargs)
            
            # Generate key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = f"{func.__module__}.{func.__name__}"
            
            # Get user and IP from request if available
            user_id = None
            ip_address = None
            
            # Try to get from Django request
            try:
                from django.contrib.auth.models import AnonymousUser
                from django.http import HttpRequest
                
                # This is a simplified approach
                # In practice, you'd get this from the request object
                pass
            except ImportError:
                pass
            
            # Check rate limit
            result = rl.check_rate_limit(key, limiter_name, user_id, ip_address)
            
            if not result.allowed:
                from django.http import HttpResponseTooManyRequests
                return HttpResponseTooManyRequests(
                    json.dumps({
                        'error': 'Rate limit exceeded',
                        'limit': result.limit,
                        'remaining': result.remaining,
                        'reset_time': result.reset_time.isoformat(),
                        'retry_after': result.retry_after
                    }),
                    content_type='application/json'
                )
            
            # Execute function
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Initialize on module import
try:
    initialize_rate_limiter()
except Exception as e:
    logger.error(f"Error initializing rate limiter: {e}")
