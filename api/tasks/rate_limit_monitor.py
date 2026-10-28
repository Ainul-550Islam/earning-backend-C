"""
tasks/rate_limit_monitor.py
Rate limit monitoring, analytics, and telemetry system.
Provides insights into rate limiting effectiveness and system health.
"""

import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.core.cache import cache
from django.db import models
from django.db.models import Count, Avg, Sum, F
from celery import shared_task
from api.tasks.models_base import TaskEventLog

# from .models import TaskEventLog

logger = logging.getLogger(__name__)


class RateLimitMetrics:
    """
    In-memory metrics collector for rate limiting.
    Tracks hits, violations, and performance metrics.
    """

    def __init__(self, window_size: int = 3600):  # 1 hour default
        self.window_size = window_size
        self.metrics = defaultdict(lambda: {
            'hits': deque(maxlen=1000),
            'violations': deque(maxlen=1000),
            'response_times': deque(maxlen=1000),
            'by_endpoint': defaultdict(lambda: deque(maxlen=500)),
            'by_user': defaultdict(lambda: deque(maxlen=500)),
        })

    def record_hit(self, limit_type: str, identifier: str, response_time: float = None):
        """Record a successful rate limit check."""
        now = time.time()
        self.metrics[limit_type]['hits'].append(now)
        self.metrics[limit_type]['by_endpoint'][limit_type].append(now)
        self.metrics[limit_type]['by_user'][identifier].append(now)

        if response_time:
            self.metrics[limit_type]['response_times'].append(response_time)

    def record_violation(self, limit_type: str, identifier: str):
        """Record a rate limit violation."""
        now = time.time()
        self.metrics[limit_type]['violations'].append(now)
        self.metrics[limit_type]['by_endpoint'][limit_type].append(now)
        self.metrics[limit_type]['by_user'][identifier].append(now)

    def get_stats(self, limit_type: str = None, hours: int = 1) -> Dict:
        """Get statistics for the specified time window."""
        now = time.time()
        cutoff = now - (hours * 3600)

        if limit_type:
            metrics = self.metrics[limit_type]
        else:
            # Aggregate all types
            metrics = {
                'hits': deque(),
                'violations': deque(),
                'response_times': deque(),
                'by_endpoint': defaultdict(deque),
                'by_user': defaultdict(deque),
            }
            for m in self.metrics.values():
                metrics['hits'].extend(m['hits'])
                metrics['violations'].extend(m['violations'])
                metrics['response_times'].extend(m['response_times'])

        # Filter by time window
        recent_hits = [t for t in metrics['hits'] if t > cutoff]
        recent_violations = [t for t in metrics['violations'] if t > cutoff]
        recent_response_times = [t for t in metrics['response_times'] if t > cutoff]

        # Calculate stats
        total_requests = len(recent_hits) + len(recent_violations)
        violation_rate = len(recent_violations) / max(total_requests, 1)

        avg_response_time = sum(recent_response_times) / max(len(recent_response_times), 1)

        return {
            'total_requests': total_requests,
            'hits': len(recent_hits),
            'violations': len(recent_violations),
            'violation_rate': violation_rate,
            'avg_response_time': avg_response_time,
            'requests_per_minute': total_requests / max(hours * 60, 1),
            'time_window_hours': hours,
        }

    def get_top_violators(self, limit_type: str = None, hours: int = 24, top_n: int = 10) -> List[Tuple[str, int]]:
        """Get top rate limit violators."""
        now = time.time()
        cutoff = now - (hours * 3600)

        violator_counts = defaultdict(int)

        if limit_type:
            metrics = self.metrics[limit_type]
        else:
            metrics = {
                'by_user': defaultdict(deque),
            }
            for m in self.metrics.values():
                for user, timestamps in m['by_user'].items():
                    metrics['by_user'][user].extend(timestamps)

        for user, timestamps in metrics['by_user'].items():
            recent_violations = [t for t in timestamps if t > cutoff]
            violator_counts[user] = len(recent_violations)

        return sorted(violator_counts.items(), key=lambda x: x[1], reverse=True)[:top_n]


# Global metrics instance
rate_limit_metrics = RateLimitMetrics()


class RateLimitMonitor:
    """
    Database-backed rate limit monitoring and analytics.
    """

    @staticmethod
    def get_violation_summary(hours: int = 24) -> Dict:
        """Get summary of rate limit violations from database."""
        cutoff = timezone.now() - timedelta(hours=hours)

        violations = TaskEventLog.objects.filter(
            event_type=TaskEventLog.EventType.ADMIN_BLOCK,
            created_at__gte=cutoff,
            event_data__violation_type='rate_limit'
        )

        summary = violations.aggregate(
            total_violations=Count('id'),
            unique_users=Count('user_id', distinct=True),
            unique_ips=Count('ip_address', distinct=True),
        )

        # Group by limit type
        by_limit_type = violations.values('event_data__limit_type').annotate(
            count=Count('id')
        ).order_by('-count')

        return {
            'total_violations': summary['total_violations'],
            'unique_users': summary['unique_users'],
            'unique_ips': summary['unique_ips'],
            'by_limit_type': list(by_limit_type),
            'time_window_hours': hours,
        }

    @staticmethod
    def get_system_health() -> Dict:
        """Get overall rate limiting system health."""
        try:
            from .middleware_rate_limit import RateLimitService
            service = RateLimitService()

            # Check Redis connectivity
            redis_ok = service.redis_client is not None
            if redis_ok:
                try:
                    service.redis_client.ping()
                except:
                    redis_ok = False

            # Get recent metrics
            stats = rate_limit_metrics.get_stats(hours=1)

            return {
                'redis_connected': redis_ok,
                'using_cache_fallback': not redis_ok,
                'total_requests_last_hour': stats['total_requests'],
                'violation_rate': stats['violation_rate'],
                'avg_response_time': stats['avg_response_time'],
                'system_status': 'healthy' if stats['violation_rate'] < 0.1 else 'warning',
            }
        except Exception as e:
            logger.error(f"Error checking rate limit system health: {e}")
            return {
                'redis_connected': False,
                'using_cache_fallback': True,
                'error': str(e),
                'system_status': 'error',
            }


@shared_task(bind=True, max_retries=1, default_retry_delay=60,
             name='tasks.rate_limit_monitor.generate_rate_limit_report')
def generate_rate_limit_report(self, hours: int = 24) -> dict:
    """Generate comprehensive rate limit report."""
    try:
        # Get database violations
        db_summary = RateLimitMonitor.get_violation_summary(hours)

        # Get in-memory metrics
        metrics_stats = rate_limit_metrics.get_stats(hours=hours)

        # Get top violators
        top_violators = rate_limit_metrics.get_top_violators(hours=hours, top_n=20)

        # Get system health
        health = RateLimitMonitor.get_system_health()

        report = {
            'generated_at': timezone.now().isoformat(),
            'time_window_hours': hours,
            'database_summary': db_summary,
            'metrics_summary': metrics_stats,
            'top_violators': top_violators,
            'system_health': health,
        }

        # Cache report for 1 hour
        cache.set(f'rate_limit_report_{hours}h', report, timeout=3600)

        logger.info(f"[RATE_LIMIT_REPORT] Generated {hours}h report: {db_summary['total_violations']} violations")

        return report

    except Exception as exc:
        logger.error(f"[RATE_LIMIT_REPORT] Error generating report: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=300,
             name='tasks.rate_limit_monitor.alert_on_high_violation_rate')
def alert_on_high_violation_rate(self, threshold: float = 0.1) -> dict:
    """Alert if violation rate exceeds threshold."""
    try:
        stats = rate_limit_metrics.get_stats(hours=1)

        if stats['violation_rate'] > threshold:
            logger.warning(
                f"[RATE_LIMIT_ALERT] High violation rate: {stats['violation_rate']:.2%} "
                f"({stats['violations']}/{stats['total_requests']} in last hour)"
            )

            # Could send email/Slack alert here
            return {
                'alert_triggered': True,
                'violation_rate': stats['violation_rate'],
                'threshold': threshold,
                'violations': stats['violations'],
                'total_requests': stats['total_requests'],
            }

        return {'alert_triggered': False, 'violation_rate': stats['violation_rate']}

    except Exception as exc:
        logger.error(f"[RATE_LIMIT_ALERT] Error checking violation rate: {exc}")
        raise self.retry(exc=exc)