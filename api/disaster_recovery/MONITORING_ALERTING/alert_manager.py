"""
Alert Manager — Evaluates alert rules and dispatches notifications
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from .alert_rules import AlertRule, AlertRuleEngine
from .notification_dispatcher import NotificationDispatcher

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Central alert management:
    - Evaluates rules against incoming metrics
    - Deduplicates and groups related alerts
    - Manages alert lifecycle (firing -> resolved)
    - Dispatches notifications via configured channels
    """

    def __init__(self, db_session=None, notification_config: dict = None):
        self.db = db_session
        self.rule_engine = AlertRuleEngine()
        self.dispatcher = NotificationDispatcher(notification_config or {})
        self._active_alerts: dict = {}
        self._cooldowns: dict = {}

    def evaluate(self, metric_name: str, value: float, labels: dict = None) -> List[dict]:
        """Evaluate metric against all rules and fire alerts as needed."""
        triggered = []
        matching_rules = self.rule_engine.get_matching_rules(metric_name)
        for rule in matching_rules:
            if rule.evaluate(value):
                alert = self._create_alert(rule, metric_name, value, labels or {})
                if self._should_fire(alert):
                    self._fire_alert(alert)
                    triggered.append(alert)
        return triggered

    def _create_alert(self, rule: AlertRule, metric: str, value: float, labels: dict) -> dict:
        return {
            "id": f"{rule.name}_{metric}_{datetime.utcnow().timestamp()}",
            "rule_name": rule.name,
            "metric": metric,
            "value": value,
            "threshold": rule.threshold,
            "severity": rule.severity,
            "labels": labels,
            "fired_at": datetime.utcnow().isoformat(),
            "message": rule.message_template.format(metric=metric, value=value, threshold=rule.threshold),
        }

    def _should_fire(self, alert: dict) -> bool:
        """Check cooldown to prevent alert storms."""
        key = f"{alert['rule_name']}_{alert['metric']}"
        last_fired = self._cooldowns.get(key)
        from ..constants import ALERT_COOLDOWN_SECONDS
        if last_fired and (datetime.utcnow() - last_fired).total_seconds() < ALERT_COOLDOWN_SECONDS:
            return False
        return True

    def _fire_alert(self, alert: dict):
        key = f"{alert['rule_name']}_{alert['metric']}"
        self._cooldowns[key] = datetime.utcnow()
        self._active_alerts[alert["id"]] = alert
        logger.warning(f"ALERT FIRED: [{alert['severity']}] {alert['message']}")
        self.dispatcher.dispatch(alert)

    def resolve_alert(self, alert_id: str):
        if alert_id in self._active_alerts:
            alert = self._active_alerts.pop(alert_id)
            alert["resolved_at"] = datetime.utcnow().isoformat()
            logger.info(f"Alert resolved: {alert_id}")
            self.dispatcher.dispatch_resolution(alert)

    def get_active_alerts(self) -> List[dict]:
        return list(self._active_alerts.values())

    def get_alert_summary(self) -> dict:
        from ..enums import AlertSeverity
        counts = {}
        for alert in self._active_alerts.values():
            sev = alert.get("severity", "info")
            counts[sev] = counts.get(sev, 0) + 1
        return {"total_active": len(self._active_alerts), "by_severity": counts}
