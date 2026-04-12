"""
Power Outage Handler — Responds to power failures, UPS activations, and PDU failures.
"""
import logging
import subprocess
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)


class PowerOutageHandler:
    """
    Handles power-related disaster scenarios:
    - Utility power failure: UPS activates automatically
    - Generator failure: Graceful shutdown sequence
    - PDU failure: Failover to redundant power feeds
    - Partial power loss: Route critical loads
    - Planned maintenance: Pre-scheduled power management

    Integrates with:
    - APC/Eaton UPS management (via SNMP or USB)
    - Schneider Electric DCIM
    - Intelligent PDUs
    - BMS (Building Management System)
    """

    UPS_RUNTIME_SHUTDOWN_THRESHOLD_MINUTES = 10  # Initiate graceful shutdown if < 10 min remaining

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.ups_host = config.get("ups_host", "ups.local") if config else "ups.local"
        self.ups_community = config.get("ups_snmp_community", "public") if config else "public"
        self.critical_services = config.get("critical_services", [
            "postgresql", "redis", "nginx", "dr-api"
        ]) if config else []
        self.shutdown_sequence = config.get("shutdown_sequence", [
            "dr-worker", "dr-beat", "dr-api", "nginx", "redis", "postgresql"
        ]) if config else []

    def handle(self, context: dict) -> dict:
        """Main handler for power outage events."""
        outage_type = context.get("outage_type", "utility_failure")
        logger.critical(f"POWER OUTAGE RESPONSE: {outage_type}")
        started_at = datetime.utcnow()
        steps = []

        if outage_type == "utility_failure":
            result = self._handle_utility_failure(context)
        elif outage_type == "ups_battery_low":
            result = self._handle_ups_low_battery(context)
        elif outage_type == "generator_failure":
            result = self._handle_generator_failure(context)
        elif outage_type == "pdu_failure":
            result = self._handle_pdu_failure(context)
        else:
            result = self._handle_generic_power_event(context)

        result.update({
            "disaster_type": "power_outage",
            "outage_type": outage_type,
            "initiated_at": started_at.isoformat(),
        })
        return result

    def _handle_utility_failure(self, context: dict) -> dict:
        """Primary power failure — UPS activates."""
        ups_runtime = self._get_ups_runtime_minutes()
        steps = [
            "Utility power failure detected",
            f"UPS activated — estimated runtime: {ups_runtime} minutes",
            "Alert on-call team and data center staff",
            "Check generator status and initiate start sequence",
        ]
        if ups_runtime and ups_runtime < self.UPS_RUNTIME_SHUTDOWN_THRESHOLD_MINUTES:
            steps.extend([
                f"UPS runtime < {self.UPS_RUNTIME_SHUTDOWN_THRESHOLD_MINUTES} minutes — initiating graceful shutdown",
                "Triggering region failover to DR site",
            ])
            shutdown_triggered = True
        else:
            steps.append("Monitoring UPS runtime — generator should start within 30 seconds")
            shutdown_triggered = False
        return {
            "steps": steps,
            "ups_runtime_minutes": ups_runtime,
            "shutdown_triggered": shutdown_triggered,
            "generator_status": self._check_generator_status(),
        }

    def _handle_ups_low_battery(self, context: dict) -> dict:
        """UPS battery critically low — immediate action required."""
        remaining_pct = context.get("battery_percent", 0)
        runtime = self._get_ups_runtime_minutes()
        logger.critical(
            f"UPS BATTERY CRITICAL: {remaining_pct}% remaining, "
            f"~{runtime} minutes runtime"
        )
        steps = [
            f"UPS battery at {remaining_pct}% — {runtime} minutes remaining",
            "IMMEDIATE: Trigger cross-region failover",
            "IMMEDIATE: Begin graceful shutdown sequence",
            "Alert all team members and management",
        ]
        self._initiate_graceful_shutdown()
        return {
            "steps": steps,
            "battery_percent": remaining_pct,
            "runtime_minutes": runtime,
            "shutdown_sequence_initiated": True,
            "failover_recommended": True,
        }

    def _handle_generator_failure(self, context: dict) -> dict:
        """Generator failed to start or stopped running."""
        ups_runtime = self._get_ups_runtime_minutes()
        steps = [
            "Generator failure detected",
            f"Falling back to UPS — {ups_runtime} minutes estimated runtime",
            "Alert facilities team for emergency generator repair",
            "Initiate planned failover to DR site",
            "Begin graceful shutdown of non-critical systems",
        ]
        return {
            "steps": steps,
            "ups_runtime_minutes": ups_runtime,
            "shutdown_sequence": self.shutdown_sequence,
            "failover_required": True,
        }

    def _handle_pdu_failure(self, context: dict) -> dict:
        """Power Distribution Unit failure — switch to redundant PDU."""
        failed_pdu = context.get("failed_pdu", "PDU-A")
        backup_pdu = context.get("backup_pdu", "PDU-B")
        steps = [
            f"PDU failure detected: {failed_pdu}",
            f"Switching to redundant PDU: {backup_pdu}",
            "Verify all servers powered via backup PDU",
            "Alert facilities team for PDU replacement",
            "Document affected equipment and verify no data loss",
        ]
        return {
            "steps": steps,
            "failed_pdu": failed_pdu,
            "backup_pdu": backup_pdu,
            "action": "pdu_failover",
        }

    def _handle_generic_power_event(self, context: dict) -> dict:
        """Generic power event handler."""
        steps = [
            "Power anomaly detected via UPS/PDU monitoring",
            "Check UPS status and battery level",
            "Verify generator auto-start sequence",
            "Alert on-call team",
            "Monitor for escalation to full outage",
            "Prepare for potential graceful shutdown",
        ]
        return {"steps": steps, "action": "monitoring_escalated"}

    def _initiate_graceful_shutdown(self) -> dict:
        """Execute graceful shutdown of services in correct order."""
        logger.critical("INITIATING GRACEFUL SHUTDOWN SEQUENCE")
        results = []
        for service in self.shutdown_sequence:
            try:
                result = subprocess.run(
                    ["systemctl", "stop", service],
                    capture_output=True, timeout=60
                )
                status = "stopped" if result.returncode == 0 else "error"
                logger.critical(f"  Shutdown: {service} -> {status}")
                results.append({"service": service, "status": status})
            except Exception as e:
                logger.error(f"  Shutdown error for {service}: {e}")
                results.append({"service": service, "status": "error", "error": str(e)})
        return {"shutdown_sequence": self.shutdown_sequence, "results": results}

    def _get_ups_runtime_minutes(self) -> Optional[int]:
        """Query UPS for estimated runtime remaining."""
        try:
            result = subprocess.run(
                ["snmpget", "-v1", "-c", self.ups_community, self.ups_host,
                 "1.3.6.1.2.1.33.1.2.3.0"],  # upsEstimatedMinutesRemaining OID
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split()
                if parts:
                    return int(parts[-1])
        except Exception:
            pass
        return 30  # Default assumption: 30 minutes

    def _check_generator_status(self) -> str:
        """Check if the backup generator is running."""
        gen_host = self.config.get("generator_host", "")
        if not gen_host:
            return "unknown"
        try:
            import socket
            with socket.create_connection((gen_host, 161), timeout=5):
                return "running"
        except Exception:
            return "unknown"

    def get_power_status(self) -> dict:
        """Get current power infrastructure status."""
        ups_runtime = self._get_ups_runtime_minutes()
        gen_status = self._check_generator_status()
        return {
            "ups_runtime_minutes": ups_runtime,
            "generator_status": gen_status,
            "critical_services": self.critical_services,
            "shutdown_threshold_minutes": self.UPS_RUNTIME_SHUTDOWN_THRESHOLD_MINUTES,
            "status": (
                "critical" if ups_runtime and ups_runtime < self.UPS_RUNTIME_SHUTDOWN_THRESHOLD_MINUTES
                else "warning" if gen_status != "running"
                else "healthy"
            ),
            "checked_at": datetime.utcnow().isoformat(),
        }
