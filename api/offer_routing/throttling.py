"""
API Rate Limiting for Offer Routing System

This module provides throttling classes for API rate limiting,
including request rate limiting, user-based limits, and tenant-based quotas.
"""

import time
import logging
from django.core.cache import cache
from django.core.exceptions import Throttled
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.response import Response
from rest_framework import status
import redis

from .models import RoutingAuditLog, SecurityEvent
from .utils import get_client_ip, validate_ip_address

User = get_user_model()
logger = logging.getLogger(__name__)


class RoutingEngineThrottle(SimpleRateThrottle):
    """
    Throttle for routing engine endpoints.
    
    Rate limits: 1000 requests per minute per user
    with burst capacity and sliding window tracking.
    """
    
    scope = 'routing_engine'
    THROTTLE_RATES = {
        'user': '1000/min',
        'anon': '100/min',
        'tenant': '10000/min'
    }
    
    def get_cache_key(self, request, view):
        """Generate cache key for throttling."""
        if request.user and request.user.is_authenticated:
            ident = f"user_{request.user.id}"
        else:
            ident = f"ip_{get_client_ip(request)}"
        
        return f"throttle_{self.scope}_{ident}"
    
    def get_rate(self):
        """Get rate based on user type."""
        if hasattr(self, 'request') and self.request.user and self.request.user.is_authenticated:
            # Check if user has custom rate limits
            user_rate_limit = self._get_user_rate_limit(self.request.user)
            if user_rate_limit:
                return user_rate_limit
            
            # Check tenant rate limits
            tenant_rate_limit = self._get_tenant_rate_limit(self.request.user)
            if tenant_rate_limit:
                return tenant_rate_limit
            
            return self.THROTTLE_RATES['user']
        
        return self.THROTTLE_RATES['anon']
    
    def _get_user_rate_limit(self, user):
        """Get custom rate limit for user."""
        try:
            # Check user-specific rate limits
            from .models import UserRateLimit
            
            rate_limit = UserRateLimit.objects.filter(
                user=user,
                is_active=True
            ).first()
            
            if rate_limit:
                return f"{rate_limit.requests_per_minute}/min"
            
        except Exception as e:
            logger.error(f"Error getting user rate limit: {e}")
        
        return None
    
    def _get_tenant_rate_limit(self, user):
        """Get tenant-specific rate limit."""
        try:
            if hasattr(user, 'tenant'):
                from .models import TenantRateLimit
                
                tenant_rate_limit = TenantRateLimit.objects.filter(
                    tenant=user.tenant,
                    is_active=True
                ).first()
                
                if tenant_rate_limit:
                    return f"{tenant_rate_limit.requests_per_minute}/min"
        
        except Exception as e:
            logger.error(f"Error getting tenant rate limit: {e}")
        
        return None
    
    def throttle_failure(self, request, wait):
        """Handle throttle failure."""
        try:
            # Log throttling event
            client_ip = get_client_ip(request)
            
            from .tasks.monitoring import log_throttling_event
            log_throttling_event.delay(
                ip_address=client_ip,
                user_id=request.user.id if request.user.is_authenticated else None,
                endpoint=request.path,
                wait_time=wait,
                rate_limit=self.get_rate(),
                timestamp=timezone.now().isoformat()
            )
            
            # Create security event for excessive throttling
            if wait > 60:  # 1 minute wait
                from .tasks.monitoring import log_security_event
                
                log_security_event.delay(
                    event_type='excessive_throttling',
                    ip_address=client_ip,
                    user_id=request.user.id if request.user.is_authenticated else None,
                    request_path=request.path,
                    details={
                        'wait_time': wait,
                        'rate_limit': self.get_rate()
                    }
                )
            
            # Log to database
            RoutingAuditLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                ip_address=client_ip,
                event_type='throttled',
                request_path=request.path,
                wait_time=wait,
                rate_limit=self.get_rate(),
                timestamp=timezone.now()
            )
            
        except Exception as e:
            logger.error(f"Error in throttle failure: {e}")
        
        super().throttle_failure(request, wait)


class EvaluatorThrottle(SimpleRateThrottle):
    """
    Throttle for evaluator endpoints.
    
    Rate limits: 500 requests per minute per user
    with stricter limits for evaluation operations.
    """
    
    scope = 'evaluator'
    THROTTLE_RATES = {
        'user': '500/min',
        'anon': '50/min',
        'tenant': '5000/min'
    }
    
    def get_cache_key(self, request, view):
        """Generate cache key for evaluator throttling."""
        if request.user and request.user.is_authenticated:
            return f"throttle_{self.scope}_user_{request.user.id}"
        else:
            return f"throttle_{self.scope}_ip_{get_client_ip(request)}"
    
    def get_rate(self):
        """Get rate based on user type."""
        if hasattr(self, 'request') and self.request.user and self.request.user.is_authenticated:
            # Check if user has evaluator-specific limits
            user_rate_limit = self._get_user_evaluator_limit(self.request.user)
            if user_rate_limit:
                return user_rate_limit
            
            return self.THROTTLE_RATES['user']
        
        return self.THROTTLE_RATES['anon']
    
    def _get_user_evaluator_limit(self, user):
        """Get evaluator-specific rate limit for user."""
        try:
            from .models import UserRateLimit
            
            rate_limit = UserRateLimit.objects.filter(
                user=user,
                service_type='evaluator',
                is_active=True
            ).first()
            
            if rate_limit:
                return f"{rate_limit.requests_per_minute}/min"
            
        except Exception as e:
            logger.error(f"Error getting user evaluator limit: {e}")
        
        return None


class AnalyticsThrottle(SimpleRateThrottle):
    """
    Throttle for analytics endpoints.
    
    Rate limits: 200 requests per minute per user
    with optimized caching for analytics queries.
    """
    
    scope = 'analytics'
    THROTTLE_RATES = {
        'user': '200/min',
        'anon': '20/min',
        'tenant': '2000/min'
    }
    
    def get_cache_key(self, request, view):
        """Generate cache key for analytics throttling."""
        if request.user and request.user.is_authenticated:
            return f"throttle_{self.scope}_user_{request.user.id}"
        else:
            return f"throttle_{self.scope}_ip_{get_client_ip(request)}"
    
    def get_rate(self):
        """Get rate based on user type."""
        if hasattr(self, 'request') and self.request.user and self.request.user.is_authenticated:
            # Check if user has analytics-specific limits
            user_rate_limit = self._get_user_analytics_limit(self.request.user)
            if user_rate_limit:
                return user_rate_limit
            
            return self.THROTTLE_RATES['user']
        
        return self.THROTTLE_RATES['anon']
    
    def _get_user_analytics_limit(self, user):
        """Get analytics-specific rate limit for user."""
        try:
            from .models import UserRateLimit
            
            rate_limit = UserRateLimit.objects.filter(
                user=user,
                service_type='analytics',
                is_active=True
            ).first()
            
            if rate_limit:
                return f"{rate_limit.requests_per_minute}/min"
            
        except Exception as e:
            logger.error(f"Error getting user analytics limit: {e}")
        
        return None


class BulkOperationThrottle(SimpleRateThrottle):
    """
    Throttle for bulk operations.
    
    Rate limits: 10 requests per minute per user
    with size-based limiting for large operations.
    """
    
    scope = 'bulk_operation'
    THROTTLE_RATES = {
        'user': '10/min',
        'anon': '5/min',
        'tenant': '100/min'
    }
    
    def get_cache_key(self, request, view):
        """Generate cache key for bulk operations."""
        if request.user and request.user.is_authenticated:
            return f"throttle_{self.scope}_user_{request.user.id}"
        else:
            return f"throttle_{self.scope}_ip_{get_client_ip(request)}"
    
    def get_rate(self):
        """Get rate based on user type."""
        if hasattr(self, 'request') and self.request.user and self.request.user.is_authenticated:
            return self.THROTTLE_RATES['user']
        
        return self.THROTTLE_RATES['anon']


class WebSocketThrottle:
    """
    Specialized throttle for WebSocket connections.
    
    Limits WebSocket connections per user and per IP
    to prevent connection flooding.
    """
    
    def __init__(self, connections_per_user=10, connections_per_ip=50):
        self.connections_per_user = connections_per_user
        self.connections_per_ip = connections_per_ip
        self.connections = {}  # Track active connections
    
    def can_connect(self, user, ip_address):
        """Check if WebSocket connection is allowed."""
        try:
            # Check user connection limit
            if user and user.is_authenticated:
                user_connections = sum(
                    1 for conn in self.connections.values()
                    if conn.get('user_id') == user.id
                )
                
                if user_connections >= self.connections_per_user:
                    logger.warning(f"WebSocket connection limit exceeded for user {user.id}")
                    return False
            
            # Check IP connection limit
            ip_connections = sum(
                1 for conn in self.connections.values()
                    if conn.get('ip_address') == ip_address
                )
                
                if ip_connections >= self.connections_per_ip:
                    logger.warning(f"WebSocket IP connection limit exceeded for {ip_address}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking WebSocket throttle: {e}")
            return False
    
    def add_connection(self, connection_id, user, ip_address):
        """Add WebSocket connection to tracking."""
        self.connections[connection_id] = {
            'user_id': user.id if user and user.is_authenticated else None,
            'ip_address': ip_address,
            'connected_at': timezone.now()
        }
    
    def remove_connection(self, connection_id):
        """Remove WebSocket connection from tracking."""
        if connection_id in self.connections:
            del self.connections[connection_id]
    
    def cleanup_expired_connections(self):
        """Clean up expired connections."""
        try:
            current_time = timezone.now()
            expired_connections = []
            
            for conn_id, conn_data in self.connections.items():
                # Remove connections older than 1 hour
                if current_time - conn_data['connected_at'] > timezone.timedelta(hours=1):
                    expired_connections.append(conn_id)
            
            for conn_id in expired_connections:
                self.remove_connection(conn_id)
            
            logger.debug(f"Cleaned up {len(expired_connections)} expired WebSocket connections")
            
        except Exception as e:
            logger.error(f"Error cleaning up expired connections: {e}")


class AdvancedThrottle:
    """
    Advanced throttling with adaptive rate limiting.
    
    Implements sliding window, burst capacity,
    and intelligent rate adjustment based on user behavior.
    """
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client or cache.client
        self.default_rate = 100  # requests per minute
        self.burst_capacity = 200  # max burst
        self.window_size = 60  # seconds
    
    def is_allowed(self, key, identifier=None):
        """Check if request is allowed using sliding window."""
        try:
            current_time = int(time.time())
            window_start = current_time - self.window_size
            
            # Clean old entries
            pipe = self.redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.execute()
            
            # Check current count in window
            current_count = self.redis_client.zcard(key)
            
            if current_count >= self.default_rate:
                # Calculate time to wait
                oldest_request = self.redis_client.zrange(key, 0, 1, withscores=True)
                
                if oldest_request:
                    oldest_time = int(oldest_request[0][1])
                    wait_time = self.window_size - (current_time - oldest_time)
                    
                    logger.debug(f"Throttling {key}: {current_count}/{self.default_rate}, wait: {wait_time}s")
                    
                    return {
                        'allowed': False,
                        'wait_time': wait_time,
                        'retry_after': current_time + wait_time
                    }
                
                return {
                    'allowed': False,
                    'wait_time': self.window_size,
                    'retry_after': current_time + self.window_size
                }
            
            # Add current request
            pipe = self.redis_client.pipeline()
            pipe.zadd(key, {str(current_time): current_time})
            pipe.expire(key, self.window_size + 60)  # Keep extra time
            pipe.execute()
            
            return {'allowed': True, 'count': current_count + 1}
            
        except Exception as e:
            logger.error(f"Error in advanced throttling: {e}")
            return {'allowed': True, 'count': 0}


class TenantBasedThrottle:
    """
    Tenant-specific throttling with quota management.
    
    Implements per-tenant rate limits with quota tracking
    and automatic quota reset scheduling.
    """
    
    def __init__(self):
        self.quota_cache_timeout = 300  # 5 minutes
    
    def get_tenant_quota(self, tenant_id):
        """Get tenant quota configuration."""
        try:
            from .models import TenantRateLimit
            
            quota = TenantRateLimit.objects.filter(
                tenant_id=tenant_id,
                is_active=True
            ).first()
            
            if quota:
                return {
                    'requests_per_minute': quota.requests_per_minute,
                    'daily_quota': quota.daily_quota,
                    'hourly_quota': quota.hourly_quota,
                    'burst_capacity': quota.burst_capacity
                }
            
            # Default quota
            return {
                'requests_per_minute': 1000,
                'daily_quota': 100000,
                'hourly_quota': 5000,
                'burst_capacity': 2000
            }
            
        except Exception as e:
            logger.error(f"Error getting tenant quota: {e}")
            return self._get_default_quota()
    
    def _get_default_quota(self):
        """Get default quota configuration."""
        return {
            'requests_per_minute': 1000,
            'daily_quota': 100000,
            'hourly_quota': 5000,
            'burst_capacity': 2000
        }
    
    def check_tenant_quota(self, tenant_id):
        """Check if tenant has exceeded quota."""
        try:
            cache_key = f"tenant_quota:{tenant_id}"
            quota_data = cache.get(cache_key)
            
            if not quota_data:
                quota_data = self.get_tenant_quota(tenant_id)
                cache.set(cache_key, quota_data, self.quota_cache_timeout)
            
            # Get current usage from cache
            usage_key = f"tenant_usage:{tenant_id}"
            current_usage = cache.get(usage_key, {'requests': 0, 'timestamp': timezone.now()})
            
            # Calculate usage in current time window
            current_time = timezone.now()
            time_diff = (current_time - current_usage['timestamp']).total_seconds()
            
            if time_diff < 60:  # Within last minute
                requests_per_minute = current_usage['requests']
            else:
                requests_per_minute = 0
            
            # Check quota
            quota_exceeded = (
                requests_per_minute >= quota_data['requests_per_minute'] or
                self._get_daily_usage(tenant_id) >= quota_data['daily_quota']
            )
            
            # Update usage
            new_usage = {
                'requests': current_usage['requests'] + 1,
                'timestamp': current_time
            }
            cache.set(usage_key, new_usage, 60)  # Update for 1 minute
            
            return {
                'allowed': not quota_exceeded,
                'quota': quota_data,
                'current_usage': new_usage,
                'wait_time': 60 if quota_exceeded else 0
            }
            
        except Exception as e:
            logger.error(f"Error checking tenant quota: {e}")
            return {'allowed': True, 'quota': self._get_default_quota()}
    
    def _get_daily_usage(self, tenant_id):
        """Get daily usage for tenant."""
        try:
            cache_key = f"tenant_daily_usage:{tenant_id}"
            daily_usage = cache.get(cache_key, 0)
            
            # Reset at midnight
            current_time = timezone.now()
            if current_time.hour == 0 and current_time.minute == 0:
                cache.set(cache_key, 0, 24 * 3600)  # 24 hours
            
            return daily_usage
            
        except Exception as e:
            logger.error(f"Error getting daily usage: {e}")
            return 0


# Utility functions for throttling
def get_throttle_class(endpoint_type='routing'):
    """Get appropriate throttle class based on endpoint type."""
    throttle_classes = {
        'routing': RoutingEngineThrottle,
        'evaluator': EvaluatorThrottle,
        'analytics': AnalyticsThrottle,
        'bulk': BulkOperationThrottle,
        'websocket': WebSocketThrottle
    }
    
    return throttle_classes.get(endpoint_type, RoutingEngineThrottle)


def check_ip_whitelist(ip_address):
    """Check if IP is in whitelist."""
    try:
        from .models import IPWhitelist
        
        return IPWhitelist.objects.filter(
            ip_address=ip_address,
            is_active=True
        ).exists()
        
    except Exception as e:
        logger.error(f"Error checking IP whitelist: {e}")
        return False


def check_user_whitelist(user):
    """Check if user is in whitelist."""
    try:
        from .models import UserWhitelist
        
        return UserWhitelist.objects.filter(
            user=user,
            is_active=True
        ).exists()
        
    except Exception as e:
        logger.error(f"Error checking user whitelist: {e}")
        return False


def log_throttling_event(request, throttle_class, wait_time):
    """Log throttling event for monitoring."""
    try:
        from .tasks.monitoring import log_throttling_event
        
        log_throttling_event.delay(
            ip_address=get_client_ip(request),
            user_id=request.user.id if request.user.is_authenticated else None,
            endpoint=request.path,
            throttle_class=throttle_class.__name__,
            wait_time=wait_time,
            timestamp=timezone.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error logging throttling event: {e}")


# Throttle configuration
THROTTLE_SETTINGS = {
    'default_rate': 1000,  # requests per minute
    'default_burst': 2000,  # max burst capacity
    'window_size': 60,  # seconds
    'cache_timeout': 300,  # 5 minutes
    'enable_adaptive': True,  # enable adaptive throttling
    'enable_whitelist': True,  # enable IP/user whitelisting
    'log_throttling': True,  # log throttling events
    'redis_key_prefix': 'throttle:',
    'cleanup_interval': 3600,  # 1 hour
}
