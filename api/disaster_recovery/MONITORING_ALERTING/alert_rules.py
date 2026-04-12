"""
Alert Rules — Defines and evaluates alert rules for system metrics
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Callable

from ..enums import AlertSeverity

logger = logging.getLogger(__name__)


@dataclass
class AlertRule:
    name: str
    metric: str
    condition: str          # "gt", "lt", "eq", "gte", "lte"
    threshold: float
    severity: AlertSeverity
    message_template: str
    description: str = ""
    duration_seconds: int = 0   # Must be triggered for N seconds before firing
    enabled: bool = True

    def evaluate(self, value: float) -> bool:
        if not self.enabled:
            return False
        ops = {
            "gt": value > self.threshold,
            "gte": value >= self.threshold,
            "lt": value < self.threshold,
            "lte": value <= self.threshold,
            "eq": value == self.threshold,
        }
        return ops.get(self.condition, False)


class AlertRuleEngine:
    """Registry and evaluator for all alert rules."""

    def __init__(self):
        self._rules: List[AlertRule] = []
        self._load_default_rules()

    def _load_default_rules(self):
        """Load default DR system alert rules."""
        defaults = [
            AlertRule(
                name="high_cpu", metric="cpu_percent",
                condition="gt", threshold=85.0,
                severity=AlertSeverity.WARNING,
                message_template="CPU usage {value:.1f}% exceeds {threshold}%",
                description="High CPU utilization"
            ),
            AlertRule(
                name="critical_cpu", metric="cpu_percent",
                condition="gt", threshold=95.0,
                severity=AlertSeverity.CRITICAL,
                message_template="CRITICAL: CPU at {value:.1f}%",
                description="CPU critically high"
            ),
            AlertRule(
                name="high_memory", metric="memory_percent",
                condition="gt", threshold=90.0,
                severity=AlertSeverity.WARNING,
                message_template="Memory usage {value:.1f}% exceeds {threshold}%",
            ),
            AlertRule(
                name="high_disk", metric="disk_percent",
                condition="gt", threshold=85.0,
                severity=AlertSeverity.WARNING,
                message_template="Disk usage {value:.1f}% exceeds {threshold}%",
            ),
            AlertRule(
                name="critical_disk", metric="disk_percent",
                condition="gt", threshold=95.0,
                severity=AlertSeverity.CRITICAL,
                message_template="CRITICAL: Disk at {value:.1f}% — immediate action required",
            ),
            AlertRule(
                name="high_replication_lag", metric="replication_lag_seconds",
                condition="gt", threshold=30.0,
                severity=AlertSeverity.WARNING,
                message_template="Replication lag {value:.1f}s exceeds {threshold}s",
            ),
            AlertRule(
                name="critical_replication_lag", metric="replication_lag_seconds",
                condition="gt", threshold=120.0,
                severity=AlertSeverity.CRITICAL,
                message_template="CRITICAL: Replication lag {value:.1f}s — failover risk",
            ),
            AlertRule(
                name="backup_failed", metric="backup_failure_count",
                condition="gt", threshold=0,
                severity=AlertSeverity.ERROR,
                message_template="{value:.0f} backup(s) failed in last hour",
            ),
            AlertRule(
                name="sla_breach_risk", metric="uptime_percent",
                condition="lt", threshold=99.9,
                severity=AlertSeverity.WARNING,
                message_template="Uptime {value:.3f}% below SLA target {threshold}%",
            ),
            AlertRule(
                name="network_latency_high", metric="network_latency_ms",
                condition="gt", threshold=200.0,
                severity=AlertSeverity.WARNING,
                message_template="Network latency {value:.1f}ms exceeds {threshold}ms",
            ),
        ]
        self._rules.extend(defaults)
        logger.info(f"Loaded {len(defaults)} default alert rules")

    def add_rule(self, rule: AlertRule):
        self._rules.append(rule)
        logger.info(f"Added alert rule: {rule.name}")

    def remove_rule(self, rule_name: str):
        self._rules = [r for r in self._rules if r.name != rule_name]

    def get_matching_rules(self, metric: str) -> List[AlertRule]:
        return [r for r in self._rules if r.metric == metric and r.enabled]

    def list_rules(self) -> List[dict]:
        return [
            {"name": r.name, "metric": r.metric, "condition": r.condition,
             "threshold": r.threshold, "severity": r.severity, "enabled": r.enabled}
            for r in self._rules
        ]

    def enable_rule(self, name: str):
        for r in self._rules:
            if r.name == name:
                r.enabled = True

    def disable_rule(self, name: str):
        for r in self._rules:
            if r.name == name:
                r.enabled = False
