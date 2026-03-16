import time
import threading
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
        self.bucket_id = bucket_id
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.lock = threading.Lock()
        
        # Initialize bucket in cache
        self._init_bucket()
    
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
        Consume tokens from the bucket
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            bool: True if tokens were consumed, False otherwise
        """
        with self.lock:
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
            return False
    
    def get_available_tokens(self) -> float:
        """Get current number of available tokens"""
        bucket_key = f"token_bucket:{self.bucket_id}"
        bucket_data = cache.get(bucket_key)
        
        if not bucket_data:
            return self.capacity
        
        bucket_data = self._refill_tokens(bucket_data)
        cache.set(bucket_key, bucket_data, timeout=None)
        
        return bucket_data['tokens']
    
    def reset(self):
        """Reset bucket to full capacity"""
        bucket_key = f"token_bucket:{self.bucket_id}"
        cache.set(bucket_key, {
            'tokens': self.capacity,
            'last_refill': time.time()
        }, timeout=None)


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
        self.lock = threading.Lock()
        
        # Initialize bucket
        self._init_bucket()
    
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
        Add a request to the bucket
        
        Returns:
            bool: True if request added, False if bucket is full
        """
        with self.lock:
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
        """Get current water level"""
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
        
        # Increment counter
        current_count = cache.incr(counter_key)
        if current_count == 1:
            # Set expiration when first creating the key
            cache.expire(counter_key, self.window_seconds)
        
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