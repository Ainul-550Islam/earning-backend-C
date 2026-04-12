"""
ELK Integration — Send DR logs and metrics to Elasticsearch/Logstash/Kibana.
"""
import logging
import json
import urllib.request
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ELKIntegration:
    """
    Elasticsearch/Logstash/Kibana integration for DR system observability.

    Sends:
    - Backup job events
    - Alert events
    - Failover events
    - System metrics
    - Audit log entries
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.elasticsearch_url = config.get("elasticsearch_url", "http://localhost:9200") if config else "http://localhost:9200"
        self.logstash_url = config.get("logstash_url", "") if config else ""
        self.index_prefix = config.get("index_prefix", "dr-system") if config else "dr-system"
        self.api_key = config.get("api_key", "") if config else ""

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"ApiKey {self.api_key}"
        return h

    def send_event(self, event_type: str, data: dict, index: str = None) -> dict:
        """Send an event to Elasticsearch."""
        index_name = index or f"{self.index_prefix}-{event_type}-{datetime.utcnow().strftime('%Y.%m')}"
        document = {
            "@timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "service": "dr-system",
            **data,
        }
        url = f"{self.elasticsearch_url}/{index_name}/_doc"
        try:
            payload = json.dumps(document, default=str).encode()
            req = urllib.request.Request(url, data=payload, headers=self._headers(), method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                return {"success": True, "id": result.get("_id", ""), "index": index_name}
        except Exception as e:
            logger.error(f"ELK send failed: {e}")
            return {"success": False, "error": str(e)}

    def bulk_send(self, events: List[dict], index: str = None) -> dict:
        """Bulk send events to Elasticsearch."""
        index_name = index or f"{self.index_prefix}-events-{datetime.utcnow().strftime('%Y.%m')}"
        lines = []
        for event in events:
            lines.append(json.dumps({"index": {"_index": index_name}}))
            lines.append(json.dumps({
                "@timestamp": datetime.utcnow().isoformat() + "Z",
                "service": "dr-system",
                **event,
            }, default=str))
        body = "\n".join(lines) + "\n"
        try:
            payload = body.encode()
            req = urllib.request.Request(
                f"{self.elasticsearch_url}/_bulk",
                data=payload, headers=self._headers(), method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
                errors = result.get("errors", False)
                return {"success": not errors, "items_sent": len(events),
                        "errors": errors, "index": index_name}
        except Exception as e:
            logger.error(f"ELK bulk send failed: {e}")
            return {"success": False, "error": str(e)}

    def send_backup_event(self, backup_job: dict) -> dict:
        """Send backup job event to ELK."""
        return self.send_event("backup", {
            "backup_id": str(backup_job.get("id", "")),
            "backup_type": backup_job.get("backup_type", ""),
            "status": backup_job.get("status", ""),
            "size_bytes": backup_job.get("source_size_bytes", 0),
            "duration_seconds": backup_job.get("duration_seconds"),
        })

    def send_alert_event(self, alert: dict) -> dict:
        """Send alert to ELK."""
        return self.send_event("alert", {
            "rule_name": alert.get("rule_name", ""),
            "severity": alert.get("severity", ""),
            "message": alert.get("message", ""),
            "metric": alert.get("metric", ""),
            "value": alert.get("value"),
            "threshold": alert.get("threshold"),
        })

    def send_failover_event(self, failover: dict) -> dict:
        """Send failover event to ELK."""
        return self.send_event("failover", {
            "failover_type": failover.get("failover_type", ""),
            "primary_node": failover.get("primary_node", ""),
            "secondary_node": failover.get("secondary_node", ""),
            "status": failover.get("status", ""),
            "rto_seconds": failover.get("rto_achieved_seconds"),
        })

    def send_metrics(self, metrics: dict) -> dict:
        """Send system metrics to ELK."""
        return self.send_event("metrics", {
            "cpu_percent": metrics.get("cpu_percent"),
            "memory_percent": metrics.get("memory_percent"),
            "disk_percent": metrics.get("disk_percent"),
            "load_avg_1m": metrics.get("load_avg_1m"),
        })

    def check_connection(self) -> dict:
        """Test Elasticsearch connection."""
        try:
            req = urllib.request.Request(
                f"{self.elasticsearch_url}/_cluster/health",
                headers=self._headers()
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                return {"connected": True, "status": data.get("status", "unknown"),
                        "cluster": data.get("cluster_name", "")}
        except Exception as e:
            return {"connected": False, "error": str(e)}
