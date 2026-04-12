# api/offer_inventory/reporting_audit/performance_analytics.py
"""
Performance Analytics — API latency, throughput, error rate tracking.
Records per-endpoint performance metrics for SLA monitoring.
"""
import logging
import time
from datetime import timedelta
from functools import wraps
from django.utils import timezone

logger = logging.getLogger(__name__)


class PerformanceAnalytics:
    """API and system performance analytics."""

    @staticmethod
    def record_request(endpoint: str, method: str, elapsed_ms: float,
                        status_code: int = 200, error_rate: float = 0.0):
        """Record an API request performance metric."""
        from api.offer_inventory.models import PerformanceMetric
        try:
            PerformanceMetric.objects.create(
                endpoint     =endpoint[:255],
                method       =method[:6],
                avg_ms       =elapsed_ms,
                p95_ms       =elapsed_ms * 1.2,
                p99_ms       =elapsed_ms * 1.5,
                error_rate   =error_rate,
                request_count=1,
                recorded_at  =timezone.now(),
            )
        except Exception as e:
            logger.debug(f'PerformanceMetric save error: {e}')

    @staticmethod
    def get_slow_endpoints(threshold_ms: float = 1000.0, limit: int = 20) -> list:
        """Endpoints with average response time above threshold."""
        from api.offer_inventory.models import PerformanceMetric
        from django.db.models import Avg, Count
        since = timezone.now() - timedelta(hours=24)
        return list(
            PerformanceMetric.objects.filter(recorded_at__gte=since)
            .values('endpoint', 'method')
            .annotate(avg=Avg('avg_ms'), requests=Count('id'))
            .filter(avg__gt=threshold_ms)
            .order_by('-avg')[:limit]
        )

    @staticmethod
    def get_error_prone_endpoints(limit: int = 10) -> list:
        """Endpoints with highest error rates."""
        from api.offer_inventory.models import PerformanceMetric
        from django.db.models import Avg, Count
        since = timezone.now() - timedelta(hours=24)
        return list(
            PerformanceMetric.objects.filter(
                recorded_at__gte=since, error_rate__gt=0
            )
            .values('endpoint', 'method')
            .annotate(avg_error=Avg('error_rate'), requests=Count('id'))
            .order_by('-avg_error')[:limit]
        )

    @staticmethod
    def get_throughput(hours: int = 1) -> dict:
        """Request throughput for the last N hours."""
        from api.offer_inventory.models import PerformanceMetric
        from django.db.models import Sum, Avg
        since = timezone.now() - timedelta(hours=hours)
        agg   = PerformanceMetric.objects.filter(recorded_at__gte=since).aggregate(
            total_requests=Sum('request_count'),
            avg_latency   =Avg('avg_ms'),
        )
        total    = agg['total_requests'] or 0
        avg_lat  = round(agg['avg_latency'] or 0, 1)
        per_min  = round(total / max(hours * 60, 1), 1)
        return {
            'total_requests': total,
            'requests_per_min': per_min,
            'avg_latency_ms': avg_lat,
            'period_hours'  : hours,
        }

    @staticmethod
    def get_sla_report(sla_ms: float = 500.0) -> dict:
        """SLA compliance report — % requests under SLA threshold."""
        from api.offer_inventory.models import PerformanceMetric
        from django.db.models import Count
        since = timezone.now() - timedelta(hours=24)
        total   = PerformanceMetric.objects.filter(recorded_at__gte=since).count()
        within  = PerformanceMetric.objects.filter(
            recorded_at__gte=since, avg_ms__lte=sla_ms
        ).count()
        return {
            'sla_threshold_ms': sla_ms,
            'total_requests'  : total,
            'within_sla'      : within,
            'sla_compliance_pct': round(within / max(total, 1) * 100, 1),
        }


def track_performance(endpoint: str = ''):
    """
    Decorator to automatically track endpoint performance.

    Usage:
        @track_performance('offer_list')
        def my_view(request):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start  = time.monotonic()
            status = 200
            error  = 0.0
            try:
                result = func(*args, **kwargs)
                if hasattr(result, 'status_code'):
                    status = result.status_code
                    if status >= 400:
                        error = 1.0
                return result
            except Exception as e:
                error = 1.0
                raise
            finally:
                elapsed = (time.monotonic() - start) * 1000
                ep = endpoint or (func.__name__ if func else 'unknown')
                PerformanceAnalytics.record_request(ep, 'CALL', elapsed, status, error)
        return wrapper
    return decorator
