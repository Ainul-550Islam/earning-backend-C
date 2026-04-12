"""
Automatic Failover — Triggers failover automatically without human intervention.
Monitors health checks and fires when threshold is crossed.
"""
import logging
import threading
import time
from datetime import datetime
from typing import Optional, Callable, List

from .failover_detector import FailoverDetector
from ..enums import FailoverType, HealthStatus

logger = logging.getLogger(__name__)


class AutomaticFailover:
    """
    Fully automated failover system.
    Continuously monitors primary nodes and triggers failover when the
    consecutive failure threshold is crossed, subject to cooldown rules.

    Usage:
        af = AutomaticFailover(failover_service, detector, config)
        af.register_pair("db-primary", "db-replica")
        af.start()  # runs in background thread
    """

    def __init__(self, failover_service, detector: FailoverDetector = None,
                 config: dict = None):
        self.svc = failover_service
        self.detector = detector or FailoverDetector()
        self.config = config or {}
        self._pairs: List[dict] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._on_failover: Optional[Callable] = None
        self.check_interval = config.get("check_interval_seconds", 30) if config else 30
        self.enabled = config.get("enabled", True) if config else True

    def register_pair(self, primary: str, secondary: str,
                       primary_port: int = 5432,
                       check_type: str = "tcp") -> dict:
        """Register a primary/secondary pair for automatic monitoring."""
        pair = {
            "primary": primary,
            "secondary": secondary,
            "primary_port": primary_port,
            "check_type": check_type,
            "last_failover": None,
            "enabled": True,
        }
        self._pairs.append(pair)
        logger.info(f"Auto-failover pair registered: {primary} -> {secondary}")
        return pair

    def unregister_pair(self, primary: str):
        """Remove a primary/secondary pair from monitoring."""
        self._pairs = [p for p in self._pairs if p["primary"] != primary]
        logger.info(f"Auto-failover pair removed: {primary}")

    def set_on_failover_callback(self, callback: Callable):
        """Set a callback to be called when failover is triggered."""
        self._on_failover = callback

    def trigger(self, primary: str, secondary: str, reason: str) -> dict:
        """Immediately trigger failover for a primary/secondary pair."""
        if not self.enabled:
            logger.warning("Auto-failover is disabled — skipping")
            return {"triggered": False, "reason": "auto_failover_disabled"}
        logger.critical(
            f"AUTO-FAILOVER TRIGGERED: {primary} -> {secondary} | Reason: {reason}"
        )
        try:
            result = self.svc.trigger_failover(
                primary_node=primary,
                secondary_node=secondary,
                failover_type=FailoverType.AUTOMATIC,
                reason=reason,
                triggered_by="auto_failover",
            )
            if self._on_failover:
                try:
                    self._on_failover(result)
                except Exception as cb_err:
                    logger.error(f"Failover callback error: {cb_err}")
            return {"triggered": True, "result": result}
        except Exception as e:
            logger.error(f"Auto-failover execution failed: {e}")
            return {"triggered": False, "error": str(e)}

    def start(self):
        """Start the background monitoring thread."""
        if not self.enabled:
            logger.info("Auto-failover monitoring disabled — not starting")
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info(
            f"Auto-failover monitoring started: {len(self._pairs)} pairs, "
            f"interval={self.check_interval}s"
        )

    def stop(self):
        """Stop the background monitoring thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Auto-failover monitoring stopped")

    def get_status(self) -> dict:
        """Get current status of the auto-failover system."""
        return {
            "enabled": self.enabled,
            "running": self._running,
            "monitored_pairs": len(self._pairs),
            "check_interval_seconds": self.check_interval,
            "pairs": [
                {"primary": p["primary"], "secondary": p["secondary"],
                 "enabled": p.get("enabled", True),
                 "last_failover": p.get("last_failover")}
                for p in self._pairs
            ],
        }

    def disable(self):
        """Temporarily disable auto-failover (e.g. during maintenance)."""
        self.enabled = False
        logger.warning("Auto-failover DISABLED")

    def enable(self):
        """Re-enable auto-failover."""
        self.enabled = True
        logger.info("Auto-failover ENABLED")

    def _monitor_loop(self):
        """Background thread: continuously checks all registered pairs."""
        logger.info("Auto-failover monitor loop started")
        while self._running:
            for pair in self._pairs:
                if not pair.get("enabled", True):
                    continue
                primary = pair["primary"]
                secondary = pair["secondary"]
                try:
                    status = self._check_primary(primary, pair["primary_port"],
                                                  pair.get("check_type", "tcp"))
                    if status == HealthStatus.DOWN:
                        count = self.detector.record_failure(primary)
                        logger.warning(
                            f"Primary {primary} is DOWN "
                            f"(consecutive failures: {count})"
                        )
                        if self.detector.should_failover(primary):
                            reason = (
                                f"Automatic failover: {primary} failed "
                                f"{count} consecutive health checks"
                            )
                            result = self.trigger(primary, secondary, reason)
                            if result.get("triggered"):
                                pair["last_failover"] = datetime.utcnow().isoformat()
                                self.detector.reset_failures(primary)
                    else:
                        self.detector.reset_failures(primary)
                except Exception as e:
                    logger.error(f"Monitor error for {primary}: {e}")
            time.sleep(self.check_interval)
        logger.info("Auto-failover monitor loop stopped")

    def _check_primary(self, host: str, port: int, check_type: str) -> HealthStatus:
        """Check if the primary is healthy."""
        from .health_checker import HealthChecker
        checker = HealthChecker()
        if check_type == "http":
            result = checker.check_http(f"http://{host}/health")
        else:
            result = checker.check_tcp(host, port, timeout=5)
        return result.get("status", HealthStatus.UNKNOWN)
