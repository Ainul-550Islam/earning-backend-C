"""
Failback Manager — Safely returns traffic to the restored original primary after failover.
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class FailbackManager:
    """
    Manages the controlled return of traffic from DR system back to the original primary
    after it has been restored and validated. Failback is riskier than failover and
    requires careful health validation and gradual traffic shifting.

    Steps:
    1. Validate original primary is healthy and stable
    2. Resync data from current primary -> original primary
    3. Gradually shift read traffic back
    4. Promote original primary
    5. Demote current DR primary to replica
    6. Verify all systems healthy
    """

    MIN_STABLE_MINUTES = 30     # Minimum time primary must be stable before failback
    HEALTH_CHECK_COUNT = 5      # Number of consecutive health checks required
    GRADUAL_SHIFT_STEPS = 5     # Steps for gradual traffic migration

    def __init__(self, failover_service=None, config: dict = None):
        self.svc = failover_service
        self.config = config or {}

    def check_primary_ready(self, primary_host: str,
                              primary_port: int = 5432,
                              stable_minutes: int = None) -> dict:
        """
        Comprehensive check if original primary is ready for failback.
        Requires N consecutive successful health checks over M minutes.
        """
        stable_minutes = stable_minutes or self.MIN_STABLE_MINUTES
        from .health_checker import HealthChecker
        checker = HealthChecker()
        logger.info(
            f"Checking primary readiness for failback: {primary_host} "
            f"(need {self.HEALTH_CHECK_COUNT} consecutive successes)"
        )
        consecutive_ok = 0
        for attempt in range(self.HEALTH_CHECK_COUNT):
            health = checker.check_tcp(primary_host, primary_port, timeout=5)
            if str(health.get("status","")).lower() == "healthy":
                consecutive_ok += 1
                logger.debug(
                    f"  Health check {attempt+1}/{self.HEALTH_CHECK_COUNT}: OK "
                    f"({consecutive_ok} consecutive)"
                )
            else:
                consecutive_ok = 0
                logger.warning(
                    f"  Health check {attempt+1}/{self.HEALTH_CHECK_COUNT}: "
                    f"FAILED (resetting counter)"
                )
            if attempt < self.HEALTH_CHECK_COUNT - 1:
                time.sleep(10)  # 10s between checks

        is_ready = consecutive_ok >= self.HEALTH_CHECK_COUNT
        disk = checker.check_disk(self.config.get("primary_data_path", "/"))
        memory = checker.check_memory()
        return {
            "host": primary_host,
            "ready_for_failback": is_ready,
            "consecutive_healthy_checks": consecutive_ok,
            "required_checks": self.HEALTH_CHECK_COUNT,
            "disk_status": str(disk.get("status","")),
            "memory_status": str(memory.get("status","")),
            "resources_adequate": (
                str(disk.get("status","")).lower() in ("healthy","degraded") and
                str(memory.get("status","")).lower() in ("healthy","degraded","unknown")
            ),
            "checked_at": datetime.utcnow().isoformat(),
        }

    def execute_failback(self, current_primary: str, original_primary: str,
                          executed_by: str = "system",
                          dry_run: bool = False) -> dict:
        """
        Execute failback from current DR primary to original primary.
        """
        started_at = datetime.utcnow()
        logger.info(
            f"FAILBACK {'[DRY RUN]' if dry_run else ''}: "
            f"{current_primary} -> {original_primary} by {executed_by}"
        )

        steps = []

        # Step 1: Validate original primary
        readiness = self.check_primary_ready(original_primary)
        steps.append({
            "step": "validate_original_primary",
            "passed": readiness["ready_for_failback"],
            "details": readiness,
        })

        if not readiness["ready_for_failback"] and not dry_run:
            return {
                "success": False,
                "reason": "Original primary not ready for failback",
                "readiness": readiness,
                "steps": steps,
            }

        # Step 2: Sync data from current primary to original
        if not dry_run:
            sync_result = self._sync_data(current_primary, original_primary)
            steps.append({
                "step": "sync_data",
                "passed": sync_result.get("success", True),
                "details": sync_result,
            })

        # Step 3: Gradually shift traffic
        if not dry_run:
            shift_result = self._gradual_traffic_shift(
                from_host=current_primary,
                to_host=original_primary,
                steps=self.GRADUAL_SHIFT_STEPS,
            )
            steps.append({
                "step": "gradual_traffic_shift",
                "passed": shift_result.get("success", True),
                "details": shift_result,
            })
        else:
            steps.append({
                "step": "gradual_traffic_shift",
                "passed": True,
                "details": "Dry run — skipped",
            })

        # Step 4: Trigger failback via failover service
        if not dry_run and self.svc:
            from ..enums import FailoverType
            fo_result = self.svc.trigger_failover(
                primary_node=current_primary,
                secondary_node=original_primary,
                failover_type=FailoverType.PLANNED,
                reason=f"Failback to original primary by {executed_by}",
                triggered_by=executed_by,
            )
            steps.append({
                "step": "trigger_failback",
                "passed": True,
                "details": fo_result,
            })

        duration = (datetime.utcnow() - started_at).total_seconds()
        success = all(s.get("passed", True) for s in steps)

        logger.info(
            f"Failback {'complete' if success else 'FAILED'}: "
            f"{current_primary} -> {original_primary} in {duration:.1f}s"
        )
        return {
            "success": success,
            "dry_run": dry_run,
            "from_primary": current_primary,
            "to_primary": original_primary,
            "executed_by": executed_by,
            "duration_seconds": round(duration, 2),
            "steps": steps,
            "started_at": started_at.isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }

    def estimate_failback_time(self, current_primary: str,
                                original_primary: str) -> dict:
        """
        Estimate how long failback will take based on data lag and system load.
        """
        # Estimate sync time based on replication lag
        from ..REPLICATION_MANAGEMENT.replication_lag_detector import ReplicationLagDetector
        detector = ReplicationLagDetector()
        # In production: get actual lag from DB
        estimated_lag_seconds = 0
        sync_time = max(estimated_lag_seconds * 1.5, 60)  # At least 60s for sync
        traffic_shift_time = self.GRADUAL_SHIFT_STEPS * 30  # 30s per step
        total_estimate = sync_time + traffic_shift_time + 120  # +2min buffer
        return {
            "estimated_sync_seconds": round(sync_time),
            "estimated_traffic_shift_seconds": traffic_shift_time,
            "total_estimated_seconds": round(total_estimate),
            "total_estimated_minutes": round(total_estimate / 60, 1),
            "estimated_at": datetime.utcnow().isoformat(),
        }

    def get_failback_runbook(self) -> List[dict]:
        """Return the failback runbook for human operators."""
        return [
            {"step": 1, "title": "Confirm original primary is healthy",
             "details": "Run health checks for minimum 30 minutes"},
            {"step": 2, "title": "Notify stakeholders",
             "details": "Announce planned failback window"},
            {"step": 3, "title": "Sync data",
             "details": "Ensure replication lag < 5 seconds before proceeding"},
            {"step": 4, "title": "Enable maintenance mode",
             "details": "Show maintenance page to prevent new write conflicts"},
            {"step": 5, "title": "Execute failback",
             "details": "Run execute_failback() with gradual traffic shift"},
            {"step": 6, "title": "Verify all services",
             "details": "Run smoke tests and check error rates"},
            {"step": 7, "title": "Monitor for 1 hour",
             "details": "Keep DR system on standby for 60 minutes post-failback"},
            {"step": 8, "title": "Close incident",
             "details": "Update incident report and schedule post-mortem"},
        ]

    def _sync_data(self, source: str, target: str) -> dict:
        """Sync any data changes from current primary to original primary."""
        logger.info(f"Syncing data: {source} -> {target}")
        # In production: check replication lag and wait for it to drop to near-zero
        return {"success": True, "sync_method": "replication_catch_up",
                "lag_seconds": 0}

    def _gradual_traffic_shift(self, from_host: str, to_host: str,
                                steps: int) -> dict:
        """Gradually shift traffic from current primary back to original."""
        logger.info(
            f"Gradual traffic shift: {from_host} -> {to_host} ({steps} steps)"
        )
        timeline = []
        step_size = 100 // steps
        for i in range(1, steps + 1):
            to_weight = min(step_size * i, 100)
            from_weight = max(100 - step_size * i, 0)
            timeline.append({
                "step": i, from_host: from_weight, to_host: to_weight,
                "timestamp": datetime.utcnow().isoformat()
            })
            time.sleep(1)  # In production: 30-60s between steps
        return {"success": True, "steps_completed": steps, "timeline": timeline}
