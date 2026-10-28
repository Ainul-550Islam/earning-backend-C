"""
throttling.py – Rate limiting and throttling for postback module.

Provides comprehensive rate limiting functionality including:
- Multiple throttling strategies
- Custom rate limit rules
- Distributed throttling
- Throttling analytics
"""
from functools import wraps
import json
import logging
import time
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field

from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.http import HttpResponse
from rest_framework.throttling import BaseThrottle, SimpleRateThrottle

from .exceptions import PostbackException

logger = logging.getLogger(__name__)


class ThrottleType(Enum):
    """Throttle type enumeration."""
    IP_BASED = "ip_based"
    USER_BASED = "user_based"
    NETWORK_BASED = "network_based"
    ENDPOINT_BASED = "endpoint_based"
    GLOBAL = "global"


class ThrottleScope(Enum):
    """Throttle scope enumeration."""
    POSTBACK_RECEIVE = "postback_receive"
    POSTBACK_ANALYTICS = "postback_analytics"
    API_REQUESTS = "api_requests"
    WEBHOOK_CALLS = "webhook_calls"
    FILE_UPLOADS = "file_uploads"


@dataclass
class ThrottleRule:
    """Throttle rule definition."""
    name: str
    scope: ThrottleScope
    rate: str  # e.g., "100/hour", "10/minute"
    throttle_type: ThrottleType
    enabled: bool = True
    priority: int = 50
    conditions: Dict[str, Any] = field(default_factory=dict)
    exemptions: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Parse rate into components."""
        self.requests, self.duration = self._parse_rate(self.rate)
    
    def _parse_rate(self, rate: str) -> Tuple[int, int]:
        """Parse rate string into requests and duration."""
        try:
            requests_str, period_str = rate.split('/')
            requests = int(requests_str)
            
            if period_str == 'second':
                duration = 1
            elif period_str == 'minute':
                duration = 60
            elif period_str == 'hour':
                duration = 3600
            elif period_str == 'day':
                duration = 86400
            else:
                raise ValueError(f"Invalid period: {period_str}")
            
            return requests, duration
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid rate format: {rate}")


class ThrottleStorage:
    """
    Storage backend for throttling data.
    
    Provides interface for storing and retrieving throttling
    counters and timestamps.
    """
    
    def __init__(self):
        self.cache_timeout = 86400  # 24 hours
    
    def get_counter(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get throttle counter data.
        
        Args:
            key: Cache key
            
        Returns:
            Counter data or None
        """
        return cache.get(key)
    
    def set_counter(self, key: str, data: Dict[str, Any], timeout: int = None):
        """
        Set throttle counter data.
        
        Args:
            key: Cache key
            data: Counter data
            timeout: Cache timeout
        """
        timeout = timeout or self.cache_timeout
        cache.set(key, data, timeout)
    
    def increment_counter(self, key: str, increment: int = 1) -> int:
        """
        Increment counter atomically.
        
        Args:
            key: Cache key
            increment: Increment amount
            
        Returns:
            New counter value
        """
        try:
            # Use cache.incr if available
            return cache.incr(key, increment)
        except (AttributeError, ValueError):
            # Fallback to get-set pattern
            data = self.get_counter(key) or {'count': 0, 'timestamp': timezone.now()}
            data['count'] += increment
            data['timestamp'] = timezone.now()
            self.set_counter(key, data)
            return data['count']
    
    def delete_counter(self, key: str):
        """Delete counter."""
        cache.delete(key)
    
    def get_all_counters(self, pattern: str) -> Dict[str, Any]:
        """
        Get all counters matching pattern.
        
        Args:
            pattern: Cache key pattern
            
        Returns:
            Dictionary of counters
        """
        # This is a simplified implementation
        # In production, you might use cache.keys() or maintain a registry
        return {}


class BaseThrottler:
    """
    Base throttler class.
    
    Provides common throttling functionality that can be
    extended for different throttling strategies.
    """
    
    def __init__(self, rule: ThrottleRule, storage: ThrottleStorage = None):
        self.rule = rule
        self.storage = storage or ThrottleStorage()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def get_cache_key(self, request, identifier: str = None) -> str:
        """
        Generate cache key for throttling.
        
        Args:
            request: HTTP request
            identifier: Additional identifier
            
        Returns:
            Cache key
        """
        key_parts = [
            'throttle',
            self.rule.scope.value,
            self.rule.name,
        ]
        
        if identifier:
            key_parts.append(identifier)
        elif self.rule.throttle_type == ThrottleType.IP_BASED:
            key_parts.append(self._get_client_ip(request))
        elif self.rule.throttle_type == ThrottleType.USER_BASED:
            key_parts.append(self._get_user_id(request))
        elif self.rule.throttle_type == ThrottleType.NETWORK_BASED:
            key_parts.append(self._get_network_key(request))
        elif self.rule.throttle_type == ThrottleType.ENDPOINT_BASED:
            key_parts.append(self._get_endpoint(request))
        else:
            key_parts.append('global')
        
        return ':'.join(key_parts)
    
    def is_allowed(self, request, identifier: str = None) -> bool:
        """
        Check if request is allowed.
        
        Args:
            request: HTTP request
            identifier: Additional identifier
            
        Returns:
            True if request is allowed
        """
        if not self.rule.enabled:
            return True
        
        # Check exemptions
        if self._is_exempt(request):
            return True
        
        # Check conditions
        if not self._check_conditions(request):
            return True
        
        # Get cache key
        cache_key = self.get_cache_key(request, identifier)
        
        # Check rate limit
        current_count = self.storage.increment_counter(cache_key)
        
        if current_count > self.rule.requests:
            self.logger.warning(f"Rate limit exceeded for {cache_key}: {current_count}/{self.rule.requests}")
            return False
        
        # Set expiration for new counters
        if current_count == 1:
            self.storage.set_counter(cache_key, {'count': current_count}, self.rule.duration)
        
        return True
    
    def get_throttle_info(self, request, identifier: str = None) -> Dict[str, Any]:
        """
        Get throttling information.
        
        Args:
            request: HTTP request
            identifier: Additional identifier
            
        Returns:
            Throttling information
        """
        cache_key = self.get_cache_key(request, identifier)
        counter_data = self.storage.get_counter(cache_key)
        
        if not counter_data:
            return {
                'allowed': True,
                'remaining': self.rule.requests,
                'reset_time': None,
                'retry_after': None,
            }
        
        current_count = counter_data.get('count', 0)
        timestamp = counter_data.get('timestamp')
        
        remaining = max(0, self.rule.requests - current_count)
        reset_time = timestamp + timedelta(seconds=self.rule.duration) if timestamp else None
        retry_after = max(0, int((reset_time - timezone.now()).total_seconds())) if reset_time else 0
        
        return {
            'allowed': current_count <= self.rule.requests,
            'current_count': current_count,
            'limit': self.rule.requests,
            'remaining': remaining,
            'reset_time': reset_time.isoformat() if reset_time else None,
            'retry_after': retry_after,
        }
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')
    
    def _get_user_id(self, request) -> str:
        """Get user ID."""
        if hasattr(request, 'user') and request.user.is_authenticated:
            return str(request.user.id)
        return 'anonymous'
    
    def _get_network_key(self, request) -> str:
        """Get network key from request."""
        if hasattr(request, 'data') or hasattr(request, 'POST'):
            data = getattr(request, 'data', request.POST)
            return data.get('network_key', 'unknown')
        return 'unknown'
    
    def _get_endpoint(self, request) -> str:
        """Get endpoint path."""
        return request.path.strip('/')
    
    def _is_exempt(self, request) -> bool:
        """Check if request is exempt from throttling."""
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_groups = [group.name for group in request.user.groups.all()]
            
            # Check if user is in exempt groups
            for exemption in self.rule.exemptions:
                if exemption in user_groups:
                    return True
        
        return False
    
    def _check_conditions(self, request) -> bool:
        """Check throttling conditions."""
        conditions = self.rule.conditions
        
        # Check IP conditions
        if 'ip_whitelist' in conditions:
            ip_whitelist = conditions['ip_whitelist']
            client_ip = self._get_client_ip(request)
            
            if client_ip not in ip_whitelist:
                return False
        
        # Check time conditions
        if 'time_window' in conditions:
            time_window = conditions['time_window']
            current_hour = timezone.now().hour
            
            if 'start_hour' in time_window and 'end_hour' in time_window:
                start_hour = time_window['start_hour']
                end_hour = time_window['end_hour']
                
                if not (start_hour <= current_hour <= end_hour):
                    return False
        
        return True


class PostbackThrottler(BaseThrottler):
    """
    Specialized throttler for postback requests.
    
    Provides throttling specifically for postback processing
    with network-aware and user-aware rate limiting.
    """
    
    def __init__(self, rule: ThrottleRule, storage: ThrottleStorage = None):
        super().__init__(rule, storage)
    
    def get_cache_key(self, request, identifier: str = None) -> str:
        """Generate cache key for postback throttling."""
        if self.rule.throttle_type == ThrottleType.NETWORK_BASED:
            network_key = self._get_network_key(request)
            return f"throttle:postback:{self.rule.name}:network:{network_key}"
        
        return super().get_cache_key(request, identifier)
    
    def is_allowed(self, request, identifier: str = None) -> bool:
        """Check if postback request is allowed."""
        # Additional postback-specific checks
        if self.rule.throttle_type == ThrottleType.NETWORK_BASED:
            network_key = self._get_network_key(request)
            
            # Check if network has custom throttling
            from .models import NetworkPostbackConfig
            try:
                network_config = NetworkPostbackConfig.objects.get(network_key=network_key)
                if hasattr(network_config, 'custom_throttle_rate') and network_config.custom_throttle_rate:
                    # Use custom rate for this network
                    custom_requests, custom_duration = self._parse_rate(network_config.custom_throttle_rate)
                    cache_key = f"throttle:postback:custom:{network_key}"
                    
                    current_count = self.storage.increment_counter(cache_key)
                    
                    if current_count > custom_requests:
                        return False
                    
                    if current_count == 1:
                        self.storage.set_counter(cache_key, {'count': current_count}, custom_duration)
                    
                    return True
            except NetworkPostbackConfig.DoesNotExist:
                pass
        
        return super().is_allowed(request, identifier)
    
    def _parse_rate(self, rate: str) -> Tuple[int, int]:
        """Parse rate string."""
        return self.rule._parse_rate(rate)


class ThrottleManager:
    """
    Manager for throttling rules and instances.
    
    Provides centralized management of throttling rules,
    creation of throttlers, and analytics.
    """
    
    def __init__(self):
        self.rules: Dict[str, ThrottleRule] = {}
        self.throttlers: Dict[str, BaseThrottler] = {}
        self.storage = ThrottleStorage()
        self._load_default_rules()
    
    def _load_default_rules(self):
        """Load default throttling rules."""
        default_rules = [
            ThrottleRule(
                name="postback_receive_ip",
                scope=ThrottleScope.POSTBACK_RECEIVE,
                rate="100/minute",
                throttle_type=ThrottleType.IP_BASED,
                priority=100
            ),
            ThrottleRule(
                name="postback_receive_network",
                scope=ThrottleScope.POSTBACK_RECEIVE,
                rate="1000/hour",
                throttle_type=ThrottleType.NETWORK_BASED,
                priority=90
            ),
            ThrottleRule(
                name="analytics_api_user",
                scope=ThrottleScope.POSTBACK_ANALYTICS,
                rate="1000/hour",
                throttle_type=ThrottleType.USER_BASED,
                priority=80
            ),
            ThrottleRule(
                name="api_requests_global",
                scope=ThrottleScope.API_REQUESTS,
                rate="10000/hour",
                throttle_type=ThrottleType.GLOBAL,
                priority=70
            ),
            ThrottleRule(
                name="file_uploads_user",
                scope=ThrottleScope.FILE_UPLOADS,
                rate="10/hour",
                throttle_type=ThrottleType.USER_BASED,
                priority=60
            ),
        ]
        
        for rule in default_rules:
            self.add_rule(rule)
    
    def add_rule(self, rule: ThrottleRule):
        """
        Add throttling rule.
        
        Args:
            rule: Throttle rule to add
        """
        self.rules[rule.name] = rule
        
        # Create throttler instance
        if rule.scope == ThrottleScope.POSTBACK_RECEIVE:
            throttler = PostbackThrottler(rule, self.storage)
        else:
            throttler = BaseThrottler(rule, self.storage)
        
        self.throttlers[rule.name] = throttler
        
        logger.info(f"Added throttling rule: {rule.name}")
    
    def remove_rule(self, name: str):
        """
        Remove throttling rule.
        
        Args:
            name: Rule name
        """
        if name in self.rules:
            del self.rules[name]
        
        if name in self.throttlers:
            del self.throttlers[name]
        
        logger.info(f"Removed throttling rule: {name}")
    
    def get_throttler(self, name: str) -> Optional[BaseThrottler]:
        """
        Get throttler by name.
        
        Args:
            name: Throttler name
            
        Returns:
            Throttler instance or None
        """
        return self.throttlers.get(name)
    
    def check_request(self, request, scope: ThrottleScope = None) -> Dict[str, Any]:
        """
        Check request against applicable throttling rules.
        
        Args:
            request: HTTP request
            scope: Throttle scope to check
            
        Returns:
            Throttling check result
        """
        applicable_throttlers = []
        
        # Get throttlers for scope
        if scope:
            applicable_throttlers = [
                throttler for throttler in self.throttlers.values()
                if throttler.rule.scope == scope and throttler.rule.enabled
            ]
        else:
            applicable_throttlers = [
                throttler for throttler in self.throttlers.values()
                if throttler.rule.enabled
            ]
        
        # Sort by priority (highest first)
        applicable_throttlers.sort(key=lambda t: t.rule.priority, reverse=True)
        
        # Check each throttler
        for throttler in applicable_throttlers:
            if not throttler.is_allowed(request):
                return {
                    'allowed': False,
                    'throttler': throttler.rule.name,
                    'scope': throttler.rule.scope.value,
                    'rate': throttler.rule.rate,
                    'info': throttler.get_throttle_info(request),
                }
        
        return {
            'allowed': True,
            'checked_throttlers': len(applicable_throttlers),
        }
    
    def get_throttle_stats(self) -> Dict[str, Any]:
        """Get throttling statistics."""
        stats = {
            'total_rules': len(self.rules),
            'enabled_rules': len([r for r in self.rules.values() if r.enabled]),
            'rules_by_scope': {},
            'rules_by_type': {},
        }
        
        for rule in self.rules.values():
            scope_key = rule.scope.value
            type_key = rule.throttle_type.value
            
            stats['rules_by_scope'][scope_key] = stats['rules_by_scope'].get(scope_key, 0) + 1
            stats['rules_by_type'][type_key] = stats['rules_by_type'].get(type_key, 0) + 1
        
        return stats
    
    def reset_counters(self, rule_name: str = None, pattern: str = None):
        """
        Reset throttling counters.
        
        Args:
            rule_name: Specific rule to reset
            pattern: Pattern to match counters
        """
        if rule_name:
            # Reset counters for specific rule
            pattern = f"throttle:{rule_name}:*"
        elif pattern:
            # Use provided pattern
            pass
        else:
            # Reset all throttling counters
            pattern = "throttle:*"
        
        counters = self.storage.get_all_counters(pattern)
        
        for key in counters.keys():
            self.storage.delete_counter(key)
        
        logger.info(f"Reset {len(counters)} throttling counters")


# DRF Throttle Classes
class PostbackRateThrottle(SimpleRateThrottle):
    """
    DRF throttle class for postback endpoints.
    
    Integrates with DRF's throttling system.
    """
    scope = 'postback'
    
    def __init__(self):
        super().__init__()
        self.throttle_manager = ThrottleManager()
    
    def get_cache_key(self, request, view):
        """Get cache key for DRF throttling."""
        if hasattr(request, 'user') and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        
        return f'rf_throttle_{self.scope}_{ident}'
    
    def allow_request(self, request, view):
        """Check if request is allowed."""
        # Use custom throttling logic
        result = self.throttle_manager.check_request(request, ThrottleScope.POSTBACK_RECEIVE)
        
        if not result['allowed']:
            self.wait = result['info'].get('retry_after', 60)
            return False
        
        return True


class AnalyticsRateThrottle(SimpleRateThrottle):
    """
    DRF throttle class for analytics endpoints.
    """
    scope = 'analytics'
    
    def __init__(self):
        super().__init__()
        self.throttle_manager = ThrottleManager()
    
    def allow_request(self, request, view):
        """Check if request is allowed."""
        result = self.throttle_manager.check_request(request, ThrottleScope.POSTBACK_ANALYTICS)
        
        if not result['allowed']:
            self.wait = result['info'].get('retry_after', 60)
            return False
        
        return True


# Global throttle manager instance
throttle_manager = ThrottleManager()


# Decorators
def throttle(rate: str, scope: ThrottleScope = None, throttle_type: ThrottleType = None):
    """
    Decorator for throttling function calls.
    
    Args:
        rate: Rate limit string
        scope: Throttle scope
        throttle_type: Throttle type
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Create temporary rule
            rule = ThrottleRule(
                name=f"decorator_{func.__name__}",
                scope=scope or ThrottleScope.API_REQUESTS,
                rate=rate,
                throttle_type=throttle_type or ThrottleType.USER_BASED
            )
            
            # Create throttler
            throttler = BaseThrottler(rule)
            
            # Check throttle
            if not throttler.is_allowed(request):
                info = throttler.get_throttle_info(request)
                response = HttpResponse(
                    json.dumps({'error': 'Rate limit exceeded', 'retry_after': info['retry_after']}),
                    status=429,
                    content_type='application/json'
                )
                response['Retry-After'] = str(info['retry_after'])
                return response
            
            return func(request, *args, **kwargs)
        
        return wrapper
    return decorator


# Utility functions
def check_throttle(request, scope: ThrottleScope = None) -> Dict[str, Any]:
    """
    Check throttling for a request.
    
    Args:
        request: HTTP request
        scope: Throttle scope
        
    Returns:
        Throttling check result
    """
    return throttle_manager.check_request(request, scope)


def get_throttle_info(request, rule_name: str = None) -> Dict[str, Any]:
    """
    Get throttling information.
    
    Args:
        request: HTTP request
        rule_name: Specific rule name
        
    Returns:
        Throttling information
    """
    if rule_name:
        throttler = throttle_manager.get_throttler(rule_name)
        if throttler:
            return throttler.get_throttle_info(request)
    else:
        # Get info from first applicable throttler
        result = throttle_manager.check_request(request)
        if not result['allowed'] and 'info' in result:
            return result['info']
    
    return {}


# Management commands integration
def get_throttle_statistics() -> Dict[str, Any]:
    """Get throttling statistics."""
    return throttle_manager.get_throttle_stats()


def reset_throttle_counters(rule_name: str = None):
    """Reset throttling counters."""
    throttle_manager.reset_counters(rule_name)


# Configuration
def configure_throttling():
    """Configure throttling from Django settings."""
    throttle_rules = getattr(settings, 'POSTBACK_THROTTLE_RULES', [])
    
    for rule_config in throttle_rules:
        try:
            rule = ThrottleRule(**rule_config)
            throttle_manager.add_rule(rule)
        except Exception as e:
            logger.error(f"Error configuring throttling rule {rule_config.get('name', 'unknown')}: {str(e)}")


# Initialize throttling
configure_throttling()
