"""
Performance Optimizations for Alerts System

This module provides performance improvements for throttling and middleware
to handle high load scenarios efficiently.
"""

import time
import hashlib
import json
from typing import Dict, Any, Optional
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
import logging
import threading
from collections import defaultdict, deque
from functools import lru_cache, wraps

logger = logging.getLogger(__name__)


class PerformanceOptimizedRateLimiter:
    """High-performance rate limiter with optimized caching and algorithms"""
    
    def __init__(self):
        # Local cache for frequently accessed data
        self._local_cache = {}
        self._cache_lock = threading.RLock()
        self._request_counts = defaultdict(deque)
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # Cleanup every 60 seconds
        
        # Performance metrics
        self._cache_hits = 0
        self._cache_misses = 0
        self._total_requests = 0
    
    def is_rate_limited(self, request, limit: int, window: int) -> bool:
        """Optimized rate limiting check with local caching"""
        self._total_requests += 1
        start_time = time.time()
        
        # Generate optimized cache key
        cache_key = self._generate_optimized_cache_key(request)
        
        # Try local cache first (much faster than Redis)
        if self._check_local_cache(cache_key, limit, window):
            self._cache_hits += 1
            return True
        
        # Fallback to Redis cache
        if self._check_redis_cache(cache_key, limit, window):
            self._cache_misses += 1
            return True
        
        # Update local cache
        self._update_local_cache(cache_key, limit, window)
        
        # Periodic cleanup
        self._cleanup_if_needed()
        
        # Log performance metrics
        processing_time = time.time() - start_time
        if processing_time > 0.001:  # Log if taking more than 1ms
            logger.warning(f"Rate limiter slow: {processing_time:.3f}s")
        
        return False
    
    def _generate_optimized_cache_key(self, request) -> str:
        """Generate optimized cache key with minimal overhead"""
        # Use cached user ID if available
        if hasattr(request, '_cached_user_id'):
            user_id = request._cached_user_id
        else:
            user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') else None
            request._cached_user_id = user_id
        
        # Use cached IP if available
        if hasattr(request, '_cached_client_ip'):
            client_ip = request._cached_client_ip
        else:
            client_ip = self._get_client_ip(request)
            request._cached_client_ip = client_ip
        
        # Generate hash for shorter cache keys
        key_data = f"{user_id}:{client_ip}:{request.path}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    def _check_local_cache(self, cache_key: str, limit: int, window: int) -> bool:
        """Check rate limit in local cache (fastest)"""
        with self._cache_lock:
            if cache_key in self._request_counts:
                request_times = self._request_counts[cache_key]
                current_time = time.time()
                
                # Remove old requests outside window
                cutoff_time = current_time - window
                while request_times and request_times[0] < cutoff_time:
                    request_times.popleft()
                
                # Check if limit exceeded
                if len(request_times) >= limit:
                    return True
                
                # Add current request
                request_times.append(current_time)
                return False
        
        return False
    
    def _check_redis_cache(self, cache_key: str, limit: int, window: int) -> bool:
        """Check rate limit in Redis cache (fallback)"""
        try:
            # Use Redis pipeline for atomic operations
            current_time = int(time.time())
            window_start = current_time - window
            
            # Use Lua script for atomic sliding window
            lua_script = """
                local key = KEYS[1]
                local current_time = tonumber(ARGV[1])
                local window_start = tonumber(ARGV[2])
                local limit = tonumber(ARGV[3])
                
                -- Remove old entries
                redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
                
                -- Get current count
                local count = redis.call('ZCARD', key)
                
                if count < limit then
                    -- Add current request
                    redis.call('ZADD', key, current_time, current_time)
                    redis.call('EXPIRE', key, ARGV[4])
                    return 0
                else
                    return 1
                end
            """
            
            result = cache.client.eval(
                lua_script,
                1,  # Number of keys
                f"rate_limit:{cache_key}",
                current_time,
                window_start,
                limit,
                window
            )
            
            return result == 1
            
        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            return False
    
    def _update_local_cache(self, cache_key: str, limit: int, window: int):
        """Update local cache with new request"""
        with self._cache_lock:
            if cache_key not in self._request_counts:
                self._request_counts[cache_key] = deque([time.time()], maxlen=limit)
            else:
                self._request_counts[cache_key].append(time.time())
    
    def _cleanup_if_needed(self):
        """Periodic cleanup of old data"""
        current_time = time.time()
        if current_time - self._last_cleanup > self._cleanup_interval:
            with self._cache_lock:
                # Clean up old entries in local cache
                cutoff_time = current_time - 300  # 5 minutes
                
                for key in list(self._request_counts.keys()):
                    request_times = self._request_counts[key]
                    while request_times and request_times[0] < cutoff_time:
                        request_times.popleft()
                    
                    # Remove empty queues
                    if not request_times:
                        del self._request_counts[key]
                
                self._last_cleanup = current_time
    
    def _get_client_ip(self, request) -> str:
        """Get client IP with caching"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        with self._cache_lock:
            return {
                'total_requests': self._total_requests,
                'cache_hits': self._cache_hits,
                'cache_misses': self._cache_misses,
                'cache_hit_ratio': self._cache_hits / max(self._total_requests, 1),
                'local_cache_size': len(self._request_counts),
                'last_cleanup': self._last_cleanup
            }


class OptimizedAlertContextMiddleware:
    """Performance-optimized version of AlertContextMiddleware"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self._context_cache = {}
        self._cache_ttl = 300  # 5 minutes
        
        # Performance metrics
        self._context_cache_hits = 0
        self._context_cache_misses = 0
    
    def __call__(self, request):
        # Generate cache key for context
        context_cache_key = self._get_context_cache_key(request)
        
        # Try to get cached context
        cached_context = self._get_cached_context(context_cache_key)
        if cached_context:
            request.alert_context = cached_context
            self._context_cache_hits += 1
        else:
            # Generate fresh context
            request.alert_context = self._get_optimized_alert_context(request)
            self._cache_context(context_cache_key, request.alert_context)
            self._context_cache_misses += 1
        
        # Process request
        response = self.get_response(request)
        
        # Add optimized headers
        self._add_optimized_headers(response, request.alert_context)
        
        return response
    
    def _get_context_cache_key(self, request) -> str:
        """Generate cache key for alert context"""
        user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') else None
        session_id = getattr(request.session, 'session_key', None) if hasattr(request, 'session') else None
        
        key_data = f"{user_id}:{session_id}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    def _get_cached_context(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached alert context"""
        try:
            cached_data = cache.get(f"alert_context:{cache_key}")
            if cached_data:
                # Update timestamp
                cached_data['timestamp'] = timezone.now().isoformat()
                return cached_data
        except Exception as e:
            logger.error(f"Error getting cached context: {e}")
        
        return None
    
    def _cache_context(self, cache_key: str, context: Dict[str, Any]):
        """Cache alert context"""
        try:
            cache.set(f"alert_context:{cache_key}", context, timeout=self._cache_ttl)
        except Exception as e:
            logger.error(f"Error caching context: {e}")
    
    def _get_optimized_alert_context(self, request) -> Dict[str, Any]:
        """Get alert context with optimized queries"""
        context = {
            'timestamp': timezone.now().isoformat(),
            'user_id': None,
            'tenant_id': None,
            'session_id': None,
            'request_id': None,
            'active_alerts': 0,
            'pending_alerts': 0,
            'critical_alerts': 0
        }
        
        try:
            # Get user information (cached)
            if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
                context['user_id'] = request.user.id
                context['tenant_id'] = getattr(request.user, 'tenant_id', None)
            
            # Get session information
            if hasattr(request, 'session') and request.session.session_key:
                context['session_id'] = request.session.session_key
            
            # Generate request ID
            if not hasattr(request, 'request_id'):
                import uuid
                request.request_id = str(uuid.uuid4())
            context['request_id'] = request.request_id
            
            # Get optimized alert statistics
            context.update(self._get_optimized_alert_statistics(request))
            
        except Exception as e:
            logger.error(f"Error getting alert context: {e}")
        
        return context
    
    def _get_optimized_alert_statistics(self, request) -> Dict[str, Any]:
        """Get alert statistics with optimized caching"""
        try:
            # Try to get cached statistics first
            cache_key = f"alert_stats:{request.user.id if hasattr(request, 'user') else 'anonymous'}"
            cached_stats = cache.get(cache_key)
            
            if cached_stats:
                return cached_stats
            
            # If not cached, get fresh data (with optimized queries)
            from .models import AlertLog, AlertRule
            
            # Use cached counts where possible
            stats = {
                'active_alerts': AlertLog.objects.filter(is_resolved=False).count(),
                'pending_alerts': AlertLog.objects.filter(
                    is_resolved=False, 
                    severity__in=['low', 'medium']
                ).count(),
                'critical_alerts': AlertLog.objects.filter(
                    is_resolved=False, 
                    severity__in=['high', 'critical']
                ).count(),
                'recent_alerts': AlertLog.objects.filter(
                    triggered_at__gte=timezone.now() - timezone.timedelta(hours=24)
                ).count(),
                'active_rules': AlertRule.objects.filter(is_active=True).count()
            }
            
            # Cache for 5 minutes
            cache.set(cache_key, stats, timeout=300)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting alert statistics: {e}")
            return {
                'active_alerts': 0,
                'pending_alerts': 0,
                'critical_alerts': 0,
                'recent_alerts': 0,
                'active_rules': 0
            }
    
    def _add_optimized_headers(self, response, context: Dict[str, Any]):
        """Add optimized alert headers to response"""
        try:
            # Only add essential headers to reduce overhead
            if context.get('request_id'):
                response['X-Alert-Request-ID'] = context['request_id']
            
            if context.get('active_alerts') is not None:
                response['X-Alert-Active-Count'] = str(context['active_alerts'])
            
            if context.get('critical_alerts') is not None:
                response['X-Alert-Critical-Count'] = str(context['critical_alerts'])
            
        except Exception as e:
            logger.error(f"Error adding alert headers: {e}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        return {
            'context_cache_hits': self._context_cache_hits,
            'context_cache_misses': self._context_cache_misses,
            'cache_hit_ratio': self._context_cache_hits / max(
                self._context_cache_hits + self._context_cache_misses, 1
            )
        }


# Performance monitoring decorator
def monitor_performance(func):
    """Decorator to monitor function performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Log slow functions
            if execution_time > 0.1:  # Log if taking more than 100ms
                logger.warning(f"Slow function: {func.__name__} took {execution_time:.3f}s")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Function {func.__name__} failed after {execution_time:.3f}s: {e}")
            raise
    
    return wrapper


# Cache utilities
class SmartCache:
    """Smart caching with automatic optimization"""
    
    def __init__(self):
        self._cache_stats = defaultdict(int)
    
    @lru_cache(maxsize=1000)
    def get_cached_result(self, key: str, func, *args, **kwargs):
        """Get cached result with LRU optimization"""
        cache_key = f"smart_cache:{hashlib.sha256(key.encode()).hexdigest()[:16]}"
        
        try:
            result = cache.get(cache_key)
            if result is not None:
                self._cache_stats['hits'] += 1
                return result
            
            # Cache miss - compute result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout=300)  # 5 minutes
            
            self._cache_stats['misses'] += 1
            return result
            
        except Exception as e:
            logger.error(f"Smart cache error: {e}")
            return func(*args, **kwargs)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self._cache_stats['hits'] + self._cache_stats['misses']
        return {
            'hits': self._cache_stats['hits'],
            'misses': self._cache_stats['misses'],
            'hit_ratio': self._cache_stats['hits'] / max(total, 1)
        }


# Global instances
performance_limiter = PerformanceOptimizedRateLimiter()
smart_cache = SmartCache()


# Performance monitoring endpoint
def get_performance_metrics():
    """Get comprehensive performance metrics"""
    return {
        'rate_limiter': performance_limiter.get_performance_metrics(),
        'smart_cache': smart_cache.get_cache_stats(),
        'timestamp': timezone.now().isoformat()
    }


# Database query optimization utilities
class QueryOptimizer:
    """Utilities for optimizing database queries"""
    
    @staticmethod
    def get_optimized_alert_counts(user_id=None, tenant_id=None):
        """Get optimized alert counts with minimal queries"""
        from .models import AlertLog
        
        queryset = AlertLog.objects.all()
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        # Use single query with aggregation
        from django.db.models import Count, Q
        
        counts = queryset.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(is_resolved=False)),
            critical=Count('id', filter=Q(is_resolved=False, severity__in=['high', 'critical'])),
            recent=Count('id', filter=Q(triggered_at__gte=timezone.now() - timezone.timedelta(hours=24)))
        )
        
        return {
            'total_alerts': counts['total'],
            'active_alerts': counts['active'],
            'critical_alerts': counts['critical'],
            'recent_alerts': counts['recent']
        }
    
    @staticmethod
    def bulk_update_alert_status(alert_ids, status_data):
        """Bulk update alert status for better performance"""
        from .models import AlertLog
        
        # Use bulk_update for better performance
        alerts = AlertLog.objects.filter(id__in=alert_ids)
        
        for alert in alerts:
            for key, value in status_data.items():
                setattr(alert, key, value)
        
        AlertLog.objects.bulk_update(alerts, status_data.keys(), batch_size=100)
        
        return len(alerts)


# Memory-efficient utilities
class MemoryEfficientProcessor:
    """Memory-efficient processing utilities"""
    
    @staticmethod
    def process_alerts_in_batches(queryset, batch_size=1000, processor_func=None):
        """Process alerts in batches to reduce memory usage"""
        from django.core.paginator import Paginator
        
        paginator = Paginator(queryset, batch_size)
        total_processed = 0
        
        for page_num in paginator.page_range:
            page = paginator.page(page_num)
            batch = list(page.object_list)
            
            if processor_func:
                processor_func(batch)
            
            total_processed += len(batch)
            
            # Clear memory
            del batch
        
        return total_processed
    
    @staticmethod
    def stream_alert_data(queryset, fields=None):
        """Stream alert data to reduce memory footprint"""
        if not fields:
            fields = ['id', 'title', 'severity', 'is_resolved', 'triggered_at']
        
        for alert in queryset.iterator():
            yield {field: getattr(alert, field) for field in fields}
