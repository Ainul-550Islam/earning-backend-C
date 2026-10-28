# Reconstructed from services/FIX_ALL_PART1_Services5-10.py (was never split into
# individual files, leaving alerts.services unimportable — see audit).
# Fixed on extraction: AlertNotification -> Notification (real model name),
# api.alerts.utils.* -> real existing module paths.

import logging
from django.db.models import Count, Q, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


class StatisticsService:
    """
    Consolidates statistics and analytics logic.
    Eliminates duplicates from: context_processors.py + endpoint.py
    """

    @staticmethod
    def alert_statistics():
        """
        Calculate alert statistics.
        
        Previously duplicated in:
        - alerts/context_processors.py
        - alerts/endpoint.py
        
        Returns:
            dict: Alert statistics
        """
        from api.alerts.models import AlertLog, AlertRule, Notification
        
        logger.info("Calculating alert statistics")
        
        stats = {
            'total_alerts': AlertLog.objects.count(),
            'active_rules': AlertRule.objects.filter(is_active=True).count(),
            'pending_alerts': AlertLog.objects.filter(status='pending').count(),
            'resolved_alerts': AlertLog.objects.filter(status='resolved').count(),
            'failed_alerts': AlertLog.objects.filter(status='failed').count(),
            'escalated_alerts': AlertLog.objects.filter(escalation_level__gt=0).count(),
            'pending_notifications': Notification.objects.filter(status='pending').count(),
            'delivered_notifications': Notification.objects.filter(status='delivered').count(),
        }
        
        # Calculate by severity
        by_severity = AlertLog.objects.values('severity').annotate(count=Count('id'))
        stats['by_severity'] = {item['severity']: item['count'] for item in by_severity}
        
        logger.info(f"Alert statistics: {stats['total_alerts']} total")
        
        return stats

    @staticmethod
    def api_info():
        """
        Get API information.
        
        Previously duplicated in:
        - alerts/context_processors.py
        - alerts/endpoint.py
        
        Returns:
            dict: API information
        """
        logger.info("Generating API info")
        
        info = {
            'name': 'Alerts API',
            'version': '1.0.0',
            'status': 'operational',
            'endpoints': [
                '/api/alerts/',
                '/api/alert-rules/',
                '/api/notifications/',
                '/api/incidents/',
            ],
            'stats': StatisticsService.alert_statistics()
        }
        
        return info

    @staticmethod
    def get_alert_trends(days=7):
        """Get alert trends over time"""
        from datetime import timedelta
        from api.alerts.models import AlertLog
        
        start_date = timezone.now() - timedelta(days=days)
        
        trends = AlertLog.objects.filter(
            triggered_at__gte=start_date
        ).values('triggered_at__date', 'status').annotate(count=Count('id')).order_by('triggered_at__date')
        
        return list(trends)

    @staticmethod
    def get_alert_by_severity_chart():
        """Get alert distribution by severity"""
        from api.alerts.models import AlertLog
        
        data = AlertLog.objects.values('severity').annotate(count=Count('id'))
        
        return list(data)

    @staticmethod
    def get_resolution_time_stats():
        """Get alert resolution time statistics"""
        from api.alerts.models import AlertLog
        from django.db.models import Avg, Max, Min, F
        
        # Calculate average resolution time
        stats = AlertLog.objects.filter(
            status='resolved', resolved_at__isnull=False
        ).annotate(
            resolution_time=F('resolved_at') - F('triggered_at')
        ).aggregate(
            avg_resolution_time=Avg('resolution_time'),
            min_resolution_time=Min('resolution_time'),
            max_resolution_time=Max('resolution_time'),
        )
        
        return stats


__all__ = ['StatisticsService']
