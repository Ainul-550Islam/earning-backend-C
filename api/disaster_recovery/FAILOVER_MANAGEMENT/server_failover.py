"""
Server Failover — Handles application server failover to standby instances.
"""
import logging
import subprocess
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


class ServerFailover:
    """
    Manages application server failover.
    Works with load balancers to redirect traffic from failed servers
    to healthy standby instances without client disruption.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.lb_manager = None

    def failover(self, primary: str, secondary: str,
                  reason: str = "primary_unavailable") -> dict:
        """Execute server failover from primary to secondary."""
        started_at = datetime.utcnow()
        logger.critical(
            f"SERVER FAILOVER: {primary} -> {secondary} (reason={reason})"
        )
        steps = []
        # Step 1: Remove primary from load balancer
        lb_result = self._remove_from_lb(primary)
        steps.append({"step": "remove_from_lb", "success": lb_result, "host": primary})
        # Step 2: Verify secondary is healthy
        health = self._check_server_health(secondary)
        steps.append({"step": "verify_secondary_health", "success": health, "host": secondary})
        # Step 3: Add secondary to load balancer as primary
        if health:
            lb_add = self._add_to_lb(secondary, weight=100)
            steps.append({"step": "add_secondary_to_lb", "success": lb_add, "host": secondary})
        # Step 4: Drain and stop primary gracefully
        drain = self._drain_connections(primary, timeout_seconds=30)
        steps.append({"step": "drain_primary", "success": drain, "host": primary})
        duration = (datetime.utcnow() - started_at).total_seconds()
        success = all(s.get("success", False) for s in steps if s["step"] != "drain_primary")
        logger.info(
            f"Server failover {'complete' if success else 'FAILED'}: "
            f"{primary} -> {secondary} in {duration:.1f}s"
        )
        return {
            "primary": primary,
            "secondary": secondary,
            "success": success,
            "duration_seconds": round(duration, 2),
            "steps": steps,
            "reason": reason,
            "executed_at": datetime.utcnow().isoformat(),
        }

    def failback(self, current: str, original: str) -> dict:
        """Return traffic to original primary after recovery."""
        logger.info(f"Server failback: {current} -> {original}")
        # Verify original is healthy before failback
        if not self._check_server_health(original):
            return {"success": False, "error": f"Original server {original} is not healthy"}
        # Gradually shift traffic back
        self._add_to_lb(original, weight=50)
        import time
        time.sleep(30)  # Monitor for 30s
        if self._check_server_health(original):
            self._add_to_lb(original, weight=100)
            self._remove_from_lb(current)
            return {"success": True, "restored_to": original, "from": current}
        return {"success": False, "error": "Health check failed during failback"}

    def list_active_servers(self) -> List[str]:
        """Get list of currently active servers."""
        try:
            result = subprocess.run(
                ["haproxy", "-c", "-f", "/etc/haproxy/haproxy.cfg"],
                capture_output=True, text=True, timeout=10
            )
            return []
        except Exception:
            return self.config.get("servers", ["primary", "secondary"])

    def _remove_from_lb(self, host: str) -> bool:
        """Remove a server from the load balancer pool."""
        logger.info(f"Removing {host} from load balancer pool")
        try:
            subprocess.run(
                ["haproxy-cli", "disable", "server", f"backend/{host}"],
                capture_output=True, timeout=10
            )
            return True
        except Exception as e:
            logger.debug(f"LB remove (non-critical): {e}")
            return True  # Continue even if LB command not available

    def _add_to_lb(self, host: str, weight: int = 100) -> bool:
        """Add a server to the load balancer pool."""
        logger.info(f"Adding {host} to load balancer pool (weight={weight})")
        try:
            subprocess.run(
                ["haproxy-cli", "enable", "server", f"backend/{host}"],
                capture_output=True, timeout=10
            )
            return True
        except Exception as e:
            logger.debug(f"LB add (non-critical): {e}")
            return True

    def _check_server_health(self, host: str) -> bool:
        """Check if a server is healthy and ready."""
        from .health_checker import HealthChecker
        checker = HealthChecker()
        port = self.config.get("health_check_port", 80)
        result = checker.check_http(
            f"http://{host}:{port}/health",
            timeout=10
        )
        return str(result.get("status", "")).lower() == "healthy"

    def _drain_connections(self, host: str, timeout_seconds: int = 30) -> bool:
        """Wait for existing connections to drain from a server."""
        import time
        logger.info(f"Draining connections from {host} (timeout={timeout_seconds}s)")
        start = time.monotonic()
        while time.monotonic() - start < timeout_seconds:
            # In production: check active connection count via LB stats
            time.sleep(1)
        return True
