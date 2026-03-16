# api/promotions/monitoring/performance_alert.py
# Performance Alert — P95 latency, error rate, DB slowness threshold alerts
import logging
from django.core.cache import cache
from .alert_system import AlertSystem, AlertSeverity
logger = logging.getLogger('monitoring.perf_alert')

class PerformanceAlertManager:
    """Thresholds cross করলে alert পাঠায়।"""
    THRESHOLDS = {
        'p95_response_ms':  2000,
        'error_rate':       0.05,
        'db_avg_ms':        200,
        'queue_depth':      10000,
    }

    def check_and_alert(self, metrics: dict) -> list:
        alerts = []
        alerter = AlertSystem()

        if metrics.get('p95_response_ms', 0) > self.THRESHOLDS['p95_response_ms']:
            msg = f'P95 latency {metrics["p95_response_ms"]:.0f}ms (threshold: {self.THRESHOLDS["p95_response_ms"]}ms)'
            alerter.send_system_alert('API Latency', msg, AlertSeverity.WARNING)
            alerts.append(msg)

        if metrics.get('error_rate', 0) > self.THRESHOLDS['error_rate']:
            msg = f'Error rate {metrics["error_rate"]*100:.1f}% (threshold: {self.THRESHOLDS["error_rate"]*100:.0f}%)'
            alerter.send_system_alert('Error Rate', msg, AlertSeverity.CRITICAL)
            alerts.append(msg)

        return alerts
