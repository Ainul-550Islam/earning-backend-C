"""
Resource Monitor — Tracks CPU, memory, disk, and network resources across all system components.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """
    Comprehensive resource monitoring for the DR system infrastructure.
    Collects metrics from all system components, detects threshold violations,
    and integrates with the alert manager to fire alerts when thresholds are exceeded.
    """

    # Default alert thresholds
    THRESHOLDS = {
        "cpu_percent": {"warning": 80.0, "critical": 95.0},
        "memory_percent": {"warning": 85.0, "critical": 95.0},
        "disk_percent": {"warning": 80.0, "critical": 90.0},
        "network_latency_ms": {"warning": 100.0, "critical": 500.0},
        "replication_lag_seconds": {"warning": 30.0, "critical": 120.0},
    }

    def __init__(self, db_session=None, alert_manager=None, config: dict = None):
        self.db = db_session
        self.alert_manager = alert_manager
        self.config = config or {}
        self._history: List[dict] = []
        self._max_history = config.get("max_history", 1000) if config else 1000

    def collect_all(self) -> dict:
        """Collect all system resource metrics in one call."""
        from .system_monitor import SystemMonitor
        sys_mon = SystemMonitor()
        sys_metrics = sys_mon.collect()
        metrics = {
            "collected_at": datetime.utcnow().isoformat(),
            "system": sys_metrics,
            "alerts_fired": [],
        }
        # Check thresholds and fire alerts
        for metric_name, thresholds in self.THRESHOLDS.items():
            value = sys_metrics.get(metric_name)
            if value is None:
                continue
            if value >= thresholds.get("critical", 999):
                alert = self._fire_alert(metric_name, value, "critical", thresholds["critical"])
                if alert:
                    metrics["alerts_fired"].append(alert)
            elif value >= thresholds.get("warning", 999):
                alert = self._fire_alert(metric_name, value, "warning", thresholds["warning"])
                if alert:
                    metrics["alerts_fired"].append(alert)
        # Persist to history
        self._history.append(metrics)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        # Persist to DB if available
        if self.db:
            self._persist_metrics(metrics)
        return metrics

    def get_cpu_history(self, minutes: int = 60) -> List[dict]:
        """Get CPU utilization history for the past N minutes."""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        history = []
        for entry in self._history:
            ts_str = entry.get("collected_at", "")
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts >= cutoff:
                    history.append({
                        "timestamp": ts_str,
                        "cpu_percent": entry.get("system", {}).get("cpu_percent", 0),
                    })
            except Exception:
                pass
        return history

    def get_memory_history(self, minutes: int = 60) -> List[dict]:
        """Get memory utilization history."""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        return [
            {"timestamp": e["collected_at"],
             "memory_percent": e.get("system", {}).get("memory_percent", 0)}
            for e in self._history
            if self._is_within_window(e.get("collected_at", ""), cutoff)
        ]

    def get_disk_history(self, minutes: int = 60) -> List[dict]:
        """Get disk utilization history."""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        return [
            {"timestamp": e["collected_at"],
             "disk_percent": e.get("system", {}).get("disk_percent", 0)}
            for e in self._history
            if self._is_within_window(e.get("collected_at", ""), cutoff)
        ]

    def get_current_metrics(self) -> dict:
        """Get the most recent resource metrics."""
        if self._history:
            return self._history[-1]
        return self.collect_all()

    def check_threshold_violations(self) -> List[dict]:
        """Check current metrics against all thresholds and return violations."""
        metrics = self.get_current_metrics()
        sys = metrics.get("system", {})
        violations = []
        for metric, thresholds in self.THRESHOLDS.items():
            value = sys.get(metric)
            if value is None:
                continue
            if value >= thresholds.get("critical", 999):
                violations.append({
                    "metric": metric,
                    "value": value,
                    "threshold": thresholds["critical"],
                    "level": "critical",
                })
            elif value >= thresholds.get("warning", 999):
                violations.append({
                    "metric": metric,
                    "value": value,
                    "threshold": thresholds["warning"],
                    "level": "warning",
                })
        return violations

    def get_summary(self) -> dict:
        """Get a summary of current resource utilization."""
        metrics = self.get_current_metrics()
        sys = metrics.get("system", {})
        violations = self.check_threshold_violations()
        return {
            "collected_at": metrics.get("collected_at"),
            "cpu_percent": sys.get("cpu_percent"),
            "memory_percent": sys.get("memory_percent"),
            "disk_percent": sys.get("disk_percent"),
            "threshold_violations": len(violations),
            "violation_levels": list({v["level"] for v in violations}),
            "status": "critical" if any(v["level"] == "critical" for v in violations)
                      else "warning" if violations else "healthy",
        }

    def update_threshold(self, metric: str, warning: float = None, critical: float = None):
        """Update alert thresholds for a specific metric."""
        if metric not in self.THRESHOLDS:
            self.THRESHOLDS[metric] = {}
        if warning is not None:
            self.THRESHOLDS[metric]["warning"] = warning
        if critical is not None:
            self.THRESHOLDS[metric]["critical"] = critical
        logger.info(f"Threshold updated: {metric} warning={warning} critical={critical}")

    def _fire_alert(self, metric: str, value: float,
                    level: str, threshold: float) -> Optional[dict]:
        """Fire an alert if alert manager is configured."""
        if not self.alert_manager:
            logger.warning(f"Resource threshold exceeded: {metric}={value:.1f} (level={level})")
            return {"metric": metric, "value": value, "level": level}
        alerts = self.alert_manager.evaluate(metric, value)
        return {"metric": metric, "value": value, "level": level} if alerts else None

    def _persist_metrics(self, metrics: dict):
        """Save metrics to database."""
        try:
            from ..repository import MonitoringRepository
            from ..enums import HealthStatus
            sys = metrics.get("system", {})
            cpu = sys.get("cpu_percent", 0)
            status = (HealthStatus.CRITICAL if cpu >= 95
                      else HealthStatus.DEGRADED if cpu >= 80
                      else HealthStatus.HEALTHY)
            repo = MonitoringRepository(self.db)
            repo.save_health_check({
                "component_name": "system",
                "component_type": "os",
                "status": status,
                "cpu_percent": cpu,
                "memory_percent": sys.get("memory_percent"),
                "disk_percent": sys.get("disk_percent"),
            })
        except Exception as e:
            logger.debug(f"Metrics persist error: {e}")

    @staticmethod
    def _is_within_window(ts_str: str, cutoff: datetime) -> bool:
        try:
            return datetime.fromisoformat(ts_str) >= cutoff
        except Exception:
            return False
