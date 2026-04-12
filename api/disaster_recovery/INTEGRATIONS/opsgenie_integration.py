"""
OpsGenie Integration — Alert and on-call management via OpsGenie API.
"""
import logging
import json
import urllib.request
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


class OpsGenieIntegration:
    """
    OpsGenie integration for DR alert management and on-call routing.
    Supports creating alerts, closing alerts, adding notes, and escalation.
    """

    BASE_URL = "https://api.opsgenie.com/v2"

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.api_key = config.get("api_key", "") if config else ""
        self.team = config.get("team", "") if config else ""
        self.integration_name = config.get("integration_name", "DR System") if config else "DR System"

    def _request(self, method: str, endpoint: str, body: dict = None) -> dict:
        """Make an authenticated OpsGenie API request."""
        url = f"{self.BASE_URL}/{endpoint}"
        data = json.dumps(body).encode() if body else None
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"GenieKey {self.api_key}",
        }
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return {"success": True, "data": json.loads(resp.read().decode())}
        except urllib.request.HTTPError as e:
            body_str = e.read().decode()
            logger.error(f"OpsGenie API error {e.code}: {body_str[:300]}")
            return {"success": False, "status_code": e.code, "error": body_str[:300]}
        except Exception as e:
            logger.error(f"OpsGenie request failed: {e}")
            return {"success": False, "error": str(e)}

    def create_alert(self, message: str, description: str = "",
                      priority: str = "P3",
                      alias: str = None,
                      tags: List[str] = None,
                      details: dict = None) -> dict:
        """
        Create an OpsGenie alert.
        priority: P1 (critical), P2 (high), P3 (moderate), P4 (low), P5 (info)
        """
        PRIORITY_MAP = {"critical": "P1", "high": "P2", "moderate": "P3", "low": "P4"}
        priority = PRIORITY_MAP.get(priority.lower(), priority)
        body = {
            "message": message[:130],
            "description": description[:15000],
            "priority": priority,
            "source": self.integration_name,
            "tags": tags or ["dr-system"],
            "details": {**(details or {}), "created_by": "DR-System",
                        "timestamp": datetime.utcnow().isoformat()},
        }
        if alias:
            body["alias"] = alias
        if self.team:
            body["responders"] = [{"name": self.team, "type": "team"}]
        logger.warning(f"OpsGenie alert [{priority}]: {message}")
        result = self._request("POST", "alerts", body)
        if result["success"]:
            request_id = result["data"].get("requestId", "")
            logger.info(f"OpsGenie alert created: requestId={request_id}")
        return result

    def close_alert(self, identifier: str, note: str = "Resolved by DR System") -> dict:
        """Close an OpsGenie alert by its alias or ID."""
        body = {"note": note, "source": self.integration_name, "user": "DR-System"}
        result = self._request("POST", f"alerts/{identifier}/close", body)
        logger.info(f"OpsGenie alert closed: {identifier}")
        return result

    def acknowledge_alert(self, identifier: str, user: str = "DR-System",
                           note: str = "") -> dict:
        """Acknowledge an alert."""
        body = {"user": user, "note": note or f"Acknowledged by {user}",
                "source": self.integration_name}
        return self._request("POST", f"alerts/{identifier}/acknowledge", body)

    def add_note(self, identifier: str, note: str, user: str = "DR-System") -> dict:
        """Add a note to an existing alert."""
        body = {"note": note[:25000], "user": user, "source": self.integration_name}
        return self._request("POST", f"alerts/{identifier}/notes", body)

    def create_critical_alert(self, title: str, description: str,
                               affected_systems: list = None) -> dict:
        """Create a P1 critical alert with full details."""
        details = {
            "affected_systems": ", ".join(affected_systems or []),
            "escalation": "immediate",
        }
        return self.create_alert(
            message=f"[CRITICAL DR ALERT] {title}",
            description=description,
            priority="P1",
            alias=f"dr-critical-{int(datetime.utcnow().timestamp())}",
            tags=["dr-system", "critical", "on-call"],
            details=details,
        )

    def get_on_call(self, schedule_name: str = None) -> dict:
        """Get current on-call user(s)."""
        endpoint = f"schedules/{schedule_name}/on-calls" if schedule_name else "schedules/on-calls"
        return self._request("GET", endpoint)

    def escalate_alert(self, identifier: str, escalation_name: str) -> dict:
        """Escalate an alert to the next level."""
        body = {"escalation": {"name": escalation_name, "type": "escalation"},
                "user": "DR-System", "source": self.integration_name}
        return self._request("POST", f"alerts/{identifier}/escalate", body)

    def get_alert(self, identifier: str) -> dict:
        """Get details of a specific alert."""
        return self._request("GET", f"alerts/{identifier}")

    def list_open_alerts(self, query: str = "status:open AND tag:dr-system") -> dict:
        """List open DR alerts."""
        import urllib.parse
        encoded = urllib.parse.quote(query)
        return self._request("GET", f"alerts?query={encoded}&limit=20")
