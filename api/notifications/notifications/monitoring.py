# earning_backend/api/notifications/monitoring.py
"""Monitoring — Real-time system monitoring for the notification system."""
import logging, time, threading
from collections import defaultdict, deque
from typing import Dict, List
from django.core.cache import cache
from django.utils import timezone
logger = logging.getLogger(__name__)

ALERT_THRESHOLDS = {
    "error_rate_pct": 10.0, "avg_latency_ms": 3000,
    "queue_depth": 5000,    "dlq_depth": 10,
}

class MetricWindow:
    def __init__(self, window_seconds=3600):
        self.window = window_seconds
        self._data = deque()
        self._lock = threading.Lock()
    def record(self, value, success=True):
        now = time.time()
        with self._lock:
            self._data.append((now, value, success))
            cutoff = now - self.window
            while self._data and self._data[0][0] < cutoff:
                self._data.popleft()
    def stats(self):
        with self._lock:
            data = list(self._data)
        if not data:
            return {"count":0,"avg":0,"max":0,"min":0,"error_rate":0,"p95":0,"p99":0}
        values = sorted([v for _,v,_ in data])
        errors = sum(1 for _,_,ok in data if not ok)
        count = len(data)
        def pct(vals, p):
            idx = int(len(vals)*p/100)
            return vals[min(idx, len(vals)-1)]
        return {
            "count": count, "avg": round(sum(values)/count,2),
            "max": round(max(values),2), "min": round(min(values),2),
            "error_rate": round(errors/count*100,2),
            "p95": round(pct(values,95),2), "p99": round(pct(values,99),2),
        }

class NotificationMonitor:
    """Central monitoring service for the notification system."""
    def __init__(self):
        self._channel_metrics = defaultdict(lambda: MetricWindow(3600))
        self._provider_metrics = defaultdict(lambda: MetricWindow(3600))
        self._alerts: List[Dict] = []
        self._lock = threading.Lock()

    def record_send(self, channel, latency_ms, success, provider="", error=""):
        self._channel_metrics[channel].record(latency_ms, success)
        if provider:
            self._provider_metrics[provider].record(latency_ms, success)
        stats = self._channel_metrics[channel].stats()
        if stats["error_rate"] > ALERT_THRESHOLDS["error_rate_pct"]:
            self._raise_alert(f"HIGH_ERROR_RATE_{channel.upper()}",
                f"Channel '{channel}' error rate {stats['error_rate']:.1f}%", "warning")
        if stats["avg"] > ALERT_THRESHOLDS["avg_latency_ms"]:
            self._raise_alert(f"HIGH_LATENCY_{channel.upper()}",
                f"Channel '{channel}' avg latency {stats['avg']:.0f}ms", "warning")

    def record_delivery(self, channel, delivered):
        self._channel_metrics[f"{channel}_delivery"].record(1 if delivered else 0, delivered)

    def get_channel_stats(self, channel=None):
        if channel:
            return {channel: self._channel_metrics[channel].stats()}
        return {ch: m.stats() for ch, m in self._channel_metrics.items()}

    def get_provider_stats(self, provider=None):
        if provider:
            return {provider: self._provider_metrics[provider].stats()}
        return {p: m.stats() for p, m in self._provider_metrics.items()}

    def get_summary(self):
        return {
            "timestamp": timezone.now().isoformat(),
            "channels": self.get_channel_stats(),
            "providers": self.get_provider_stats(),
            "queues": self._get_queue_depths(),
            "health": self._get_service_health(),
            "alerts": self._alerts[-20:],
            "thresholds": ALERT_THRESHOLDS,
        }

    def _get_queue_depths(self):
        try:
            from django.conf import settings
            import redis
            r = redis.from_url(getattr(settings,"CELERY_BROKER_URL","redis://localhost:6379/0"))
            queues = ["notifications_high","notifications_push","notifications_email",
                      "notifications_sms","notifications_campaigns","notifications_retry"]
            return {q: r.llen(q) for q in queues}
        except Exception:
            return {}

    def _get_service_health(self):
        try:
            from notifications.integration_system.health_check import health_checker
            return health_checker.get_summary()
        except Exception:
            return {}

    def _raise_alert(self, alert_id, message, severity="warning"):
        cooldown_key = f"monitor:alert:{alert_id}"
        if cache.get(cooldown_key):
            return
        alert = {"alert_id": alert_id, "message": message, "severity": severity,
                  "raised_at": timezone.now().isoformat()}
        with self._lock:
            self._alerts.append(alert)
            if len(self._alerts) > 500:
                self._alerts = self._alerts[-250:]
        cache.set(cooldown_key, "1", 3600)
        logger.warning(f"MONITOR ALERT [{severity.upper()}]: {message}")
        if severity == "critical":
            self._notify_admin(alert)

    def _notify_admin(self, alert):
        try:
            from django.contrib.auth import get_user_model
            from notifications.services.NotificationService import notification_service
            User = get_user_model()
            for admin in User.objects.filter(is_staff=True, is_active=True)[:3]:
                notification_service.create_notification(
                    user=admin, title=f"🚨 {alert['alert_id']}",
                    message=alert["message"], notification_type="system_alert",
                    channel="in_app", priority="critical",
                )
        except Exception as exc:
            logger.error(f"_notify_admin: {exc}")

    def clear_alerts(self):
        with self._lock:
            self._alerts.clear()

monitor = NotificationMonitor()

def run_monitoring_check():
    try:
        summary = monitor.get_summary()
        logger.info(f"Monitoring: {len(summary['channels'])} channels, alerts={len(summary['alerts'])}")
        return summary
    except Exception as exc:
        logger.error(f"run_monitoring_check: {exc}")
        return {}
