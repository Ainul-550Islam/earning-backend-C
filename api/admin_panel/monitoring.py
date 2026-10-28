# api/admin_panel/monitoring.py
"""
Admin Panel Monitoring — Real-time system monitoring, metrics, SLA tracking,
alert rules, uptime monitoring, performance monitoring.
Calls api.alerts for alert creation — never duplicates.
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    name: str
    value: float
    unit: str = ''
    tags: Dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: timezone.now().isoformat())

    def to_dict(self) -> Dict:
        return {'name': self.name, 'value': self.value, 'unit': self.unit,
                'tags': self.tags, 'timestamp': self.timestamp}


@dataclass
class AlertThreshold:
    metric: str
    warning_gt: Optional[float] = None
    critical_gt: Optional[float] = None
    warning_lt: Optional[float] = None
    critical_lt: Optional[float] = None
    window_minutes: int = 5


class MetricsCollector:
    """Collects and stores platform metrics."""

    BUFFER_KEY = 'admin_panel:metrics_buffer'
    BUFFER_SIZE = 10000

    def record(self, name: str, value: float, unit: str = '', **tags) -> None:
        point = MetricPoint(name=name, value=value, unit=unit, tags=tags)
        try:
            buf = cache.get(self.BUFFER_KEY) or []
            buf.insert(0, point.to_dict())
            cache.set(self.BUFFER_KEY, buf[:self.BUFFER_SIZE], 3600)
        except Exception:
            pass

    def get_metric(self, name: str, minutes: int = 60) -> List[Dict]:
        buf = cache.get(self.BUFFER_KEY) or []
        cutoff = (timezone.now() - timedelta(minutes=minutes)).isoformat()
        return [p for p in buf if p['name'] == name and p['timestamp'] >= cutoff]

    def get_latest(self, name: str) -> Optional[float]:
        points = self.get_metric(name, minutes=5)
        return points[0]['value'] if points else None

    def get_avg(self, name: str, minutes: int = 60) -> float:
        points = self.get_metric(name, minutes)
        if not points:
            return 0.0
        return sum(p['value'] for p in points) / len(points)

    def get_summary(self) -> Dict:
        return {
            'total_users': self.get_latest('platform.users.total') or 0,
            'online_users': self.get_latest('platform.users.online') or 0,
            'revenue_today': self.get_latest('platform.revenue.today') or 0,
            'pending_payouts': self.get_latest('platform.payouts.pending') or 0,
            'fraud_alerts_24h': self.get_latest('platform.fraud.alerts_24h') or 0,
            'system_health': self.get_latest('platform.system.health_score') or 100,
            'api_response_ms': self.get_avg('platform.api.response_ms'),
        }


class SLAMonitor:
    """SLA (Service Level Agreement) tracking."""

    SLAS = {
        'api_response_time':   {'target_ms': 200,   'critical_ms': 1000},
        'payout_processing':   {'target_hours': 24,  'critical_hours': 48},
        'kyc_review_time':     {'target_hours': 48,  'critical_hours': 72},
        'support_first_reply': {'target_hours': 4,   'critical_hours': 24},
        'fraud_review':        {'target_hours': 2,   'critical_hours': 6},
        'uptime':              {'target_pct': 99.9,  'critical_pct': 99.0},
    }

    def check_all(self) -> Dict[str, Dict]:
        results = {}
        for sla_name, thresholds in self.SLAS.items():
            status = self._check_sla(sla_name, thresholds)
            results[sla_name] = status
        return results

    def _check_sla(self, sla_name: str, thresholds: Dict) -> Dict:
        cached = cache.get(f'admin_panel:sla:{sla_name}')
        if cached:
            return cached
        return {'sla': sla_name, 'status': 'unknown', 'thresholds': thresholds}

    def get_uptime(self, hours: int = 24) -> float:
        """Calculate system uptime percentage."""
        downtime_minutes = cache.get('admin_panel:downtime_minutes_24h', 0)
        total_minutes = hours * 60
        uptime_pct = max(0.0, (total_minutes - downtime_minutes) / total_minutes * 100)
        return round(uptime_pct, 3)


class AlertEngine:
    """Alert creation engine — calls api.alerts to create alerts."""

    def check_thresholds(self, metrics: Dict[str, float]) -> List[Dict]:
        """Check metrics against thresholds and create alerts."""
        thresholds = self._load_thresholds()
        alerts_created = []
        for threshold in thresholds:
            metric_val = metrics.get(threshold.metric)
            if metric_val is None:
                continue
            severity = self._evaluate(metric_val, threshold)
            if severity:
                alert = self._create_alert(threshold.metric, metric_val, severity)
                if alert:
                    alerts_created.append(alert)
        return alerts_created

    def _evaluate(self, value: float, threshold: AlertThreshold) -> Optional[str]:
        if threshold.critical_gt and value > threshold.critical_gt:
            return 'critical'
        if threshold.critical_lt and value < threshold.critical_lt:
            return 'critical'
        if threshold.warning_gt and value > threshold.warning_gt:
            return 'warning'
        if threshold.warning_lt and value < threshold.warning_lt:
            return 'warning'
        return None

    def _create_alert(self, metric: str, value: float, severity: str) -> Optional[Dict]:
        try:
            from api.alerts.models import AlertLog
            alert = AlertLog.objects.create(
                alert_type=f'metric_{metric.replace(".", "_")}',
                severity=severity,
                message=f"Metric '{metric}' = {value} ({severity})",
                data={'metric': metric, 'value': value},
            )
            return {'id': alert.pk, 'metric': metric, 'severity': severity}
        except Exception as e:
            logger.debug(f"[AlertEngine._create_alert] {e}")
            return None

    def _load_thresholds(self) -> List[AlertThreshold]:
        return [
            AlertThreshold('platform.fraud.fraud_score', warning_gt=70, critical_gt=90),
            AlertThreshold('platform.api.response_ms', warning_gt=500, critical_gt=2000),
            AlertThreshold('platform.queue.size', warning_gt=1000, critical_gt=5000),
            AlertThreshold('platform.system.health_score', warning_lt=80, critical_lt=60),
            AlertThreshold('platform.users.online', warning_lt=0, critical_lt=0),
        ]


# Global instances
metrics = MetricsCollector()
sla_monitor = SLAMonitor()
alert_engine = AlertEngine()


def record_api_call(endpoint: str, duration_ms: float, status_code: int) -> None:
    """Record API call metric."""
    metrics.record('platform.api.response_ms', duration_ms, unit='ms', endpoint=endpoint)
    if status_code >= 500:
        metrics.record('platform.api.errors', 1, status=str(status_code))


def get_system_health_score() -> int:
    """0-100 health score based on all monitored metrics."""
    score = 100
    try:
        uptime = sla_monitor.get_uptime()
        if uptime < 99.0:
            score -= int((99.0 - uptime) * 10)
        error_rate = metrics.get_latest('platform.api.error_rate') or 0
        if error_rate > 5:
            score -= 20
        elif error_rate > 1:
            score -= 10
    except Exception:
        pass
    return max(0, min(100, score))