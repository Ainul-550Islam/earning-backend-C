# engagement/throttling.py
"""
Custom throttling classes for engagement system.
Provides rate limiting for different engagement actions.
"""
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle, SimpleRateThrottle
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class EngagementRateThrottle(BaseThrottle):
    """Base throttle class for engagement actions."""
    
    def __init__(self):
        self.rate = None
        self.num_requests = None
        self.duration = None
        self.cache_key_prefix = 'engagement_throttle'
    
    def get_cache_key(self, request, view):
        """Generate cache key for throttling."""
        if request.user.is_authenticated:
            identifier = f"user_{request.user.id}"
        else:
            identifier = f"ip_{self.get_client_ip(request)}"
        
        return f"{self.cache_key_prefix}:{view.__class__.__name__}:{identifier}"
    
    def get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def allow_request(self, request, view):
        """Check if request should be allowed."""
        if self.rate is None:
            return True
        
        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True
        
        history = self.cache.get(self.key, [])
        now = timezone.now()
        
        # Drop old entries
        while history and history[-1] <= now - timedelta(seconds=self.duration):
            history.pop()
        
        # Check if request exceeds rate limit
        if len(history) >= self.num_requests:
            return self.throttle_failure()
        
        # Add current request to history
        history.insert(0, now)
        self.cache.set(self.key, history, self.duration)
        
        return True
    
    def wait(self):
        """Returns the recommended next available time."""
        if self.key is None:
            return None
        
        history = self.cache.get(self.key, [])
        if not history:
            return None
        
        # Calculate wait time
        oldest_request = history[-1]
        wait_time = self.duration - (timezone.now() - oldest_request).total_seconds()
        
        return max(wait_time, 0)


class CheckInRateThrottle(EngagementRateThrottle):
    """Throttle for check-in actions (1 per day)."""
    
    def __init__(self):
        super().__init__()
        self.rate = '1/day'
        self.num_requests = 1
        self.duration = 86400  # 24 hours
        self.cache_key_prefix = 'checkin_throttle'


class SpinRateThrottle(EngagementRateThrottle):
    """Throttle for spin actions (10 per hour)."""
    
    def __init__(self):
        super().__init__()
        self.rate = '10/hour'
        self.num_requests = 10
        self.duration = 3600  # 1 hour
        self.cache_key_prefix = 'spin_throttle'


class QuestRateThrottle(EngagementRateThrottle):
    """Throttle for quest actions (100 per hour)."""
    
    def __init__(self):
        super().__init__()
        self.rate = '100/hour'
        self.num_requests = 100
        self.duration = 3600  # 1 hour
        self.cache_key_prefix = 'quest_throttle'


class PurchaseRateThrottle(EngagementRateThrottle):
    """Throttle for purchase actions (20 per hour)."""
    
    def __init__(self):
        super().__init__()
        self.rate = '20/hour'
        self.num_requests = 20
        self.duration = 3600  # 1 hour
        self.cache_key_prefix = 'purchase_throttle'


class SocialRateThrottle(EngagementRateThrottle):
    """Throttle for social actions (50 per hour)."""
    
    def __init__(self):
        super().__init__()
        self.rate = '50/hour'
        self.num_requests = 50
        self.duration = 3600  # 1 hour
        self.cache_key_prefix = 'social_throttle'


class NotificationRateThrottle(EngagementRateThrottle):
    """Throttle for notification actions (100 per hour)."""
    
    def __init__(self):
        super().__init__()
        self.rate = '100/hour'
        self.num_requests = 100
        self.duration = 3600  # 1 hour
        self.cache_key_prefix = 'notification_throttle'


class APIRateThrottle(EngagementRateThrottle):
    """General API throttle (1000 per hour)."""
    
    def __init__(self):
        super().__init__()
        self.rate = '1000/hour'
        self.num_requests = 1000
        self.duration = 3600  # 1 hour
        self.cache_key_prefix = 'api_throttle'


class BurstRateThrottle(EngagementRateThrottle):
    """Burst throttle for high-frequency actions (10 per minute)."""
    
    def __init__(self):
        super().__init__()
        self.rate = '10/minute'
        self.num_requests = 10
        self.duration = 60  # 1 minute
        self.cache_key_prefix = 'burst_throttle'


class PremiumUserRateThrottle(EngagementRateThrottle):
    """Relaxed throttle for premium users."""
    
    def get_cache_key(self, request, view):
        """Generate cache key with premium user consideration."""
        if request.user.is_authenticated:
            is_premium = getattr(request.user, 'has_premium', False)
            identifier = f"user_{request.user.id}_premium_{is_premium}"
        else:
            identifier = f"ip_{self.get_client_ip(request)}"
        
        return f"{self.cache_key_prefix}:{view.__class__.__name__}:{identifier}"
    
    def __init__(self):
        super().__init__()
        self.rate = '2000/hour'
        self.num_requests = 2000
        self.duration = 3600  # 1 hour
        self.cache_key_prefix = 'premium_throttle'


class TenantRateThrottle(EngagementRateThrottle):
    """Tenant-aware throttle."""
    
    def get_cache_key(self, request, view):
        """Generate cache key with tenant consideration."""
        if request.user.is_authenticated:
            tenant_id = getattr(request.user, 'tenant_id', 'default')
            identifier = f"user_{request.user.id}_tenant_{tenant_id}"
        else:
            identifier = f"ip_{self.get_client_ip(request)}"
        
        return f"{self.cache_key_prefix}:{view.__class__.__name__}:{identifier}"


class DynamicRateThrottle(EngagementRateThrottle):
    """Dynamic throttle based on user level/activity."""
    
    def get_rate(self, request, view):
        """Get dynamic rate based on user."""
        if not request.user.is_authenticated:
            return '100/hour'
        
        # Get user level
        user_level = getattr(request.user, 'level', 1)
        
        # Adjust rate based on level
        if user_level >= 50:
            return '5000/hour'
        elif user_level >= 25:
            return '3000/hour'
        elif user_level >= 10:
            return '2000/hour'
        else:
            return '1000/hour'
    
    def parse_rate(self, rate):
        """Parse rate string into components."""
        if rate is None:
            return (None, None)
        
        rate_str = rate.replace(' ', '')
        if '/' not in rate_str:
            return (None, None)
        
        num, period = rate_str.split('/')
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
    
    def allow_request(self, request, view):
        """Check if request should be allowed with dynamic rate."""
        rate = self.get_rate(request, view)
        self.num_requests, self.duration = self.parse_rate(rate)
        
        if self.num_requests is None:
            return True
        
        return super().allow_request(request, view)


class ActionSpecificThrottle(EngagementRateThrottle):
    """Throttle based on specific action types."""
    
    def __init__(self):
        super().__init__()
        self.action_rates = {
            'checkin': ('1/day', 1, 86400),
            'spin': ('10/hour', 10, 3600),
            'quest_complete': ('100/hour', 100, 3600),
            'purchase': ('20/hour', 20, 3600),
            'social': ('50/hour', 50, 3600),
        }
    
    def get_action_rate(self, request, view):
        """Get rate based on action type."""
        action = getattr(view, 'action_type', None)
        
        if action and action in self.action_rates:
            return self.action_rates[action]
        
        # Default rate
        return ('1000/hour', 1000, 3600)
    
    def allow_request(self, request, view):
        """Check if request should be allowed."""
        rate_str, num_requests, duration = self.get_action_rate(request, view)
        
        self.rate = rate_str
        self.num_requests = num_requests
        self.duration = duration
        
        if self.num_requests is None:
            return True
        
        return super().allow_request(request, view)


class CumulativeRateThrottle(EngagementRateThrottle):
    """Cumulative throttle across multiple actions."""
    
    def __init__(self):
        super().__init__()
        self.rate = '5000/hour'
        self.num_requests = 5000
        self.duration = 3600
        self.cache_key_prefix = 'cumulative_throttle'
    
    def get_cache_key(self, request, view):
        """Generate cache key for cumulative throttling."""
        if request.user.is_authenticated:
            identifier = f"user_{request.user.id}"
        else:
            identifier = f"ip_{self.get_client_ip(request)}"
        
        return f"{self.cache_key_prefix}:cumulative:{identifier}"


class TimeWindowThrottle(EngagementRateThrottle):
    """Time window based throttle."""
    
    def __init__(self, window_start=None, window_end=None, max_requests=100):
        super().__init__()
        self.window_start = window_start
        self.window_end = window_end
        self.max_requests = max_requests
        self.cache_key_prefix = 'time_window_throttle'
    
    def allow_request(self, request, view):
        """Check if request should be allowed within time window."""
        now = timezone.now()
        
        # Check if we're within the time window
        if self.window_start and now < self.window_start:
            return True
        if self.window_end and now > self.window_end:
            return True
        
        # Use regular throttling within window
        self.num_requests = self.max_requests
        self.duration = (self.window_end - self.window_start).total_seconds() if self.window_start and self.window_end else 3600
        
        return super().allow_request(request, view)


class AdaptiveThrottle(EngagementRateThrottle):
    """Adaptive throttle that adjusts based on system load."""
    
    def __init__(self):
        super().__init__()
        self.base_rate = '1000/hour'
        self.cache_key_prefix = 'adaptive_throttle'
    
    def get_system_load(self):
        """Get current system load."""
        try:
            # Check cache hit rate as a simple load metric
            cache_stats = cache._cache.get_stats() if hasattr(cache._cache, 'get_stats') else {}
            hit_rate = cache_stats.get('hit_rate', 0.5)
            
            # Adjust rate based on hit rate
            if hit_rate > 0.8:
                return 2.0  # High cache hit rate, allow more requests
            elif hit_rate > 0.6:
                return 1.0  # Normal cache hit rate
            else:
                return 0.5  # Low cache hit rate, reduce requests
                
        except Exception:
            return 1.0  # Default to normal rate
    
    def allow_request(self, request, view):
        """Check if request should be allowed with adaptive rate."""
        load_factor = self.get_system_load()
        
        # Adjust rate based on load
        base_num, base_duration = self.parse_rate(self.base_rate)
        self.num_requests = int(base_num * load_factor)
        self.duration = base_duration
        
        return super().allow_request(request, view)


class UserBehaviorThrottle(EngagementRateThrottle):
    """Throttle based on user behavior patterns."""
    
    def __init__(self):
        super().__init__()
        self.rate = '1000/hour'
        self.cache_key_prefix = 'behavior_throttle'
    
    def get_user_behavior_score(self, user_id):
        """Get user behavior score."""
        try:
            # Simple behavior scoring based on recent activity
            cache_key = f"user_behavior_{user_id}"
            behavior_data = cache.get(cache_key, {'score': 1.0, 'last_updated': timezone.now()})
            
            # Update behavior score based on recent activity
            now = timezone.now()
            if (now - behavior_data['last_updated']).total_seconds() > 3600:  # Update every hour
                # Calculate behavior score based on activity patterns
                # This is a simplified example
                behavior_data['score'] = min(2.0, behavior_data['score'] * 1.1)
                behavior_data['last_updated'] = now
                cache.set(cache_key, behavior_data, 86400)
            
            return behavior_data['score']
            
        except Exception:
            return 1.0  # Default to normal behavior
    
    def allow_request(self, request, view):
        """Check if request should be allowed based on user behavior."""
        if request.user.is_authenticated:
            behavior_score = self.get_user_behavior_score(request.user.id)
            
            # Adjust rate based on behavior score
            base_num, base_duration = self.parse_rate(self.rate)
            self.num_requests = int(base_num * behavior_score)
            self.duration = base_duration
        else:
            # Use base rate for anonymous users
            self.num_requests, self.duration = self.parse_rate(self.rate)
        
        return super().allow_request(request, view)


# ── Throttle Utilities ─────────────────────────────────────────────────────

class ThrottleManager:
    """Manager for throttling operations."""
    
    def __init__(self):
        self.throttles = {}
        self._register_default_throttles()
    
    def _register_default_throttles(self):
        """Register default throttles."""
        self.throttles.update({
            'checkin': CheckInRateThrottle,
            'spin': SpinRateThrottle,
            'quest': QuestRateThrottle,
            'purchase': PurchaseRateThrottle,
            'social': SocialRateThrottle,
            'notification': NotificationRateThrottle,
            'api': APIRateThrottle,
            'burst': BurstRateThrottle,
            'premium': PremiumUserRateThrottle,
            'tenant': TenantRateThrottle,
            'dynamic': DynamicRateThrottle,
            'cumulative': CumulativeRateThrottle,
            'adaptive': AdaptiveThrottle,
            'behavior': UserBehaviorThrottle,
        })
    
    def get_throttle(self, throttle_name):
        """Get throttle class by name."""
        return self.throttles.get(throttle_name)
    
    def register_throttle(self, name, throttle_class):
        """Register a custom throttle."""
        self.throttles[name] = throttle_class
    
    def get_user_throttle_stats(self, user_id):
        """Get throttle statistics for a user."""
        stats = {}
        
        for throttle_name, throttle_class in self.throttles.items():
            try:
                throttle = throttle_class()
                cache_key = f"{throttle.cache_key_prefix}:*:user_{user_id}"
                
                # Get all throttle keys for user
                keys = cache.keys(cache_key)
                
                stats[throttle_name] = {
                    'total_keys': len(keys),
                    'active_keys': 0,
                    'rate': throttle.rate
                }
                
                # Check active throttles
                for key in keys:
                    history = cache.get(key, [])
                    if history:
                        stats[throttle_name]['active_keys'] += 1
                        
            except Exception as exc:
                logger.error(f"Error getting throttle stats for {throttle_name}: {exc}")
                stats[throttle_name] = {'error': str(exc)}
        
        return stats
    
    def clear_user_throttles(self, user_id):
        """Clear all throttle data for a user."""
        cleared_count = 0
        
        for throttle_class in self.throttles.values():
            try:
                throttle = throttle_class()
                cache_key = f"{throttle.cache_key_prefix}:*:user_{user_id}"
                
                # Delete all throttle keys for user
                keys = cache.keys(cache_key)
                for key in keys:
                    cache.delete(key)
                    cleared_count += 1
                    
            except Exception as exc:
                logger.error(f"Error clearing throttle: {exc}")
        
        return cleared_count


# Global throttle manager instance
throttle_manager = ThrottleManager()


# ── Throttle Decorators ─────────────────────────────────────────────────────

def throttle_action(action_type, rate=None):
    """Decorator to apply action-specific throttling."""
    def decorator(view_func):
        def wrapper(view, request, *args, **kwargs):
            # Get throttle for action type
            throttle = throttle_manager.get_throttle(action_type)
            
            if throttle:
                throttle_instance = throttle()
                if not throttle_instance.allow_request(request, view):
                    return Response(
                        {'error': 'Rate limit exceeded', 'retry_after': throttle_instance.wait()},
                        status=429
                    )
            
            return view_func(view, request, *args, **kwargs)
        return wrapper
    return decorator


def throttle_premium_users(view_func):
    """Decorator to apply premium user throttling."""
    def wrapper(view, request, *args, **kwargs):
        if request.user.is_authenticated and getattr(request.user, 'has_premium', False):
            throttle = PremiumUserRateThrottle()
            if not throttle.allow_request(request, view):
                return Response(
                    {'error': 'Rate limit exceeded', 'retry_after': throttle.wait()},
                    status=429
                )
        
        return view_func(view, request, *args, **kwargs)
    return wrapper


def throttle_tenant_users(view_func):
    """Decorator to apply tenant-aware throttling."""
    def wrapper(view, request, *args, **kwargs):
        throttle = TenantRateThrottle()
        if not throttle.allow_request(request, view):
            return Response(
                {'error': 'Rate limit exceeded', 'retry_after': throttle.wait()},
                status=429
            )
        
        return view_func(view, request, *args, **kwargs)
    return wrapper


# ── Throttle Configuration ─────────────────────────────────────────────────

THROTTLE_CONFIG = {
    'default': 'engagement.throttling.APIRateThrottle',
    'checkin': 'engagement.throttling.CheckInRateThrottle',
    'spin': 'engagement.throttling.SpinRateThrottle',
    'quest': 'engagement.throttling.QuestRateThrottle',
    'purchase': 'engagement.throttling.PurchaseRateThrottle',
    'social': 'engagement.throttling.SocialRateThrottle',
    'notification': 'engagement.throttling.NotificationRateThrottle',
    'burst': 'engagement.throttling.BurstRateThrottle',
    'premium': 'engagement.throttling.PremiumUserRateThrottle',
    'tenant': 'engagement.throttling.TenantRateThrottle',
    'dynamic': 'engagement.throttling.DynamicRateThrottle',
    'cumulative': 'engagement.throttling.CumulativeRateThrottle',
    'adaptive': 'engagement.throttling.AdaptiveThrottle',
    'behavior': 'engagement.throttling.UserBehaviorThrottle',
}


def get_throttle_class(throttle_name):
    """Get throttle class from configuration."""
    throttle_path = THROTTLE_CONFIG.get(throttle_name)
    
    if throttle_path:
        try:
            module_path, class_name = throttle_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[class_name])
            return getattr(module, class_name)
        except Exception as exc:
            logger.error(f"Error importing throttle {throttle_name}: {exc}")
    
    return None
