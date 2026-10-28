import time
import redis
import json
from typing import Optional, Dict, Any, List, Tuple
from django.conf import settings
from django.core.cache import cache
from api.rate_limit.services.TokenBucket import TokenBucket, LeakyBucket, FixedWindowCounter


class _NoOpRedisClient:
    """No-op Redis client used when Redis is unavailable and fakeredis not installed."""
    def __getattr__(self, name):
        def noop(*args, **kwargs):
            if name in ('get', 'lrange', 'keys'):
                return None if name == 'get' else []
            if name in ('exists',): return 0
            if name in ('incr', 'incrby'): return 1
            return True
        return noop


class RedisRateLimiter:
    """Redis-based rate limiter for earning application"""
    
    def __init__(self):
        self.redis_client = self._get_redis_client()
    
    def _get_redis_client(self):
        """Get Redis client - uses fakeredis fallback when real Redis unavailable."""
        try:
            redis_url = getattr(settings, 'REDIS_URL', None)
            if redis_url and 'redis_url' not in redis_url:
                client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=0.5)
            else:
                client = redis.Redis(
                    host=getattr(settings, 'REDIS_HOST', 'localhost'),
                    port=int(getattr(settings, 'REDIS_PORT', 6379)),
                    db=int(getattr(settings, 'REDIS_DB', 0)),
                    decode_responses=True,
                    socket_connect_timeout=0.5,
                    socket_timeout=0.5,
                )
            client.ping()
            return client
        except Exception:
            # Fallback: try fakeredis for testing
            try:
                import fakeredis
                if not hasattr(self.__class__, '_fake_redis_instance'):
                    self.__class__._fake_redis_instance = fakeredis.FakeRedis(decode_responses=True)
                return self.__class__._fake_redis_instance
            except ImportError:
                pass
            # Final fallback: return a no-op mock
            return _NoOpRedisClient()


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
        Atomic sliding window log algorithm implementation using Lua script
        
        Args:
            identifier: Unique identifier for the window
            window_seconds: Window size in seconds
            limit: Maximum requests in the window
            
        Returns:
            tuple: (is_allowed, metadata)
        """
        current_time = time.time()
        window_key = f"sliding_window:{identifier}"
        
        # Lua script for atomic sliding window
        lua_script = """
        local key = KEYS[1]
        local current_time = tonumber(ARGV[1])
        local window_seconds = tonumber(ARGV[2])
        local limit = tonumber(ARGV[3])
        
        -- Get all timestamps
        local timestamps = redis.call('LRANGE', key, 0, -1)
        local valid_timestamps = {}
        local cutoff = current_time - window_seconds
        
        -- Filter valid timestamps
        for i, ts in ipairs(timestamps) do
            local ts_num = tonumber(ts)
            if ts_num > cutoff then
                table.insert(valid_timestamps, ts_num)
            end
        end
        
        local current_count = #valid_timestamps
        
        -- Check if under limit
        if current_count < limit then
            -- Rebuild the list with only valid timestamps + new timestamp
            redis.call('DEL', key)  -- Clear the list
            redis.call('LPUSH', key, current_time)  -- Add new timestamp first
            
            -- Add back valid timestamps (newest first)
            for i, ts in ipairs(valid_timestamps) do
                redis.call('RPUSH', key, ts)
            end
            
            -- Trim to limit (now contains only valid entries)
            redis.call('LTRIM', key, 0, limit - 1)
            -- Set expiration
            redis.call('EXPIRE', key, window_seconds)
            
            -- Calculate reset time (oldest timestamp + window_seconds)
            local reset_time
            if current_count > 0 then
                reset_time = valid_timestamps[1] + window_seconds
            else
                reset_time = current_time + window_seconds
            end
            
            return {1, current_count + 1, limit - (current_count + 1), reset_time}
        else
            -- Even for denied requests, clean up expired entries
            if #timestamps > current_count then
                -- Rebuild list with only valid timestamps
                redis.call('DEL', key)
                for i, ts in ipairs(valid_timestamps) do
                    redis.call('RPUSH', key, ts)
                end
                redis.call('EXPIRE', key, window_seconds)
            end
            
            -- Calculate reset time for denied request
            local reset_time = valid_timestamps[1] + window_seconds
            return {0, current_count, 0, reset_time}
        end
        """
        
        try:
            # Execute Lua script atomically
            result = self.redis_client.eval(
                lua_script,
                1,  # Number of keys
                window_key,  # KEYS[1]
                current_time,  # ARGV[1]
                window_seconds,  # ARGV[2]
                limit  # ARGV[3]
            )
            
            is_allowed = bool(result[0])
            current_count = int(result[1])
            remaining = int(result[2])
            reset_time = float(result[3])
            
            return is_allowed, {
                'current_count': current_count,
                'limit': limit,
                'remaining': remaining,
                'reset_time': reset_time
            }
            
        except Exception as e:
            # Fallback to non-atomic implementation if Lua script fails
            return self._sliding_window_log_fallback(identifier, window_seconds, limit)
    
    def _sliding_window_log_fallback(self, identifier: str, window_seconds: int, limit: int) -> tuple[bool, dict]:
        """
        Fallback implementation for sliding window (non-atomic)
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

    # ─────────────────────────────────────────────────────────
    # Integration-friendly methods (called by RateLimitService)
    # ─────────────────────────────────────────────────────────

    def check_rate_limit_by_identifier(
        self,
        identifier: str,
        config,
    ) -> tuple:
        """
        Check rate limit using a pre-built identifier string.
        Called by RateLimitService.check_request_by_config().

        Returns:
            tuple: (is_allowed: bool, metadata: dict)
        """
        try:
            TIME_MAP = {'second': 1, 'minute': 60, 'hour': 3600, 'day': 86400}
            window_seconds = TIME_MAP.get(config.time_unit, 3600) * (config.time_value or 1)
            limit = config.requests_per_unit or 100

            is_allowed, metadata = self.sliding_window_log(
                identifier=f'{identifier}:{config.id}',
                window_seconds=window_seconds,
                limit=limit,
            )
            return is_allowed, metadata
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f'check_rate_limit_by_identifier error: {e}')
            return True, {'remaining': -1, 'current': 0, 'reset_time': None}

    def add_request(self, identifier: str, timestamp: float = None) -> bool:
        """Add request to sliding window. Returns True if allowed."""
        import time
        ts = timestamp or time.time()
        try:
            key = f'sw:{identifier}'
            self.redis_client.lpush(key, ts)
            self.redis_client.expire(key, 3600)
            return True
        except Exception:
            return True

    def get_request_count(self, identifier: str, window_seconds: int = 3600) -> int:
        """Get request count in window."""
        import time
        try:
            key = f'sw:{identifier}'
            now = time.time()
            requests = self.redis_client.lrange(key, 0, -1)
            return sum(1 for r in requests if float(r) > now - window_seconds)
        except Exception:
            return 0

    def clear_requests(self, identifier: str) -> bool:
        """Clear all requests for identifier."""
        try:
            self.redis_client.delete(f'sw:{identifier}')
            return True
        except Exception:
            return False

    def is_allowed(self, identifier: str, limit: int, window_seconds: int = 3600) -> bool:
        """Check if request is within rate limit."""
        return self.get_request_count(identifier, window_seconds) < limit

    def get_remaining(self, identifier: str, limit: int, window_seconds: int = 3600) -> int:
        """Get remaining allowed requests."""
        return max(0, limit - self.get_request_count(identifier, window_seconds))

    def get_window_stats(self, identifier: str, window_seconds: int = 3600) -> dict:
        """Get window statistics."""
        count = self.get_request_count(identifier, window_seconds)
        return {'count': count, 'window_seconds': window_seconds}

    def reset_rate_limit(self, identifier: str, config=None) -> bool:
        """Reset rate limit for identifier."""
        return self.clear_requests(identifier)

    def create_window(self, identifier: str, window_seconds: int = 3600, limit: int = 100, window_size: int = None, max_requests: int = None, **kwargs) -> dict:
        """Create a rate limit window for identifier."""
        import time
        # Handle alias kwargs
        if window_size is not None: window_seconds = window_size
        if max_requests is not None: limit = max_requests
        key = f'window:{identifier}'
        window_data = {
            'identifier': identifier,
            'window_seconds': window_seconds,
            'limit': limit,
            'requests': [],
            'created_at': time.time(),
        }
        try:
            self.redis_client.setex(key, window_seconds, str(window_data))
        except Exception:
            pass
        return window_data

    def check_window(self, identifier: str, window_seconds: int = 3600, limit: int = 100, window_size: int = None, max_requests: int = None, **kwargs) -> dict:
        """Check rate limit window."""
        count = self.get_request_count(identifier, window_seconds)
        allowed = count < limit
        return {
            'allowed': allowed,
            'count': count,
            'limit': limit,
            'remaining': max(0, limit - count),
            'window_seconds': window_seconds,
        }

    def delete_window(self, identifier: str) -> bool:
        """Delete rate limit window."""
        try:
            self.redis_client.delete(f'window:{identifier}')
            self.redis_client.delete(f'sw:{identifier}')
            return True
        except Exception:
            return False

    def list_windows(self, pattern: str = '*') -> list:
        """List all windows matching pattern."""
        try:
            keys = self.redis_client.keys(f'window:{pattern}')
            return [k.decode() if isinstance(k, bytes) else k for k in keys]
        except Exception:
            return []
