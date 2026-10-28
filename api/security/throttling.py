"""
Security Throttling Module
Advanced rate limiting and throttling for security endpoints
"""

import logging
import time
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from rest_framework.throttling import BaseThrottle, SimpleRateThrottle
from rest_framework import exceptions
from django.contrib.auth import get_user_model
from django.http import HttpResponse

from .utils import SecurityUtils
from .registry import security_registry, ComponentType

User = get_user_model()
logger = logging.getLogger('security.throttling')


class ThrottleType:
    """Throttle rate types"""
    SECOND = 's'
    MINUTE = 'm'
    HOUR = 'h'
    DAY = 'd'
    WEEK = 'w'
    MONTH = 'mo'


class SecurityThrottle(BaseThrottle):
    """Base security throttle with advanced features"""
    
    def __init__(self, rate: str = '1000/h', scope: str = 'security'):
        self.rate = rate
        self.scope = scope
        self.num_requests, self.duration = self.parse_rate(rate)
        self.cache_key_prefix = 'throttle_'
        self.history = []
        self.now = None
    
    def parse_rate(self, rate: str) -> tuple:
        """Parse rate string like '1000/h'"""
        if not rate:
            return (None, None)
        
        rate_parts = rate.split('/')
        if len(rate_parts) != 2:
            return (None, None)
        
        try:
            num_requests = int(rate_parts[0])
            duration_unit = rate_parts[1].lower()
            
            # Convert duration unit to seconds
            duration_map = {
                ThrottleType.SECOND: 1,
                ThrottleType.MINUTE: 60,
                ThrottleType.HOUR: 3600,
                ThrottleType.DAY: 86400,
                ThrottleType.WEEK: 604800,
                ThrottleType.MONTH: 2592000,  # 30 days
            }
            
            duration = duration_map.get(duration_unit[0], 3600)  # Default to hour
            
            return (num_requests, duration)
        except (ValueError, KeyError):
            return (None, None)
    
    def get_cache_key(self, request, view) -> str:
        """Generate cache key for throttling"""
        ident = self.get_ident(request)
        return f"{self.cache_key_prefix}{self.scope}_{ident}"
    
    def get_ident(self, request) -> str:
        """Get identifier for request"""
        # Use user ID if authenticated
        if request.user and request.user.is_authenticated:
            return f"user_{request.user.id}"
        
        # Use IP address for anonymous requests
        ip = SecurityUtils.get_client_ip(request)
        return f"ip_{ip}"
    
    def allow_request(self, request, view) -> bool:
        """Check if request should be allowed"""
        if self.num_requests is None or self.duration is None:
            return True
        
        self.now = time.time()
        cache_key = self.get_cache_key(request, view)
        
        # Get history from cache
        history = cache.get(cache_key, [])
        
        # Clean old entries
        self.history = [
            timestamp for timestamp in history
            if timestamp > self.now - self.duration
        ]
        
        # Check if request should be throttled
        if len(self.history) >= self.num_requests:
            return self.throttle_failure(cache_key, request)
        
        # Add current request to history
        self.history.append(self.now)
        cache.set(cache_key, self.history, self.duration)
        
        return True
    
    def throttle_failure(self, cache_key: str, request) -> bool:
        """Handle throttle failure"""
        # Log throttling attempt
        logger.warning(f"Request throttled: {self.get_ident(request)} - {self.scope}")
        
        # Create security log
        try:
            from .models import SecurityLog
            
            SecurityLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                security_type='rate_limit_exceeded',
                severity='medium',
                ip_address=SecurityUtils.get_client_ip(request),
                description=f'Rate limit exceeded for {self.scope}',
                metadata={
                    'scope': self.scope,
                    'rate': self.rate,
                    'ident': self.get_ident(request)
                }
            )
        except Exception as e:
            logger.error(f"Failed to log throttling event: {e}")
        
        return False
    
    def wait(self) -> Optional[float]:
        """Get time until next request is allowed"""
        if not self.history:
            return None
        
        # Calculate wait time
        oldest_request = min(self.history)
        wait_time = self.duration - (self.now - oldest_request)
        
        return max(wait_time, 0)


class UserBasedThrottle(SecurityThrottle):
    """Throttle based on user ID"""
    
    def get_ident(self, request) -> str:
        """Get user-based identifier"""
        if request.user and request.user.is_authenticated:
            return f"user_{request.user.id}"
        
        # Fall back to IP for anonymous users
        ip = SecurityUtils.get_client_ip(request)
        return f"ip_{ip}"


class IPBasedThrottle(SecurityThrottle):
    """Throttle based on IP address"""
    
    def get_ident(self, request) -> str:
        """Get IP-based identifier"""
        ip = SecurityUtils.get_client_ip(request)
        return f"ip_{ip}"


class EndpointBasedThrottle(SecurityThrottle):
    """Throttle based on endpoint"""
    
    def get_cache_key(self, request, view) -> str:
        """Generate cache key including endpoint"""
        ident = self.get_ident(request)
        endpoint = f"{view.__class__.__name__}.{view.action}" if view else 'unknown'
        return f"{self.cache_key_prefix}{self.scope}_{ident}_{endpoint}"


class BurstThrottle(SecurityThrottle):
    """Throttle with burst capacity"""
    
    def __init__(self, rate: str = '1000/h', burst_rate: str = '100/m', scope: str = 'security'):
        super().__init__(rate, scope)
        self.burst_num_requests, self.burst_duration = self.parse_rate(burst_rate)
        self.burst_cache_key_prefix = 'burst_throttle_'
    
    def allow_request(self, request, view) -> bool:
        """Check burst and sustained rates"""
        # Check sustained rate first
        if not super().allow_request(request, view):
            return False
        
        # Check burst rate
        if self.burst_num_requests and self.burst_duration:
            return self.check_burst_rate(request, view)
        
        return True
    
    def check_burst_rate(self, request, view) -> bool:
        """Check burst rate limiting"""
        burst_cache_key = f"{self.burst_cache_key_prefix}{self.scope}_{self.get_ident(request)}"
        
        # Get burst history
        burst_history = cache.get(burst_cache_key, [])
        
        # Clean old entries
        burst_history = [
            timestamp for timestamp in burst_history
            if timestamp > self.now - self.burst_duration
        ]
        
        # Check burst limit
        if len(burst_history) >= self.burst_num_requests:
            return False
        
        # Add current request
        burst_history.append(self.now)
        cache.set(burst_cache_key, burst_history, self.burst_duration)
        
        return True


class AdaptiveThrottle(SecurityThrottle):
    """Adaptive throttle that adjusts based on user behavior"""
    
    def __init__(self, base_rate: str = '1000/h', scope: str = 'security'):
        super().__init__(base_rate, scope)
        self.base_num_requests = self.num_requests
        self.base_duration = self.duration
        self.adaptation_factor = 1.0
        self.user_behavior_cache_key = 'user_behavior_'
    
    def get_cache_key(self, request, view) -> str:
        """Generate cache key including adaptation"""
        ident = self.get_ident(request)
        return f"{self.cache_key_prefix}{self.scope}_{ident}_{int(self.adaptation_factor * 100)}"
    
    def allow_request(self, request, view) -> bool:
        """Check with adaptive rate limiting"""
        # Adjust rate based on user behavior
        self.adjust_rate(request)
        
        return super().allow_request(request, view)
    
    def adjust_rate(self, request) -> None:
        """Adjust rate based on user behavior"""
        if not request.user or not request.user.is_authenticated:
            return
        
        user_id = request.user.id
        behavior_key = f"{self.user_behavior_cache_key}{user_id}"
        
        # Get user behavior score
        behavior_score = cache.get(behavior_key, 1.0)
        
        # Adjust adaptation factor
        if behavior_score > 0.8:  # Good behavior
            self.adaptation_factor = 1.5
        elif behavior_score > 0.6:  # Normal behavior
            self.adaptation_factor = 1.0
        elif behavior_score > 0.4:  # Suspicious behavior
            self.adaptation_factor = 0.5
        else:  # Bad behavior
            self.adaptation_factor = 0.25
        
        # Update rate
        self.num_requests = int(self.base_num_requests * self.adaptation_factor)
        self.duration = int(self.base_duration / self.adaptation_factor)
    
    def update_user_behavior(self, user_id: int, action: str, positive: bool = True) -> None:
        """Update user behavior score"""
        behavior_key = f"{self.user_behavior_cache_key}{user_id}"
        current_score = cache.get(behavior_key, 1.0)
        
        # Adjust score based on action
        if positive:
            current_score = min(1.0, current_score + 0.1)
        else:
            current_score = max(0.0, current_score - 0.2)
        
        # Cache for 24 hours
        cache.set(behavior_key, current_score, 86400)


class RoleBasedThrottle(SecurityThrottle):
    """Throttle based on user role"""
    
    def __init__(self, rates: Dict[str, str], default_rate: str = '1000/h', scope: str = 'security'):
        self.rates = rates
        self.default_rate = default_rate
        super().__init__(default_rate, scope)
    
    def get_rate_for_user(self, request) -> str:
        """Get rate based on user role"""
        if not request.user or not request.user.is_authenticated:
            return self.default_rate
        
        user = request.user
        
        # Check user role hierarchy
        if user.is_superuser:
            return self.rates.get('superuser', self.default_rate)
        elif user.is_staff:
            return self.rates.get('staff', self.default_rate)
        elif getattr(user, 'is_security_admin', False):
            return self.rates.get('security_admin', self.default_rate)
        else:
            return self.rates.get('user', self.default_rate)
    
    def allow_request(self, request, view) -> bool:
        """Check with role-based rate"""
        # Update rate based on user role
        user_rate = self.get_rate_for_user(request)
        self.num_requests, self.duration = self.parse_rate(user_rate)
        
        return super().allow_request(request, view)


class TimeBasedThrottle(SecurityThrottle):
    """Throttle with different rates for different times"""
    
    def __init__(self, normal_rate: str = '1000/h', peak_rate: str = '500/h',
                 peak_hours: List[int] = None, scope: str = 'security'):
        self.normal_rate = normal_rate
        self.peak_rate = peak_rate
        self.peak_hours = peak_hours or [9, 10, 11, 14, 15, 16, 17, 18]  # Business hours
        super().__init__(normal_rate, scope)
    
    def allow_request(self, request, view) -> bool:
        """Check with time-based rate"""
        # Check if current time is peak hour
        current_hour = timezone.now().hour
        
        if current_hour in self.peak_hours:
            # Use peak rate
            self.num_requests, self.duration = self.parse_rate(self.peak_rate)
        else:
            # Use normal rate
            self.num_requests, self.duration = self.parse_rate(self.normal_rate)
        
        return super().allow_request(request, view)


class LocationBasedThrottle(SecurityThrottle):
    """Throttle based on geographic location"""
    
    def __init__(self, normal_rate: str = '1000/h', restricted_rate: str = '100/h',
                 restricted_countries: List[str] = None, scope: str = 'security'):
        self.normal_rate = normal_rate
        self.restricted_rate = restricted_rate
        self.restricted_countries = restricted_countries or ['CN', 'RU', 'IR', 'KP']
        super().__init__(normal_rate, scope)
    
    def get_country(self, request) -> Optional[str]:
        """Get country from request"""
        ip = SecurityUtils.get_client_ip(request)
        
        # Get geolocation data
        geo_data = SecurityUtils.get_ip_geolocation(ip)
        return geo_data.get('country')
    
    def allow_request(self, request, view) -> bool:
        """Check with location-based rate"""
        country = self.get_country(request)
        
        if country in self.restricted_countries:
            # Use restricted rate
            self.num_requests, self.duration = self.parse_rate(self.restricted_rate)
        else:
            # Use normal rate
            self.num_requests, self.duration = self.parse_rate(self.normal_rate)
        
        return super().allow_request(request, view)


class ThreatBasedThrottle(SecurityThrottle):
    """Throttle based on threat intelligence"""
    
    def __init__(self, normal_rate: str = '1000/h', threat_rate: str = '10/h',
                 scope: str = 'security'):
        self.normal_rate = normal_rate
        self.threat_rate = threat_rate
        super().__init__(normal_rate, scope)
    
    def is_threat_ip(self, request) -> bool:
        """Check if IP is in threat intelligence"""
        ip = SecurityUtils.get_client_ip(request)
        
        try:
            from .models import ThreatIntelligence
            
            # Check if IP is in threat intelligence
            threat = ThreatIntelligence.objects.filter(
                ip_range__contains=ip,
                is_active=True
            ).first()
            
            return threat is not None
        except Exception:
            return False
    
    def allow_request(self, request, view) -> bool:
        """Check with threat-based rate"""
        if self.is_threat_ip(request):
            # Use threat rate
            self.num_requests, self.duration = self.parse_rate(self.threat_rate)
        else:
            # Use normal rate
            self.num_requests, self.duration = self.parse_rate(self.normal_rate)
        
        return super().allow_request(request, view)


class CompositeThrottle(SecurityThrottle):
    """Composite throttle that combines multiple throttles"""
    
    def __init__(self, throttles: List[SecurityThrottle], scope: str = 'security'):
        self.throttles = throttles
        self.scope = scope
        super().__init__('1000/h', scope)  # Default rate
    
    def allow_request(self, request, view) -> bool:
        """Check all throttles"""
        for throttle in self.throttles:
            if not throttle.allow_request(request, view):
                return False
        
        return True
    
    def wait(self) -> Optional[float]:
        """Get maximum wait time from all throttles"""
        wait_times = []
        
        for throttle in self.throttles:
            wait_time = throttle.wait()
            if wait_time is not None:
                wait_times.append(wait_time)
        
        return max(wait_times) if wait_times else None


# Predefined throttle classes
class LoginThrottle(UserBasedThrottle):
    """Throttle for login endpoints"""
    
    def __init__(self):
        super().__init__('5/m', 'login')


class PasswordResetThrottle(UserBasedThrottle):
    """Throttle for password reset endpoints"""
    
    def __init__(self):
        super().__init__('3/h', 'password_reset')


class APIThrottle(IPBasedThrottle):
    """Throttle for general API endpoints"""
    
    def __init__(self):
        super().__init__('1000/h', 'api')


class AdminAPIThrottle(RoleBasedThrottle):
    """Throttle for admin API endpoints"""
    
    def __init__(self):
        rates = {
            'superuser': '5000/h',
            'staff': '2000/h',
            'security_admin': '3000/h',
            'user': '500/h'
        }
        super().__init__(rates, '100/h', 'admin_api')


class SecurityEventThrottle(AdaptiveThrottle):
    """Throttle for security event endpoints"""
    
    def __init__(self):
        super().__init__('100/m', 'security_event')


class FileUploadThrottle(UserBasedThrottle):
    """Throttle for file upload endpoints"""
    
    def __init__(self):
        super().__init__('10/h', 'file_upload')


class ExportThrottle(UserBasedThrottle):
    """Throttle for data export endpoints"""
    
    def __init__(self):
        super().__init__('5/h', 'export')


# Throttle manager
class ThrottleManager:
    """Manager for throttle configuration and monitoring"""
    
    def __init__(self):
        self.throttles = {}
        self.metrics_cache_key = 'throttle_metrics'
        self.metrics_cache_timeout = 300  # 5 minutes
    
    def register_throttle(self, name: str, throttle_class: type, **kwargs) -> None:
        """Register a throttle class"""
        try:
            throttle_instance = throttle_class(**kwargs)
            self.throttles[name] = throttle_instance
            logger.info(f"Registered throttle: {name}")
        except Exception as e:
            logger.error(f"Failed to register throttle {name}: {e}")
    
    def get_throttle(self, name: str) -> Optional[SecurityThrottle]:
        """Get throttle by name"""
        return self.throttles.get(name)
    
    def get_throttle_metrics(self) -> Dict[str, Any]:
        """Get throttle metrics"""
        # Try to get from cache
        cached_metrics = cache.get(self.metrics_cache_key)
        if cached_metrics:
            return cached_metrics
        
        # Calculate metrics
        metrics = {
            'total_throttles': len(self.throttles),
            'active_throttles': 0,
            'throttle_details': {},
            'cache_keys': [],
        }
        
        # Count cache keys and active throttles
        for name, throttle in self.throttles.items():
            # Count cache keys (simplified)
            cache_keys = []
            for key in cache.keys('*'):
                if throttle.cache_key_prefix in key:
                    cache_keys.append(key)
            
            throttle_metrics = {
                'name': name,
                'type': throttle.__class__.__name__,
                'rate': getattr(throttle, 'rate', 'unknown'),
                'cache_keys_count': len(cache_keys),
                'active': len(cache_keys) > 0,
            }
            
            metrics['throttle_details'][name] = throttle_metrics
            metrics['cache_keys'].extend(cache_keys)
            
            if throttle_metrics['active']:
                metrics['active_throttles'] += 1
        
        metrics['total_cache_keys'] = len(set(metrics['cache_keys']))
        
        # Cache metrics
        cache.set(self.metrics_cache_key, metrics, self.metrics_cache_timeout)
        
        return metrics
    
    def clear_throttle_cache(self, pattern: str = '*') -> int:
        """Clear throttle cache entries"""
        # This is a simplified implementation
        # In production, you might want to use Redis pattern matching
        cleared_count = 0
        
        for key in cache.keys(pattern):
            if 'throttle_' in key:
                cache.delete(key)
                cleared_count += 1
        
        logger.info(f"Cleared {cleared_count} throttle cache entries")
        return cleared_count
    
    def reset_user_throttles(self, user_id: int) -> None:
        """Reset throttles for a specific user"""
        user_prefix = f"throttle_*_user_{user_id}"
        cleared_count = self.clear_throttle_cache(user_prefix)
        
        # Reset adaptive throttle behavior
        try:
            adaptive_throttle = self.get_throttle('adaptive')
            if adaptive_throttle:
                behavior_key = f"{adaptive_throttle.user_behavior_cache_key}{user_id}"
                cache.delete(behavior_key)
        except Exception:
            pass
        
        logger.info(f"Reset throttles for user {user_id}")


# Global throttle manager
throttle_manager = ThrottleManager()

# Register default throttles
def register_default_throttles():
    """Register default throttle classes"""
    throttle_manager.register_throttle('login', LoginThrottle)
    throttle_manager.register_throttle('password_reset', PasswordResetThrottle)
    throttle_manager.register_throttle('api', APIThrottle)
    throttle_manager.register_throttle('admin_api', AdminAPIThrottle)
    throttle_manager.register_throttle('security_event', SecurityEventThrottle)
    throttle_manager.register_throttle('file_upload', FileUploadThrottle)
    throttle_manager.register_throttle('export', ExportThrottle)


# Decorator for applying throttles
def apply_throttle(throttle_name: str, **kwargs):
    """Decorator to apply throttle to a view"""
    def decorator(view_func):
        # This would typically be used with Django's throttle_classes
        # For now, it's a placeholder for documentation
        view_func._throttle_name = throttle_name
        view_func._throttle_kwargs = kwargs
        return view_func
    
    return decorator


# Export classes and utilities
__all__ = [
    'ThrottleType',
    'SecurityThrottle',
    'UserBasedThrottle',
    'IPBasedThrottle',
    'EndpointBasedThrottle',
    'BurstThrottle',
    'AdaptiveThrottle',
    'RoleBasedThrottle',
    'TimeBasedThrottle',
    'LocationBasedThrottle',
    'ThreatBasedThrottle',
    'CompositeThrottle',
    'LoginThrottle',
    'PasswordResetThrottle',
    'APIThrottle',
    'AdminAPIThrottle',
    'SecurityEventThrottle',
    'FileUploadThrottle',
    'ExportThrottle',
    'ThrottleManager',
    'throttle_manager',
    'register_default_throttles',
    'apply_throttle'
]