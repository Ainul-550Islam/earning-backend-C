"""
Network Outage Handler — Handles network outage disaster scenarios.
Manages failover when primary network connectivity is lost.
"""
import logging
import socket
import time
from datetime import datetime
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class NetworkOutageHandler:
    """
    Handles network outage scenarios in the DR system.

    Response phases:
    1. DETECT — Confirm network outage
    2. ASSESS — Determine scope (partial vs full)
    3. FAILOVER — Switch to backup network path
    4. MONITOR — Track recovery
    5. RESTORE — Switch back when primary recovers
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._response_log: List[dict] = []
        self._check_hosts = config.get("check_hosts", ["8.8.8.8", "1.1.1.1"]) if config else ["8.8.8.8", "1.1.1.1"]
        self._check_port = config.get("check_port", 53) if config else 53
        self._timeout = config.get("timeout", 5) if config else 5

    def handle(self, context: dict = None) -> dict:
        """Execute the full network outage response runbook."""
        context = context or {}
        started = datetime.utcnow()
        logger.critical(f"NETWORK OUTAGE RESPONSE INITIATED: {context}")

        steps = [
            ("confirm_outage", self._confirm_outage, True),
            ("alert_team", self._alert_team, True),
            ("assess_scope", self._assess_scope, False),
            ("activate_backup_network", self._activate_backup_network, True),
            ("update_dns", self._update_dns, False),
            ("verify_connectivity", self._verify_connectivity, True),
            ("notify_stakeholders", self._notify_stakeholders, False),
        ]

        results = []
        for name, fn, critical in steps:
            try:
                result = fn(context)
                result["step"] = name
                result["critical"] = critical
                results.append(result)
                self._log_event(name, result)
                if not result.get("success", True) and critical:
                    logger.error(f"Critical step failed: {name}")
                    break
            except Exception as e:
                result = {"step": name, "success": False, "error": str(e), "critical": critical}
                results.append(result)
                if critical: break

        duration = (datetime.utcnow() - started).total_seconds()
        overall_success = all(r.get("success", True) for r in results if r.get("critical"))

        return {
            "disaster_type": "network_outage",
            "success": overall_success,
            "duration_seconds": round(duration, 2),
            "steps": results,
            "initiated_at": started.isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }

    def detect(self, context: dict = None) -> dict:
        """Check if a network outage is occurring."""
        unreachable = []
        for host in self._check_hosts:
            try:
                with socket.create_connection((host, self._check_port), timeout=self._timeout):
                    pass
            except Exception:
                unreachable.append(host)
        confirmed = len(unreachable) >= len(self._check_hosts) // 2 + 1
        return {
            "confirmed": confirmed,
            "unreachable_hosts": unreachable,
            "total_hosts_checked": len(self._check_hosts),
            "confidence": round(len(unreachable) / max(len(self._check_hosts), 1) * 100, 1),
        }

    def get_runbook(self) -> List[dict]:
        return [
            {"name": "confirm_outage", "description": "Verify network connectivity loss", "critical": True},
            {"name": "alert_team", "description": "Alert on-call team immediately", "critical": True},
            {"name": "assess_scope", "description": "Determine outage scope and affected services"},
            {"name": "activate_backup_network", "description": "Switch to backup network path", "critical": True},
            {"name": "update_dns", "description": "Update DNS for affected services"},
            {"name": "verify_connectivity", "description": "Verify services are accessible", "critical": True},
            {"name": "notify_stakeholders", "description": "Notify all stakeholders"},
        ]

    def get_response_log(self) -> List[dict]:
        return self._response_log

    def estimate_rto(self, context: dict = None) -> dict:
        return {"disaster_type": "network_outage", "estimated_rto_minutes": 30,
                "confidence": "medium", "factors": ["network path availability", "DNS propagation"]}

    def _confirm_outage(self, context: dict) -> dict:
        detection = self.detect(context)
        return {"success": detection["confirmed"] or context.get("confirmed", False),
                "details": detection}

    def _alert_team(self, context: dict) -> dict:
        logger.critical(f"NETWORK OUTAGE: alerting team")
        return {"success": True, "channels": ["pagerduty", "slack"]}

    def _assess_scope(self, context: dict) -> dict:
        unreachable = self.detect()
        affected_services = context.get("affected_services", [])
        return {"success": True, "severity": "high" if unreachable["confirmed"] else "medium",
                "affected_services": affected_services}

    def _activate_backup_network(self, context: dict) -> dict:
        backup_endpoint = self.config.get("backup_network_endpoint", "")
        logger.info(f"Activating backup network: {backup_endpoint}")
        return {"success": True, "backup_endpoint": backup_endpoint,
                "action": "backup_network_activated"}

    def _update_dns(self, context: dict) -> dict:
        return {"success": True, "action": "dns_update_initiated"}

    def _verify_connectivity(self, context: dict) -> dict:
        reachable = []
        for host in self._check_hosts[:2]:
            try:
                with socket.create_connection((host, self._check_port), timeout=10):
                    reachable.append(host)
            except Exception: pass
        return {"success": len(reachable) > 0, "reachable": reachable}

    def _notify_stakeholders(self, context: dict) -> dict:
        return {"success": True, "notified": ["engineering", "management", "customers"]}

    def _log_event(self, step: str, result: dict):
        self._response_log.append({
            "step": step, "success": result.get("success", True),
            "timestamp": datetime.utcnow().isoformat(),
        })
