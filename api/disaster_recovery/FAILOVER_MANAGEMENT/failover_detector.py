"""
Failover Detector — Continuously monitors primary nodes and triggers failover
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ..enums import HealthStatus, FailoverType
from ..constants import FAILOVER_HEALTH_CHECK_FAILURES, HEALTH_CHECK_INTERVAL

logger = logging.getLogger(__name__)


class FailoverDetector:
    """
    Monitors component health and determines when automatic failover
    should be triggered. Uses consecutive failure counting to avoid
    triggering on transient network blips.
    """

    def __init__(self, db_session=None, alert_callback=None):
        self.db = db_session
        self.alert_callback = alert_callback
        self._failure_counts: Dict[str, int] = {}
        self._last_failover: Dict[str, datetime] = {}

    def check_component(self, component_name: str) -> HealthStatus:
        """Check if a component is healthy."""
        from ..repository import MonitoringRepository
        if not self.db:
            return HealthStatus.UNKNOWN
        repo = MonitoringRepository(self.db)
        latest = repo.get_latest_health(component_name)
        if not latest:
            return HealthStatus.UNKNOWN
        # Check if the log is recent (within 2x check interval)
        age = (datetime.utcnow() - latest.checked_at).total_seconds()
        if age > HEALTH_CHECK_INTERVAL * 2:
            return HealthStatus.UNKNOWN
        return latest.status

    def record_failure(self, component: str) -> int:
        """Increment failure counter and return current count."""
        self._failure_counts[component] = self._failure_counts.get(component, 0) + 1
        count = self._failure_counts[component]
        logger.warning(f"Health failure {count}/{FAILOVER_HEALTH_CHECK_FAILURES} for {component}")
        return count

    def reset_failures(self, component: str):
        """Reset failure counter when component recovers."""
        if component in self._failure_counts:
            del self._failure_counts[component]
            logger.info(f"Failure counter reset for {component}")

    def should_failover(self, component: str) -> bool:
        """Return True if failover threshold has been crossed."""
        count = self._failure_counts.get(component, 0)
        if count < FAILOVER_HEALTH_CHECK_FAILURES:
            return False
        # Prevent repeated failovers within 10 minutes
        last = self._last_failover.get(component)
        if last and datetime.utcnow() - last < timedelta(minutes=10):
            logger.info(f"Skipping failover for {component} — cooldown active")
            return False
        return True

    def monitor_loop(self, components: List[dict], failover_service=None):
        """
        Main monitoring loop. Run in a background thread/process.
        components = [{"name": "db-primary", "type": "database", "secondary": "db-replica"}]
        """
        logger.info(f"Failover detector started monitoring {len(components)} components")
        while True:
            for comp in components:
                name = comp["name"]
                status = self.check_component(name)
                if status in (HealthStatus.DOWN, HealthStatus.CRITICAL):
                    count = self.record_failure(name)
                    if self.should_failover(name) and failover_service:
                        secondary = comp.get("secondary")
                        if secondary:
                            logger.critical(f"AUTO-FAILOVER: {name} -> {secondary}")
                            self._last_failover[name] = datetime.utcnow()
                            try:
                                failover_service.trigger_failover(
                                    primary_node=name,
                                    secondary_node=secondary,
                                    failover_type=FailoverType.AUTOMATIC,
                                    reason=f"Auto-failover: {count} consecutive failures",
                                    triggered_by="auto"
                                )
                            except Exception as e:
                                logger.error(f"Auto-failover failed: {e}")
                else:
                    self.reset_failures(name)
            time.sleep(HEALTH_CHECK_INTERVAL)
