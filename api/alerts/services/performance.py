# Reconstructed from services/FIX_ALL_PART1_Services1-4.py (was never split into
# individual files, leaving alerts.services unimportable — see audit).
# Fixed on extraction: AlertNotification -> Notification (real model name),
# api.alerts.utils.* -> real existing module paths.

import logging
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class PerformanceService:
    """
    Consolidates performance monitoring logic.
    Eliminates duplicates from: performance_optimizations.py + integration/
    """

    @staticmethod
    def get_performance_metrics():
        """
        Get system performance metrics.
        
        Previously duplicated in:
        - alerts/performance_optimizations.py
        - alerts/integration/performance_monitor.py
        
        Returns:
            dict: Performance metrics
        """
        from api.alerts.models import AlertLog, Notification
        from django.db.models import Avg, Max, Min, F
        
        logger.info("Calculating performance metrics")
        
        # Calculate response time
        last_hour = timezone.now() - timedelta(hours=1)
        
        response_times = AlertLog.objects.filter(
            triggered_at__gte=last_hour,
            resolved_at__isnull=False
        ).annotate(
            response_time=(F('resolved_at') - F('triggered_at'))
        ).aggregate(
            avg=Avg('response_time'),
            min=Min('response_time'),
            max=Max('response_time')
        )
        
        # Calculate throughput
        alerts_processed = AlertLog.objects.filter(
            triggered_at__gte=last_hour,
            status__in=['processed', 'resolved']
        ).count()
        
        throughput = alerts_processed / 60  # Per minute
        
        # Calculate notification delivery rate
        total_notifications = Notification.objects.filter(
            created_at__gte=last_hour
        ).count()
        
        delivered = Notification.objects.filter(
            created_at__gte=last_hour,
            status='delivered'
        ).count()
        
        delivery_rate = (delivered / total_notifications * 100) if total_notifications > 0 else 0
        
        metrics = {
            'response_time_avg_ms': int((response_times['avg'].total_seconds() * 1000) if response_times['avg'] else 0),
            'response_time_min_ms': int((response_times['min'].total_seconds() * 1000) if response_times['min'] else 0),
            'response_time_max_ms': int((response_times['max'].total_seconds() * 1000) if response_times['max'] else 0),
            'throughput_per_minute': round(throughput, 2),
            'notification_delivery_rate': round(delivery_rate, 2),
            'alerts_processed_last_hour': alerts_processed,
        }
        
        logger.info(f"Performance metrics: {metrics}")
        return metrics

    @staticmethod
    def get_database_stats():
        """Get database performance statistics"""
        from django.db import connection
        
        stats = {
            'queries_executed': len(connection.queries),
            'slow_queries': len([q for q in connection.queries if float(q['time']) > 0.5])
        }
        
        return stats

    @staticmethod
    def get_memory_usage():
        """Get memory usage statistics"""
        import psutil
        
        process = psutil.Process()
        
        return {
            'memory_mb': process.memory_info().rss / 1024 / 1024,
            'memory_percent': process.memory_percent()
        }

    @staticmethod
    def get_cpu_usage():
        """Get CPU usage"""
        import psutil
        
        return {
            'cpu_percent': psutil.cpu_percent(interval=1)
        }

    @staticmethod
    def is_system_healthy():
        """Check if system performance is healthy"""
        metrics = PerformanceService.get_performance_metrics()
        
        # Define health thresholds
        if metrics['response_time_avg_ms'] > 5000:  # 5 seconds
            return False, "High response time"
        
        if metrics['notification_delivery_rate'] < 95:  # Less than 95%
            return False, "Low delivery rate"
        
        return True, "System healthy"


__all__ = ['PerformanceService']
