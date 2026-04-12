"""
Datadog Integration — Send DR metrics and events to Datadog for unified observability.
"""
import logging, json, urllib.request
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class DatadogIntegration:
    """
    Datadog integration for DR system observability with custom metrics,
    events, service checks, and log ingestion.
    """

    def __init__(self, api_key: str = None, config: dict = None):
        self.config = config or {}
        self.api_key = api_key or config.get("api_key","") if config else ""
        self.app_key = config.get("app_key","") if config else ""
        self.site = config.get("site","datadoghq.com") if config else "datadoghq.com"
        self.host = config.get("host_name","dr-system") if config else "dr-system"
        self.service_tags = config.get("service_tags",["service:dr-system","env:production"]) if config else []

    def _headers(self) -> dict:
        h = {"Content-Type":"application/json","DD-API-KEY": self.api_key}
        if self.app_key: h["DD-APPLICATION-KEY"] = self.app_key
        return h

    def _post(self, url: str, payload) -> dict:
        data = json.dumps(payload, default=str).encode()
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return {"success": True, "status": resp.status, "data": json.loads(resp.read().decode())}
        except urllib.request.HTTPError as e:
            body = e.read().decode()
            logger.error(f"Datadog API error {e.code}: {body[:200]}")
            return {"success": False, "status": e.code, "error": body[:200]}
        except Exception as e:
            logger.error(f"Datadog request failed: {e}")
            return {"success": False, "error": str(e)}

    def send_metric(self, name: str, value: float, metric_type: str = "gauge",
                     tags: List[str] = None, timestamp: datetime = None) -> dict:
        """Send a custom metric."""
        ts = int((timestamp or datetime.utcnow()).timestamp())
        metric_name = f"dr.{name}" if not name.startswith("dr.") else name
        payload = {"series": [{"metric": metric_name, "type": 0, "points": [[ts, value]],
                                "tags": list(self.service_tags) + (tags or []), "host": self.host}]}
        return self._post(f"https://api.{self.site}/api/v2/series", payload)

    def send_metrics(self, metrics: List[Dict]) -> dict:
        """Send multiple metrics in one call."""
        ts = int(datetime.utcnow().timestamp())
        series = [{"metric": f"dr.{m['name']}" if not m['name'].startswith("dr.") else m['name'],
                   "type": 0, "points": [[ts, m["value"]]],
                   "tags": list(self.service_tags) + m.get("tags",[]), "host": self.host}
                  for m in metrics]
        return self._post(f"https://api.{self.site}/api/v2/series", {"series": series})

    def create_event(self, title: str, text: str, alert_type: str = "info",
                      tags: List[str] = None, aggregation_key: str = None) -> dict:
        """Create a Datadog event."""
        payload = {"title": title[:100], "text": text[:4000], "alert_type": alert_type,
                   "date_happened": int(datetime.utcnow().timestamp()),
                   "tags": list(self.service_tags) + (tags or []), "host": self.host,
                   "source_type_name": "DR System"}
        if aggregation_key: payload["aggregation_key"] = aggregation_key
        return self._post(f"https://api.{self.site}/api/v1/events", payload)

    def service_check(self, check_name: str, status: int, message: str = "", tags: List[str] = None) -> dict:
        """Submit service check (0=OK,1=WARNING,2=CRITICAL,3=UNKNOWN)."""
        checks = [{"check": f"dr.{check_name}" if not check_name.startswith("dr.") else check_name,
                   "host_name": self.host, "status": status, "message": message,
                   "tags": list(self.service_tags) + (tags or []),
                   "timestamp": int(datetime.utcnow().timestamp())}]
        return self._post(f"https://api.{self.site}/api/v1/check_run", checks)

    def send_log(self, message: str, level: str = "info", service: str = "dr-system",
                  tags: List[str] = None, extra: dict = None) -> dict:
        """Send a log to Datadog Log Management."""
        log = {"ddsource": "dr-system", "ddtags": ",".join(list(self.service_tags)+(tags or [])),
               "hostname": self.host, "message": message, "service": service, "status": level,
               "timestamp": datetime.utcnow().isoformat(), **(extra or {})}
        return self._post(f"https://http-intake.logs.{self.site}/api/v2/logs", [log])

    def annotate_failover(self, failover: dict) -> dict:
        fo_type = str(failover.get("failover_type","")).upper()
        return self.create_event(
            title=f"DR {fo_type} FAILOVER: {failover.get('primary_node','')} -> {failover.get('secondary_node','')}",
            text=f"Reason: {failover.get('trigger_reason','')}\nTriggered by: {failover.get('triggered_by','')}",
            alert_type="error" if fo_type=="AUTOMATIC" else "warning",
            tags=["event_type:failover"], aggregation_key=f"failover-{failover.get('primary_node','')}")

    def annotate_backup_complete(self, backup: dict) -> dict:
        success = backup.get("status","") == "completed"
        return self.create_event(
            title=f"Backup {'Completed' if success else 'Failed'}: {backup.get('backup_type','')}",
            text=f"Size: {backup.get('source_size_bytes',0)/1e6:.1f}MB | Duration: {backup.get('duration_seconds',0):.0f}s",
            alert_type="success" if success else "error", tags=["event_type:backup"])

    def update_backup_metrics_batch(self, stats: dict) -> dict:
        return self.send_metrics([
            {"name": "backup.total_jobs", "value": stats.get("total_jobs",0)},
            {"name": "backup.completed", "value": stats.get("completed",0)},
            {"name": "backup.failed", "value": stats.get("failed",0)},
            {"name": "backup.success_rate_pct",
             "value": round(stats.get("completed",0)/max(stats.get("total_jobs",1),1)*100,2)},
            {"name": "backup.avg_duration_seconds", "value": stats.get("avg_duration_seconds",0) or 0}])

    def get_all_metrics(self) -> dict:
        return {"note": "Use generate_metrics_text or Datadog API to retrieve metric values"}
