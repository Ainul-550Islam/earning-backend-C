# alerts/metrics_collector.py
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta
from .models import SystemMetrics
import psutil# pip install psutil
from django.db import connection
from django.contrib.auth import get_user_model
User = get_user_model()  # module level


class MetricsCollector:
    """Collect system metrics for monitoring"""
    
    @staticmethod
    def collect_all_metrics():
        """Collect all system metrics"""
        from django.contrib.auth import get_user_model
        from django.db import connection
        from django.utils import timezone
        from datetime import timedelta

        User = get_user_model()
        now = timezone.now()

        try:
            from api.alerts.models.core import AlertRule, AlertLog, Notification, SystemHealthCheck
            metrics = {
                'total_alert_rules': AlertRule.objects.count(),
                'active_alert_rules': AlertRule.objects.filter(is_active=True).count(),
                'total_alert_logs': AlertLog.objects.count(),
                'unresolved_alerts': AlertLog.objects.filter(is_resolved=False).count(),
                'alerts_last_hour': AlertLog.objects.filter(
                    triggered_at__gte=now - timedelta(hours=1)).count(),
                'total_notifications': Notification.objects.count(),
                'pending_notifications': Notification.objects.filter(status='pending').count(),
                'failed_notifications': Notification.objects.filter(status='failed').count(),
                'total_users': User.objects.count(),
                'active_users': User.objects.filter(is_active=True).count(),
                'collected_at': now.isoformat(),
            }
        except Exception as e:
            metrics = {'error': str(e), 'collected_at': now.isoformat()}
        return metrics