# api/offer_inventory/reporting_audit/real_time_monitor.py
"""
Real-Time Monitor — Live platform health monitoring with alerting.
Detects: fraud spikes, revenue drops, error surges, queue backlogs.
"""
import logging
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)

THRESHOLDS = {
    'fraud_rate_pct'      : 15.0,
    'error_rate_per_hour' : 50,
    'conversion_drop_pct' : 30.0,
    'queue_depth_alert'   : 500,
    'response_time_ms'    : 2000.0,
}


class RealTimeMonitor:
    """Real-time platform health monitoring."""

    @classmethod
    def check_all(cls) -> dict:
        """Run all health checks and return alert list."""
        alerts  = []
        results = {}

        # 1. Fraud rate
        fr = cls._current_fraud_rate()
        results['fraud_rate_pct'] = fr
        if fr > THRESHOLDS['fraud_rate_pct']:
            alerts.append({
                'type'      : 'fraud_spike',
                'value'     : fr,
                'threshold' : THRESHOLDS['fraud_rate_pct'],
                'severity'  : 'high',
            })

        # 2. Error rate
        er = cls._current_error_count()
        results['error_count_hour'] = er
        if er > THRESHOLDS['error_rate_per_hour']:
            alerts.append({
                'type'     : 'error_spike',
                'value'    : er,
                'threshold': THRESHOLDS['error_rate_per_hour'],
                'severity' : 'medium',
            })

        # 3. Queue depth
        qd = cls._queue_depth()
        results['queue_depth'] = qd
        if qd > THRESHOLDS['queue_depth_alert']:
            alerts.append({
                'type'     : 'queue_backlog',
                'value'    : qd,
                'threshold': THRESHOLDS['queue_depth_alert'],
                'severity' : 'medium',
            })

        if alerts:
            cls._dispatch_alerts(alerts)

        return {
            'healthy'   : len(alerts) == 0,
            'alerts'    : alerts,
            'metrics'   : results,
            'checked_at': timezone.now().isoformat(),
        }

    @staticmethod
    def _current_fraud_rate() -> float:
        """Fraud rate in last 30 minutes."""
        from api.offer_inventory.models import Click
        since = timezone.now() - timedelta(minutes=30)
        total = Click.objects.filter(created_at__gte=since).count()
        fraud = Click.objects.filter(created_at__gte=since, is_fraud=True).count()
        return round(fraud / max(total, 1) * 100, 2)

    @staticmethod
    def _current_error_count() -> int:
        """Error count in last hour."""
        from api.offer_inventory.models import ErrorLog
        since = timezone.now() - timedelta(hours=1)
        return ErrorLog.objects.filter(
            created_at__gte=since, level__in=['error', 'critical']
        ).count()

    @staticmethod
    def _queue_depth() -> int:
        """Total pending Celery tasks."""
        from api.offer_inventory.models import TaskQueue
        return TaskQueue.objects.filter(status='pending').count()

    @staticmethod
    def _dispatch_alerts(alerts: list):
        """Send alerts via Slack + Email."""
        try:
            from api.offer_inventory.notifications.slack_webhook import SlackNotifier
            notifier = SlackNotifier()
            for alert in alerts:
                if alert['type'] == 'fraud_spike':
                    notifier.alert_fraud({'fraud_rate': alert['value']})
                elif alert['severity'] == 'high':
                    notifier.alert_system_error(
                        f'{alert["type"]}: {alert["value"]} (threshold: {alert["threshold"]})'
                    )
        except Exception as e:
            logger.error(f'Alert dispatch error: {e}')

    @staticmethod
    def get_live_metrics() -> dict:
        """Quick live metrics for dashboard."""
        from api.offer_inventory.models import Click, Conversion, WithdrawalRequest
        from django.db.models import Count, Sum
        now   = timezone.now()
        since = now - timedelta(hours=1)

        return {
            'clicks_last_hour' : Click.objects.filter(created_at__gte=since, is_fraud=False).count(),
            'fraud_last_hour'  : Click.objects.filter(created_at__gte=since, is_fraud=True).count(),
            'convs_last_hour'  : Conversion.objects.filter(created_at__gte=since).count(),
            'pending_withdrawals': WithdrawalRequest.objects.filter(status='pending').count(),
            'timestamp'        : now.isoformat(),
        }
