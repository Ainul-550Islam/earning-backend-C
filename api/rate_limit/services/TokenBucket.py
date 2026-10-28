import time
import redis
import json
from typing import Optional, Dict, Any
from django.core.cache import cache
from django.conf import settings


class TokenBucket:
    """টোকেন বাকেট অ্যালগরিদম ইমপ্লিমেন্টেশন"""
    
    def __init__(self, bucket_id: str, capacity: int, refill_rate: float):
        """
        Initialize token bucket
        
        Args:
            bucket_id: Unique identifier for the bucket
            capacity: Maximum tokens the bucket can hold
            refill_rate: Tokens added per second
        """
        # Validate parameters
        if capacity <= 0:
            raise ValueError(f"capacity must be positive, got {capacity}")
        if refill_rate <= 0:
            raise ValueError(f"refill_rate must be positive, got {refill_rate}")
        self.bucket_id = bucket_id
        self.capacity = capacity
        self.tokens = float(capacity)  # Start full
        self._last_refill = __import__("time").time()
        self.refill_rate = refill_rate
        self.redis_client = self._get_redis_client()
        
        # Initialize bucket in cache
        self._init_bucket()
    
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
    
    def _init_bucket(self):
        """Initialize bucket data in cache"""
        bucket_key = f"token_bucket:{self.bucket_id}"
        if not cache.get(bucket_key):
            cache.set(bucket_key, {
                'tokens': self.capacity,
                'last_refill': time.time()
            }, timeout=None)
    
    def _refill_tokens(self, bucket_data: Dict[str, Any]) -> Dict[str, Any]:
        """Refill tokens based on elapsed time"""
        current_time = time.time()
        elapsed = current_time - bucket_data['last_refill']
        
        # Calculate new tokens
        new_tokens = elapsed * self.refill_rate
        bucket_data['tokens'] = min(
            self.capacity, 
            bucket_data['tokens'] + new_tokens
        )
        bucket_data['last_refill'] = current_time
        
        return bucket_data
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Consume tokens from the bucket using Redis atomic operations
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            bool: True if tokens were consumed, False otherwise
        """
        bucket_key = f"token_bucket:{self.bucket_id}"
        current_time = time.time()
        
        # Use Redis WATCH/MULTI/EXEC for atomic operations
        while True:
            try:
                # Start watching the key
                self.redis_client.watch(bucket_key)
                
                # Get current bucket data
                bucket_data = self.redis_client.get(bucket_key)
                if bucket_data:
                    bucket_data = json.loads(bucket_data)
                else:
                    # Reinitialize if bucket was evicted
                    bucket_data = {
                        'tokens': self.capacity,
                        'last_refill': current_time
                    }
                
                # Refill tokens based on elapsed time
                elapsed = current_time - bucket_data['last_refill']
                new_tokens = elapsed * self.refill_rate
                bucket_data['tokens'] = min(
                    self.capacity, 
                    bucket_data['tokens'] + new_tokens
                )
                bucket_data['last_refill'] = current_time
                
                # Check if enough tokens are available
                if bucket_data['tokens'] >= tokens:
                    bucket_data['tokens'] -= tokens
                    
                    # Start transaction
                    pipe = self.redis_client.pipeline()
                    pipe.multi()
                    pipe.set(bucket_key, json.dumps(bucket_data))
                    pipe.execute()
                    return True
                else:
                    # Not enough tokens, update bucket data anyway
                    pipe = self.redis_client.pipeline()
                    pipe.multi()
                    pipe.set(bucket_key, json.dumps(bucket_data))
                    pipe.execute()
                    return False
                    
            except redis.WatchError:
                # Key was modified, retry
                pass  # was: continue (fixed)
            except Exception as e:
                # Fallback to cache if Redis fails
                return self._consume_fallback(tokens)
    
    def _consume_fallback(self, tokens: int = 1) -> bool:
        """Fallback method using Django cache when Redis is not available"""
        bucket_key = f"token_bucket:{self.bucket_id}"
        bucket_data = cache.get(bucket_key)
        
        if not bucket_data:
            # Reinitialize if bucket was evicted from cache
            bucket_data = {
                'tokens': self.capacity,
                'last_refill': time.time()
            }
        
        # Refill tokens
        bucket_data = self._refill_tokens(bucket_data)
        
        # Check if enough tokens are available
        if bucket_data['tokens'] >= tokens:
            bucket_data['tokens'] -= tokens
            cache.set(bucket_key, bucket_data, timeout=None)
            return True
        
        # Update cache even if no tokens consumed
        cache.set(bucket_key, bucket_data, timeout=None)
        try:
            return self._consume_from_memory(tokens)
        except Exception:
            return False
    
    def get_available_tokens(self) -> float:
        """Get current number of available tokens using Redis atomic operations"""
        bucket_key = f"token_bucket:{self.bucket_id}"
        current_time = time.time()
        
        try:
            # Use Redis WATCH/MULTI/EXEC for atomic operations
            while True:
                self.redis_client.watch(bucket_key)
                
                # Get current bucket data
                bucket_data = self.redis_client.get(bucket_key)
                if bucket_data:
                    bucket_data = json.loads(bucket_data)
                else:
                    # Return capacity if bucket doesn't exist
                    return self.capacity
                
                # Refill tokens based on elapsed time
                elapsed = current_time - bucket_data['last_refill']
                new_tokens = elapsed * self.refill_rate
                bucket_data['tokens'] = min(
                    self.capacity, 
                    bucket_data['tokens'] + new_tokens
                )
                bucket_data['last_refill'] = current_time
                
                # Update bucket data
                pipe = self.redis_client.pipeline()
                pipe.multi()
                pipe.set(bucket_key, json.dumps(bucket_data))
                pipe.execute()
                
                return bucket_data['tokens']
                
        except redis.WatchError:
            # Key was modified, retry
            pass  # was: continue (fixed)
        except Exception:
            # Fallback to cache if Redis fails
            return self._get_available_tokens_fallback()
    
    def _consume_from_memory(self, tokens: int = 1) -> bool:
        """Simple in-memory consume - used as final fallback."""
        import time
        current_time = time.time()
        # Refill tokens based on elapsed time
        elapsed = current_time - self._last_refill
        refill_amount = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + refill_amount)
        self._last_refill = current_time
        # Try to consume
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _get_available_tokens_fallback(self) -> float:
        """Fallback method using Django cache when Redis is not available"""
        bucket_key = f"token_bucket:{self.bucket_id}"
        bucket_data = cache.get(bucket_key)
        
        if not bucket_data:
            return self.capacity
        
        bucket_data = self._refill_tokens(bucket_data)
        cache.set(bucket_key, bucket_data, timeout=None)
        
        return bucket_data['tokens']
    
    def reset(self):
        """Reset bucket to full capacity using Redis"""
        bucket_key = f"token_bucket:{self.bucket_id}"
        bucket_data = {
            'tokens': self.capacity,
            'last_refill': time.time()
        }
        
        try:
            self.redis_client.set(bucket_key, json.dumps(bucket_data))
        except Exception:
            # Fallback to cache if Redis fails
            cache.set(bucket_key, bucket_data, timeout=None)


class LeakyBucket:
    """লিকি বাকেট অ্যালগরিদম ইমপ্লিমেন্টেশন"""
    
    def __init__(self, bucket_id: str, capacity: int, leak_rate: float):
        """
        Initialize leaky bucket
        
        Args:
            bucket_id: Unique identifier for the bucket
            capacity: Maximum capacity of the bucket
            leak_rate: Requests processed per second
        """
        self.bucket_id = bucket_id
        self.capacity = capacity
        self.leak_rate = leak_rate
        self.redis_client = self._get_redis_client()
        
        # Initialize bucket
        self._init_bucket()
    
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
    
    def _init_bucket(self):
        """Initialize bucket data"""
        bucket_key = f"leaky_bucket:{self.bucket_id}"
        if not cache.get(bucket_key):
            cache.set(bucket_key, {
                'water': 0,
                'last_leak': time.time()
            }, timeout=None)
    
    def _leak_water(self, bucket_data: Dict[str, Any]) -> Dict[str, Any]:
        """Leak water based on elapsed time"""
        current_time = time.time()
        elapsed = current_time - bucket_data['last_leak']
        
        # Calculate leaked water
        leaked = elapsed * self.leak_rate
        bucket_data['water'] = max(0, bucket_data['water'] - leaked)
        bucket_data['last_leak'] = current_time
        
        return bucket_data
    
    def add_request(self) -> bool:
        """
        Add a request to the bucket using Redis atomic operations
        
        Returns:
            bool: True if request added, False if bucket is full
        """
        bucket_key = f"leaky_bucket:{self.bucket_id}"
        current_time = time.time()
        
        # Use Redis WATCH/MULTI/EXEC for atomic operations
        while True:
            try:
                # Start watching the key
                self.redis_client.watch(bucket_key)
                
                # Get current bucket data
                bucket_data = self.redis_client.get(bucket_key)
                if bucket_data:
                    bucket_data = json.loads(bucket_data)
                else:
                    # Initialize if bucket was evicted
                    bucket_data = {
                        'water': 0,
                        'last_leak': current_time
                    }
                
                # Leak water based on elapsed time
                elapsed = current_time - bucket_data['last_leak']
                leaked = elapsed * self.leak_rate
                bucket_data['water'] = max(0, bucket_data['water'] - leaked)
                bucket_data['last_leak'] = current_time
                
                # Check if there's space for new request
                if bucket_data['water'] < self.capacity:
                    bucket_data['water'] += 1
                    
                    # Start transaction
                    pipe = self.redis_client.pipeline()
                    pipe.multi()
                    pipe.set(bucket_key, json.dumps(bucket_data))
                    pipe.execute()
                    return True
                else:
                    # Update bucket data even if request not added
                    pipe = self.redis_client.pipeline()
                    pipe.multi()
                    pipe.set(bucket_key, json.dumps(bucket_data))
                    pipe.execute()
                    return False
                    
            except redis.WatchError:
                # Key was modified, retry
                pass  # was: continue (fixed)
            except Exception as e:
                # Fallback to cache if Redis fails
                return self._add_request_fallback()
    
    def _add_request_fallback(self) -> bool:
        """Fallback method using Django cache when Redis is not available"""
        bucket_key = f"leaky_bucket:{self.bucket_id}"
        bucket_data = cache.get(bucket_key)
        
        if not bucket_data:
            bucket_data = {
                'water': 0,
                'last_leak': time.time()
            }
        
        # Leak water
        bucket_data = self._leak_water(bucket_data)
        
        # Check if there's space for new request
        if bucket_data['water'] < self.capacity:
            bucket_data['water'] += 1
            cache.set(bucket_key, bucket_data, timeout=None)
            return True
        
        # Update cache even if request not added
        cache.set(bucket_key, bucket_data, timeout=None)
        return False
    
    def get_current_level(self) -> float:
        """Get current water level using Redis atomic operations"""
        bucket_key = f"leaky_bucket:{self.bucket_id}"
        current_time = time.time()
        
        try:
            # Use Redis WATCH/MULTI/EXEC for atomic operations
            while True:
                self.redis_client.watch(bucket_key)
                
                # Get current bucket data
                bucket_data = self.redis_client.get(bucket_key)
                if bucket_data:
                    bucket_data = json.loads(bucket_data)
                else:
                    # Return 0 if bucket doesn't exist
                    return 0
                
                # Leak water based on elapsed time
                elapsed = current_time - bucket_data['last_leak']
                leaked = elapsed * self.leak_rate
                bucket_data['water'] = max(0, bucket_data['water'] - leaked)
                bucket_data['last_leak'] = current_time
                
                # Update bucket data
                pipe = self.redis_client.pipeline()
                pipe.multi()
                pipe.set(bucket_key, json.dumps(bucket_data))
                pipe.execute()
                
                return bucket_data['water']
                
        except redis.WatchError:
            # Key was modified, retry
            pass  # was: continue (fixed)
        except Exception:
            # Fallback to cache if Redis fails
            return self._get_current_level_fallback()
    
    def _get_current_level_fallback(self) -> float:
        """Fallback method using Django cache when Redis is not available"""
        bucket_key = f"leaky_bucket:{self.bucket_id}"
        bucket_data = cache.get(bucket_key)
        
        if not bucket_data:
            return 0
        
        bucket_data = self._leak_water(bucket_data)
        cache.set(bucket_key, bucket_data, timeout=None)
        
        return bucket_data['water']


class FixedWindowCounter:
    """ফিক্সড উইন্ডো কাউন্টার ইমপ্লিমেন্টেশন"""
    
    def __init__(self, counter_id: str, limit: int, window_seconds: int):
        """
        Initialize fixed window counter
        
        Args:
            counter_id: Unique identifier for the counter
            limit: Maximum requests in the window
            window_seconds: Window size in seconds
        """
        self.counter_id = counter_id
        self.limit = limit
        self.window_seconds = window_seconds
    
    def increment(self) -> tuple[bool, dict]:
        """
        Increment counter for current window
        
        Returns:
            tuple: (is_allowed, metadata)
        """
        current_window = int(time.time() // self.window_seconds)
        counter_key = f"fixed_window:{self.counter_id}:{current_window}"
        
        # Use Django cache API properly - atomic increment with expiration
        # Try to add new key with expiration (atomic operation)
        if cache.add(counter_key, 1, timeout=self.window_seconds):
            # Key was successfully added (didn't exist before)
            current_count = 1
        else:
            # Key already exists, increment it
            try:
                current_count = cache.incr(counter_key)
                # Note: Django cache.incr() doesn't preserve timeout, so we need to handle it
                # For most use cases, the key will expire naturally from the initial add()
            except ValueError:
                # Fallback: set the key again if increment fails
                cache.set(counter_key, 1, timeout=self.window_seconds)
                current_count = 1
        
        # Check limit
        is_allowed = current_count <= self.limit
        
        metadata = {
            'current_count': current_count,
            'limit': self.limit,
            'window_start': current_window * self.window_seconds,
            'window_end': (current_window + 1) * self.window_seconds,
            'remaining': max(0, self.limit - current_count),
            'reset_time': (current_window + 1) * self.window_seconds
        }
        
        return is_allowed, metadata
    
    def get_current_count(self) -> int:
        """Get current count for active window"""
        current_window = int(time.time() // self.window_seconds)
        counter_key = f"fixed_window:{self.counter_id}:{current_window}"
        
        return cache.get(counter_key) or 0