# cms/monitoring/metrics.py
"""
Performance Monitoring & Metrics System

Tracks and reports on:
- API response times
- Database query performance
- Cache hit rates
- Error rates
- User activity metrics
- Business metrics (conversions, earnings, etc.)

Provides:
- Real-time metrics collection
- Historical data tracking
- Alert triggers
- Dashboard data
- Performance analysis
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, date
from collections import defaultdict, deque
import time
import logging
import json
from django.utils import timezone
from django.db import models

logger = logging.getLogger('cms.monitoring')


# ─────────────────────────────────────────────────────────────────────────────
# METRICS COLLECTOR
# ─────────────────────────────────────────────────────────────────────────────

class MetricsCollector:
    """
    Central metrics collection system
    
    Tracks:
    - Request metrics (response time, status, path)
    - Database metrics (query count, execution time)
    - Cache metrics (hit rate, miss rate)
    - Error metrics (error count, error types)
    """
    
    def __init__(self, window_size: int = 1000):
        """
        Initialize collector
        
        Args:
            window_size: Size of rolling window for metrics
        """
        self.window_size = window_size
        
        # Metrics storage (deques for rolling window)
        self.request_times = deque(maxlen=window_size)
        self.database_queries = deque(maxlen=window_size)
        self.cache_hits = deque(maxlen=window_size)
        self.errors = deque(maxlen=window_size)
        
        # Counters
        self.total_requests = 0
        self.total_errors = 0
        self.total_cache_hits = 0
        self.total_cache_misses = 0
    
    # ─────────────────────────────────────────────────────────────────────────
    # REQUEST METRICS
    # ─────────────────────────────────────────────────────────────────────────
    
    def record_request(self, path: str, method: str, status_code: int,
                      response_time: float, user_id: Optional[int] = None):
        """
        Record API request metrics
        
        Args:
            path: Request path
            method: HTTP method (GET, POST, etc.)
            status_code: Response status code
            response_time: Response time in seconds
            user_id: User ID if authenticated
        """
        self.total_requests += 1
        
        metric = {
            'timestamp': timezone.now(),
            'path': path,
            'method': method,
            'status_code': status_code,
            'response_time': response_time,
            'user_id': user_id,
        }
        
        self.request_times.append(metric)
        
        # Log slow requests
        if response_time > 1.0:
            logger.warning(
                f"Slow request: {method} {path} took {response_time:.2f}s"
            )
        
        # Log errors
        if status_code >= 400:
            self.record_error(path, status_code, method)
    
    def get_request_stats(self) -> Dict[str, Any]:
        """Get request statistics"""
        if not self.request_times:
            return {}
        
        times = [m['response_time'] for m in self.request_times]
        
        return {
            'total_requests': self.total_requests,
            'avg_response_time': sum(times) / len(times),
            'min_response_time': min(times),
            'max_response_time': max(times),
            'p95_response_time': self._percentile(times, 95),
            'p99_response_time': self._percentile(times, 99),
            'slow_requests': sum(1 for t in times if t > 1.0),
        }
    
    def get_endpoints_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics per endpoint"""
        stats = defaultdict(lambda: {
            'count': 0,
            'total_time': 0,
            'min_time': float('inf'),
            'max_time': 0,
            'errors': 0,
        })
        
        for metric in self.request_times:
            key = f"{metric['method']} {metric['path']}"
            stat = stats[key]
            
            stat['count'] += 1
            stat['total_time'] += metric['response_time']
            stat['min_time'] = min(stat['min_time'], metric['response_time'])
            stat['max_time'] = max(stat['max_time'], metric['response_time'])
            
            if metric['status_code'] >= 400:
                stat['errors'] += 1
        
        # Calculate averages
        for key in stats:
            stats[key]['avg_time'] = stats[key]['total_time'] / stats[key]['count']
        
        return dict(stats)
    
    # ─────────────────────────────────────────────────────────────────────────
    # DATABASE METRICS
    # ─────────────────────────────────────────────────────────────────────────
    
    def record_database_query(self, query_type: str, execution_time: float,
                             table: str = None, rows_affected: int = None):
        """
        Record database query metrics
        
        Args:
            query_type: SELECT, INSERT, UPDATE, DELETE
            execution_time: Query execution time
            table: Table name
            rows_affected: Number of rows affected
        """
        metric = {
            'timestamp': timezone.now(),
            'query_type': query_type,
            'execution_time': execution_time,
            'table': table,
            'rows_affected': rows_affected,
        }
        
        self.database_queries.append(metric)
        
        # Log slow queries
        if execution_time > 0.1:
            logger.warning(
                f"Slow query: {query_type} on {table} took {execution_time:.3f}s"
            )
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        if not self.database_queries:
            return {}
        
        # Group by query type
        by_type = defaultdict(list)
        for metric in self.database_queries:
            by_type[metric['query_type']].append(metric['execution_time'])
        
        return {
            'total_queries': len(self.database_queries),
            'by_type': {
                qtype: {
                    'count': len(times),
                    'avg_time': sum(times) / len(times),
                    'total_time': sum(times),
                }
                for qtype, times in by_type.items()
            },
            'slow_queries': sum(
                1 for m in self.database_queries if m['execution_time'] > 0.1
            ),
        }
    
    # ─────────────────────────────────────────────────────────────────────────
    # CACHE METRICS
    # ─────────────────────────────────────────────────────────────────────────
    
    def record_cache_hit(self, key: str, execution_time: float = 0):
        """Record cache hit"""
        self.total_cache_hits += 1
        
        self.cache_hits.append({
            'timestamp': timezone.now(),
            'key': key,
            'type': 'hit',
            'execution_time': execution_time,
        })
    
    def record_cache_miss(self, key: str):
        """Record cache miss"""
        self.total_cache_misses += 1
        
        self.cache_hits.append({
            'timestamp': timezone.now(),
            'key': key,
            'type': 'miss',
        })
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.total_cache_hits + self.total_cache_misses
        
        if total == 0:
            return {'hit_rate': 0}
        
        return {
            'total_hits': self.total_cache_hits,
            'total_misses': self.total_cache_misses,
            'hit_rate': (self.total_cache_hits / total) * 100,
            'miss_rate': (self.total_cache_misses / total) * 100,
        }
    
    # ─────────────────────────────────────────────────────────────────────────
    # ERROR METRICS
    # ─────────────────────────────────────────────────────────────────────────
    
    def record_error(self, path: str, error_code: int, method: str = 'GET',
                    error_type: str = None, details: str = None):
        """
        Record error metrics
        
        Args:
            path: Error path
            error_code: HTTP error code
            method: HTTP method
            error_type: Type of error (ValidationError, etc.)
            details: Error details
        """
        self.total_errors += 1
        
        self.errors.append({
            'timestamp': timezone.now(),
            'path': path,
            'method': method,
            'error_code': error_code,
            'error_type': error_type,
            'details': details,
        })
        
        logger.error(f"Error: {method} {path} - {error_code} ({error_type})")
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        if not self.errors:
            return {'total_errors': 0}
        
        # Group by error code
        by_code = defaultdict(int)
        by_type = defaultdict(int)
        
        for error in self.errors:
            by_code[error['error_code']] += 1
            if error['error_type']:
                by_type[error['error_type']] += 1
        
        return {
            'total_errors': self.total_errors,
            'error_rate': (self.total_errors / max(1, self.total_requests)) * 100,
            'by_code': dict(by_code),
            'by_type': dict(by_type),
        }
    
    # ─────────────────────────────────────────────────────────────────────────
    # AGGREGATED STATS
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get all metrics"""
        return {
            'timestamp': timezone.now().isoformat(),
            'requests': self.get_request_stats(),
            'database': self.get_database_stats(),
            'cache': self.get_cache_stats(),
            'errors': self.get_error_stats(),
        }
    
    # ─────────────────────────────────────────────────────────────────────────
    # HELPER METHODS
    # ─────────────────────────────────────────────────────────────────────────
    
    @staticmethod
    def _percentile(data: List[float], p: int) -> float:
        """Calculate percentile"""
        if not data:
            return 0
        
        sorted_data = sorted(data)
        index = (p / 100) * len(sorted_data)
        
        if index == int(index):
            return sorted_data[int(index) - 1]
        else:
            return sorted_data[int(index)]


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL METRICS INSTANCE
# ─────────────────────────────────────────────────────────────────────────────

# Singleton instance
metrics = MetricsCollector()


# ─────────────────────────────────────────────────────────────────────────────
# MIDDLEWARE FOR AUTOMATIC COLLECTION
# ─────────────────────────────────────────────────────────────────────────────

class MetricsMiddleware:
    """
    Django middleware for automatic metrics collection
    
    Captures:
    - Request timing
    - Response status
    - Error tracking
    
    Usage in settings.py:
        MIDDLEWARE = [
            ...
            'cms.monitoring.metrics.MetricsMiddleware',
            ...
        ]
    """
    
    def __init__(self, get_response):
        """Initialize middleware"""
        self.get_response = get_response
    
    def __call__(self, request):
        """Process request and response"""
        
        # Record start time
        start_time = time.time()
        
        # Get user ID if authenticated
        user_id = request.user.id if request.user.is_authenticated else None
        
        # Process request
        response = self.get_response(request)
        
        # Calculate response time
        response_time = time.time() - start_time
        
        # Record metrics
        metrics.record_request(
            path=request.path,
            method=request.method,
            status_code=response.status_code,
            response_time=response_time,
            user_id=user_id,
        )
        
        return response


# ─────────────────────────────────────────────────────────────────────────────
# BUSINESS METRICS
# ─────────────────────────────────────────────────────────────────────────────

class BusinessMetrics:
    """
    Track business-relevant metrics
    
    Tracks:
    - User registrations
    - Survey completions
    - Offer conversions
    - Earnings
    - Withdrawals
    """
    
    @staticmethod
    def record_survey_completion(user_id: int, survey_id: int, reward: float):
        """Record survey completion"""
        logger.info(
            f"Survey completed: user={user_id}, survey={survey_id}, reward={reward}"
        )
        metrics.record_request(
            path='/surveys/complete',
            method='POST',
            status_code=200,
            response_time=0.1,
            user_id=user_id,
        )
    
    @staticmethod
    def record_offer_conversion(user_id: int, offer_id: int, amount: float):
        """Record offer conversion"""
        logger.info(
            f"Offer converted: user={user_id}, offer={offer_id}, amount={amount}"
        )
    
    @staticmethod
    def record_withdrawal(user_id: int, amount: float, status: str):
        """Record withdrawal"""
        logger.info(
            f"Withdrawal: user={user_id}, amount={amount}, status={status}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# ALERT SYSTEM
# ─────────────────────────────────────────────────────────────────────────────

class MetricsAlerts:
    """
    Alert triggers for performance issues
    
    Alerts when:
    - Error rate > threshold
    - Response time p95 > threshold
    - Cache hit rate < threshold
    - Database slow queries > threshold
    """
    
    # Thresholds
    ERROR_RATE_THRESHOLD = 5.0  # 5%
    RESPONSE_TIME_THRESHOLD = 1.0  # 1 second (p95)
    CACHE_HIT_RATE_THRESHOLD = 70.0  # 70%
    SLOW_QUERY_THRESHOLD = 10  # queries
    
    @staticmethod
    def check_alerts():
        """Check for alert conditions"""
        stats = metrics.get_all_stats()
        
        # Check error rate
        error_rate = stats['errors'].get('error_rate', 0)
        if error_rate > MetricsAlerts.ERROR_RATE_THRESHOLD:
            MetricsAlerts.send_alert(
                f"High error rate: {error_rate:.2f}%"
            )
        
        # Check response time
        p95_time = stats['requests'].get('p95_response_time', 0)
        if p95_time > MetricsAlerts.RESPONSE_TIME_THRESHOLD:
            MetricsAlerts.send_alert(
                f"High response time (p95): {p95_time:.2f}s"
            )
        
        # Check cache hit rate
        hit_rate = stats['cache'].get('hit_rate', 0)
        if hit_rate < MetricsAlerts.CACHE_HIT_RATE_THRESHOLD:
            MetricsAlerts.send_alert(
                f"Low cache hit rate: {hit_rate:.2f}%"
            )
        
        # Check slow queries
        slow_queries = stats['database'].get('slow_queries', 0)
        if slow_queries > MetricsAlerts.SLOW_QUERY_THRESHOLD:
            MetricsAlerts.send_alert(
                f"Too many slow queries: {slow_queries}"
            )
    
    @staticmethod
    def send_alert(message: str):
        """Send alert"""
        logger.warning(f"ALERT: {message}")
        
        # Could integrate with monitoring service (Sentry, DataDog, etc.)
        # send_to_monitoring_service(message)


# Export public API
__all__ = [
    'MetricsCollector',
    'metrics',
    'MetricsMiddleware',
    'BusinessMetrics',
    'MetricsAlerts',
]
