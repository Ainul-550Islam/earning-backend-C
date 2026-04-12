"""
Grafana Integration — Create annotations, dashboards, and alerts in Grafana.
"""
import logging
import json
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


class GrafanaIntegration:
    """
    Grafana integration for DR monitoring dashboards.
    Supports creating annotations for DR events, updating dashboard variables,
    and triggering Grafana alerts.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.url = config.get("url", "http://localhost:3000") if config else "http://localhost:3000"
        self.api_key = config.get("api_key", "") if config else ""
        self.org_id = config.get("org_id", 1) if config else 1

    def _request(self, method: str, endpoint: str, body: dict = None) -> dict:
        """Make an authenticated Grafana API request."""
        url = f"{self.url}/api/{endpoint}"
        data = json.dumps(body).encode() if body else None
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return {"success": True, "data": json.loads(resp.read().decode())}
        except Exception as e:
            logger.error(f"Grafana API error: {e}")
            return {"success": False, "error": str(e)}

    def create_annotation(self, text: str, tags: List[str] = None,
                           dashboard_uid: str = None,
                           panel_id: int = None,
                           time_ms: int = None) -> dict:
        """Create a Grafana annotation for a DR event."""
        body = {
            "text": text,
            "tags": tags or ["dr-system"],
            "time": time_ms or int(datetime.utcnow().timestamp() * 1000),
            "timeEnd": int(datetime.utcnow().timestamp() * 1000),
        }
        if dashboard_uid:
            body["dashboardUID"] = dashboard_uid
        if panel_id:
            body["panelId"] = panel_id
        result = self._request("POST", "annotations", body)
        if result["success"]:
            logger.info(f"Grafana annotation created: {text[:50]}")
        return result

    def create_region_annotation(self, text: str, start_ms: int, end_ms: int,
                                   tags: List[str] = None,
                                   dashboard_uid: str = None) -> dict:
        """Create a time-range (region) annotation."""
        body = {
            "text": text,
            "tags": tags or ["dr-system"],
            "time": start_ms,
            "timeEnd": end_ms,
        }
        if dashboard_uid:
            body["dashboardUID"] = dashboard_uid
        return self._request("POST", "annotations", body)

    def annotate_failover(self, failover_event: dict) -> dict:
        """Create annotations for the start and end of a failover."""
        start_text = (
            f"🔴 FAILOVER START: {failover_event.get('primary_node')} → "
            f"{failover_event.get('secondary_node')}"
        )
        start_ms = int(datetime.utcnow().timestamp() * 1000)
        result = self.create_annotation(
            text=start_text,
            tags=["dr-system", "failover", "critical"],
        )
        if failover_event.get("completed_at"):
            end_ms = int(datetime.utcnow().timestamp() * 1000)
            self.create_region_annotation(
                text=f"Failover duration: {failover_event.get('duration_seconds','?')}s",
                start_ms=start_ms,
                end_ms=end_ms,
                tags=["dr-system", "failover"],
            )
        return result

    def annotate_backup(self, backup_job: dict) -> dict:
        """Annotate a backup completion on the Grafana timeline."""
        status = str(backup_job.get("status", "")).upper()
        emoji = "✅" if status == "COMPLETED" else "❌"
        text = (
            f"{emoji} Backup {status}: {backup_job.get('backup_type','')} "
            f"({(backup_job.get('source_size_bytes', 0) or 0) / 1e6:.0f} MB)"
        )
        tags = ["dr-system", "backup",
                "success" if status == "COMPLETED" else "failure"]
        return self.create_annotation(text=text, tags=tags)

    def annotate_dr_drill(self, drill: dict) -> dict:
        """Annotate a DR drill event."""
        passed = drill.get("passed", False)
        text = (
            f"{'✅' if passed else '❌'} DR Drill: {drill.get('name', '')} "
            f"({'PASSED' if passed else 'FAILED'})"
        )
        return self.create_annotation(
            text=text,
            tags=["dr-system", "drill", "passed" if passed else "failed"]
        )

    def get_dashboard(self, uid: str) -> dict:
        """Fetch a Grafana dashboard by UID."""
        return self._request("GET", f"dashboards/uid/{uid}")

    def search_dashboards(self, query: str = "dr") -> List[dict]:
        """Search for DR-related dashboards."""
        result = self._request("GET", f"search?query={urllib.parse.quote(query)}&type=dash-db")
        if result["success"]:
            return result.get("data", [])
        return []

    def get_datasource(self, name: str) -> dict:
        """Get a Grafana datasource by name."""
        return self._request("GET", f"datasources/name/{urllib.parse.quote(name)}")

    def trigger_alert_test(self, alert_rule_uid: str) -> dict:
        """Test a Grafana alert rule."""
        return self._request("POST", f"alertmanager/grafana/config/api/v1/receivers/test", {})

    def get_alerts(self, state: str = "firing") -> List[dict]:
        """Get currently firing Grafana alerts."""
        result = self._request("GET", f"alertmanager/grafana/api/v2/alerts?active=true&silenced=false")
        if result["success"]:
            alerts = result.get("data", [])
            return [a for a in alerts if a.get("status", {}).get("state") == state]
        return []

    def create_dr_dashboard(self) -> dict:
        """Create a standard DR monitoring dashboard."""
        dashboard = {
            "dashboard": {
                "id": None,
                "uid": "dr-overview",
                "title": "Disaster Recovery Overview",
                "tags": ["dr-system"],
                "timezone": "browser",
                "panels": [
                    {
                        "id": 1,
                        "title": "System Health Status",
                        "type": "stat",
                        "gridPos": {"x": 0, "y": 0, "w": 6, "h": 4},
                    },
                    {
                        "id": 2,
                        "title": "Backup Success Rate (24h)",
                        "type": "gauge",
                        "gridPos": {"x": 6, "y": 0, "w": 6, "h": 4},
                    },
                    {
                        "id": 3,
                        "title": "Replication Lag",
                        "type": "timeseries",
                        "gridPos": {"x": 0, "y": 4, "w": 12, "h": 8},
                    },
                    {
                        "id": 4,
                        "title": "RTO / RPO Achievement",
                        "type": "bargauge",
                        "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
                    },
                ],
                "refresh": "30s",
            },
            "folderId": 0,
            "overwrite": True,
        }
        result = self._request("POST", "dashboards/db", dashboard)
        if result["success"]:
            logger.info("DR dashboard created/updated in Grafana")
        return result
