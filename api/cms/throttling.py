# api/cms/throttling.py
"""Rate limiting and throttling utilities for CMS."""
import logging
import time
import hashlib
from typing import Dict, Any, Optional, Union, Callable
from django.core.cache import cache
from django.conf import settings
from django.http import HttpResponse
from rest_framework.throttling import BaseThrottle, SimpleRateThrottle, AnonRateThrottle, UserRateThrottle
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


# ── Original Throttle Classes (Enhanced) ─────────────────────────────────────

class CMSAnonThrottle(AnonRateThrottle):
    rate = '100/hour'

class CMSUserThrottle(UserRateThrottle):
    rate = '1000/hour'

class CMSWriteThrottle(UserRateThrottle):
    scope = 'cms_write'
    rate = '60/minute'

class CMSPostbackThrottle(SimpleRateThrottle):
    scope = 'cpalead_postback'
    rate = '500/day'
    def get_cache_key(self, request, view):
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        return f"throttle_postback_{ip}"

class CMSWithdrawalThrottle(UserRateThrottle):
    scope = 'cms_withdrawal'
    rate = '5/hour'

class CMSReferralThrottle(UserRateThrottle):
    scope = 'cms_referral'
    rate = '10/hour'

class CMSQuizThrottle(UserRateThrottle):
    scope = 'cms_quiz'
    rate = '30/hour'

class CMSFormSubmitThrottle(SimpleRateThrottle):
    scope = 'cms_form_submit'
    rate = '20/hour'
    def get_cache_key(self, request, view):
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        uid = request.user.id if request.user.is_authenticated else 'anon'
        return f"throttle_form_{ip}_{uid}"

class CMSBurstThrottle(UserRateThrottle):
    scope = 'cms_burst'
    rate = '20/minute'

class CMSAdminThrottle(UserRateThrottle):
    rate = '5000/hour'   # Admins get higher limit


# ── Enhanced Throttle Classes ─────────────────────────────────────

class CMSThrottle(BaseThrottle):
    """Base throttle class for CMS with configurable rates."""
    
    def __init__(self):
        self.rate = getattr(settings, 'CMS_DEFAULT_THROTTLE_RATE', '1000/hour')
        self.num_requests, self.duration = self.parse_rate(self.rate)
        self.history = []
        super().__init__()
    
    def parse_rate(self, rate: str) -> tuple:
        """Parse rate string like '1000/hour' into (1000, 3600)."""
        if not rate:
            return (1000, 3600)  # Default: 1000 requests per hour
        
        num, period = rate.split('/')
        num = int(num)
        
        if period == 'second':
            duration = 1
        elif period == 'minute':
            duration = 60
        elif period == 'hour':
            duration = 3600
        elif period == 'day':
            duration = 86400
        else:
            duration = 3600  # Default to hour
        
        return (num, duration)
    
    def get_cache_key(self, request, view=None) -> str:
        """Generate cache key for throttling."""
        ident = self.get_ident(request)
        return f"throttle:{self.__class__.__name__}:{ident}"
    
    def get_ident(self, request) -> str:
        """Get identifier for throttling."""
        if request.user.is_authenticated:
            return f"user:{request.user.id}"
        return f"ip:{self.get_client_ip(request)}"
    
    def get_client_ip(self, request) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip or 'unknown'
    
    def allow_request(self, request, view) -> bool:
        """Check if request should be allowed."""
        if self.rate is None:
            return True
        
        self.key = self.get_cache_key(request, view)
        self.history = cache.get(self.key, [])
        
        # Remove old entries
        now = time.time()
        while self.history and self.history[-1] <= now - self.duration:
            self.history.pop()
        
        # Check if limit exceeded
        if len(self.history) >= self.num_requests:
            return self.throttle_failure()
        
        # Add current request
        self.history.insert(0, now)
        cache.set(self.key, self.history, self.duration)
        return True
    
    def throttle_failure(self) -> bool:
        """Handle throttle failure."""
        logger.warning(f"Throttling request: {self.key}")
        return False
    
    def wait(self) -> Optional[float]:
        """Get time to wait until next request is allowed."""
        if not self.history:
            return None
        
        return self.history[-1] + self.duration - time.time()


class SurveyThrottle(CMSThrottle):
    """Throttle for survey-related endpoints."""
    
    def __init__(self):
        self.rate = getattr(settings, 'CMS_SURVEY_THROTTLE_RATE', '10/minute')
        super().__init__()


class RewardThrottle(CMSThrottle):
    """Throttle for reward-related endpoints."""
    
    def __init__(self):
        self.rate = getattr(settings, 'CMS_REWARD_THROTTLE_RATE', '5/minute')
        super().__init__()


class PayoutThrottle(CMSThrottle):
    """Throttle for payout endpoints."""
    
    def __init__(self):
        self.rate = getattr(settings, 'CMS_PAYOUT_THROTTLE_RATE', '3/hour')
        super().__init__()


class APIKeyThrottle(CMSThrottle):
    """Throttle based on API key."""
    
    def get_ident(self, request) -> str:
        """Get API key for throttling."""
        api_key = request.META.get('HTTP_X_API_KEY')
        if api_key:
            # Hash API key for security
            return f"apikey:{hashlib.md5(api_key.encode()).hexdigest()}"
        return f"ip:{self.get_client_ip(request)}"


# ── Advanced Throttling ─────────────────────────────────────

class BurstThrottle(CMSThrottle):
    """Throttle with burst capacity and sustained rate."""
    
    def __init__(self, burst_capacity: int = 10, sustained_rate: str = '100/hour'):
        self.burst_capacity = burst_capacity
        self.sustained_rate = sustained_rate
        self.num_requests, self.duration = self.parse_rate(sustained_rate)
        self.history = []
        super().__init__()
    
    def allow_request(self, request, view) -> bool:
        """Check if request should be allowed with burst handling."""
        if self.rate is None:
            return True
        
        self.key = self.get_cache_key(request, view)
        self.history = cache.get(self.key, [])
        
        now = time.time()
        
        # Remove old entries
        while self.history and self.history[-1] <= now - self.duration:
            self.history.pop()
        
        # Allow burst if under capacity
        if len(self.history) < self.burst_capacity:
            self.history.insert(0, now)
            cache.set(self.key, self.history, self.duration)
            return True
        
        # Check sustained rate
        if len(self.history) >= self.num_requests:
            return self.throttle_failure()
        
        self.history.insert(0, now)
        cache.set(self.key, self.history, self.duration)
        return True


class AdaptiveThrottle(CMSThrottle):
    """Throttle that adapts based on user behavior."""
    
    def __init__(self):
        self.base_rate = getattr(settings, 'CMS_DEFAULT_THROTTLE_RATE', '1000/hour')
        self.trust_factor = 1.0
        super().__init__()
    
    def get_trust_factor(self, request) -> float:
        """Calculate trust factor for user."""
        if not request.user.is_authenticated:
            return 0.5  # Lower trust for anonymous users
        
        # Factor in user age, activity, etc.
        user_age = (time.time() - request.user.date_joined.timestamp()) / 86400  # days
        
        if user_age > 365:  # 1 year
            return 2.0  # High trust
        elif user_age > 30:  # 1 month
            return 1.5  # Medium trust
        elif user_age > 7:  # 1 week
            return 1.0  # Normal trust
        else:
            return 0.7  # Low trust
    
    def allow_request(self, request, view) -> bool:
        """Check if request should be allowed with adaptive rate."""
        if self.rate is None:
            return True
        
        self.trust_factor = self.get_trust_factor(request)
        
        # Adjust rate based on trust factor
        base_num, base_duration = self.parse_rate(self.base_rate)
        self.num_requests = int(base_num * self.trust_factor)
        self.duration = base_duration
        
        return super().allow_request(request, view)


# ── Throttling Utilities ─────────────────────────────────────

class ThrottleManager:
    """Manager for handling multiple throttles."""
    
    def __init__(self):
        self.throttles = {}
    
    def register_throttle(self, name: str, throttle_class: type):
        """Register a throttle class."""
        self.throttles[name] = throttle_class
        logger.info(f"Throttle registered: {name}")
    
    def get_throttle(self, name: str) -> Optional[type]:
        """Get throttle class by name."""
        return self.throttles.get(name)
    
    def create_throttle(self, name: str, **kwargs) -> Optional[CMSThrottle]:
        """Create throttle instance."""
        throttle_class = self.get_throttle(name)
        if throttle_class:
            return throttle_class(**kwargs)
        return None
    
    def check_throttles(self, request, throttle_names: list) -> tuple:
        """Check multiple throttles."""
        for name in throttle_names:
            throttle = self.create_throttle(name)
            if throttle and not throttle.allow_request(request, None):
                return False, throttle
        
        return True, None


# Global throttle manager
throttle_manager = ThrottleManager()

# Register default throttles
throttle_manager.register_throttle('user', CMSUserThrottle)
throttle_manager.register_throttle('survey', SurveyThrottle)
throttle_manager.register_throttle('reward', RewardThrottle)
throttle_manager.register_throttle('payout', PayoutThrottle)
throttle_manager.register_throttle('api_key', APIKeyThrottle)
throttle_manager.register_throttle('burst', BurstThrottle)
throttle_manager.register_throttle('adaptive', AdaptiveThrottle)


# ── Throttling Configuration ─────────────────────────────────────

class ThrottleConfig:
    """Configuration for throttling system."""
    
    DEFAULT_CACHE_PREFIX = 'throttle'
    DEFAULT_TIMEOUT = 86400  # 24 hours
    DEFAULT_RETRY_AFTER_HEADER = 'Retry-After'
    
    @classmethod
    def get_cache_prefix(cls) -> str:
        return getattr(settings, 'CMS_THROTTLE_CACHE_PREFIX', cls.DEFAULT_CACHE_PREFIX)
    
    @classmethod
    def get_timeout(cls) -> int:
        return getattr(settings, 'CMS_THROTTLE_TIMEOUT', cls.DEFAULT_TIMEOUT)
    
    @classmethod
    def get_retry_after_header(cls) -> str:
        return getattr(settings, 'CMS_THROTTLE_RETRY_AFTER_HEADER', cls.DEFAULT_RETRY_AFTER_HEADER)


# ── Throttling Analytics ─────────────────────────────────────

def get_throttle_stats() -> Dict[str, Any]:
    """Get throttling statistics."""
    from django.core.cache import cache
    
    # Get all throttle keys
    cache_keys = cache.keys(f"{ThrottleConfig.get_cache_prefix()}:*")
    
    stats = {
        'total_throttled_requests': 0,
        'active_throttle_keys': len(cache_keys),
        'throttle_types': {},
        'timestamp': time.time()
    }
    
    for key in cache_keys:
        try:
            history = cache.get(key, [])
            if history:
                # Extract throttle type from key
                parts = key.split(':')
                if len(parts) >= 2:
                    throttle_type = parts[1]
                    
                    if throttle_type not in stats['throttle_types']:
                        stats['throttle_types'][throttle_type] = {
                            'active_keys': 0,
                            'total_requests': 0
                        }
                    
                    stats['throttle_types'][throttle_type]['active_keys'] += 1
                    stats['throttle_types'][throttle_type]['total_requests'] += len(history)
        except Exception as e:
            logger.error(f"Error processing throttle key {key}: {e}")
    
    return stats


def clear_throttle_cache(pattern: str = None):
    """Clear throttle cache entries."""
    from django.core.cache import cache
    
    if pattern:
        cache_keys = cache.keys(f"{ThrottleConfig.get_cache_prefix()}:{pattern}")
    else:
        cache_keys = cache.keys(f"{ThrottleConfig.get_cache_prefix()}:*")
    
    for key in cache_keys:
        cache.delete(key)
    
    logger.info(f"Cleared {len(cache_keys)} throttle cache entries")
