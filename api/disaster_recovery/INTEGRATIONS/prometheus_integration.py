"""
Prometheus Integration — Expose DR metrics via HTTP /metrics endpoint.
"""
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger(__name__)


class PrometheusIntegration:
    """
    Prometheus metrics server for the DR system.
    Serves metrics at /metrics in Prometheus text format.
    """

    METRIC_DEFINITIONS = {
        "dr_backup_jobs_total": ("counter", "Total backup jobs by status"),
        "dr_replication_lag_seconds": ("gauge", "Replication lag in seconds"),
        "dr_health_check_status": ("gauge", "Component health: 1=healthy 0=down"),
        "dr_failover_events_total": ("counter", "Total failover events"),
        "dr_sla_uptime_percent": ("gauge", "SLA uptime percentage"),
        "dr_incident_open_total": ("gauge", "Open incidents by severity"),
        "dr_storage_used_bytes": ("gauge", "Storage used in bytes"),
        "dr_backup_success_rate_percent": ("gauge", "Backup success rate"),
        "dr_active_alerts_total": ("gauge", "Currently firing alerts"),
    }

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.port = config.get("port", 9091) if config else 9091
        self.push_gateway_url = config.get("push_gateway_url", "") if config else ""
        self._metrics: Dict[str, List[dict]] = {}
        self._lock = threading.Lock()
        self._server: Optional[HTTPServer] = None

    def record(self, metric_name: str, value: float, labels: dict = None):
        """Record a metric value."""
        name = f"dr_{metric_name}" if not metric_name.startswith("dr_") else metric_name
        entry = {"value": value, "labels": labels or {}, "timestamp": datetime.utcnow().isoformat()}
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = []
            existing = self._metrics[name]
            for i, m in enumerate(existing):
                if m["labels"] == (labels or {}):
                    existing[i] = entry
                    return
            existing.append(entry)

    def increment(self, metric_name: str, labels: dict = None):
        """Increment a counter."""
        name = f"dr_{metric_name}" if not metric_name.startswith("dr_") else metric_name
        with self._lock:
            for m in self._metrics.get(name, []):
                if m["labels"] == (labels or {}):
                    m["value"] += 1
                    return
            self._metrics.setdefault(name, []).append(
                {"value": 1, "labels": labels or {}, "timestamp": datetime.utcnow().isoformat()})

    def update_backup_metrics(self, stats: dict):
        self.record("dr_backup_jobs_total", stats.get("completed", 0), {"status": "completed"})
        self.record("dr_backup_jobs_total", stats.get("failed", 0), {"status": "failed"})
        if "success_rate_percent" in stats:
            self.record("dr_backup_success_rate_percent", stats["success_rate_percent"])

    def update_replication_metrics(self, statuses: List[dict]):
        for s in statuses:
            self.record("dr_replication_lag_seconds", s.get("lag_seconds", 0) or 0,
                        {"replica": s.get("replica", "unknown")})

    def update_health_metrics(self, health_data: dict):
        for name, data in health_data.get("components", {}).items():
            status = data.get("status", "")
            if hasattr(status, "value"): status = status.value
            self.record("dr_health_check_status",
                        1 if str(status).lower() == "healthy" else 0,
                        {"component": name})

    def update_incident_metrics(self, incidents: List[dict]):
        counts = {"sev1": 0, "sev2": 0, "sev3": 0, "sev4": 0}
        for i in incidents:
            sev = str(i.get("severity", "")).lower()
            if sev in counts: counts[sev] += 1
        for sev, count in counts.items():
            self.record("dr_incident_open_total", count, {"severity": sev})

    def update_storage_metrics(self, storage_data: dict):
        for backend in storage_data.get("backends", []):
            labels = {"provider": backend.get("provider", "?"), "name": backend.get("name", "?")}
            if backend.get("used_capacity_gb") is not None:
                self.record("dr_storage_used_bytes", backend["used_capacity_gb"] * 1e9, labels)

    def generate_metrics_text(self) -> str:
        """Generate Prometheus text format."""
        lines = [f"# DR System Metrics - {datetime.utcnow().isoformat()}"]
        with self._lock:
            for name, values in self._metrics.items():
                defn = self.METRIC_DEFINITIONS.get(name)
                if defn:
                    lines.append(f"# HELP {name} {defn[1]}")
                    lines.append(f"# TYPE {name} {defn[0]}")
                for m in values:
                    if m["labels"]:
                        label_str = ",".join(f'{k}="{v}"' for k, v in m["labels"].items())
                        lines.append(f"{name}{{{label_str}}} {m['value']}")
                    else:
                        lines.append(f"{name} {m['value']}")
        return "\n".join(lines) + "\n"

    def start_metrics_server(self, port: int = None) -> bool:
        """Start HTTP metrics server on background thread."""
        server_port = port or self.port
        integration = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/metrics":
                    content = integration.generate_metrics_text().encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; version=0.0.4")
                    self.send_header("Content-Length", len(content))
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    self.send_response(404)
                    self.end_headers()
            def log_message(self, *args): pass

        try:
            self._server = HTTPServer(("0.0.0.0", server_port), Handler)
            t = threading.Thread(target=self._server.serve_forever,
                                  daemon=True, name="prometheus-server")
            t.start()
            logger.info(f"Prometheus metrics server started on port {server_port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")
            return False

    def stop_metrics_server(self):
        if self._server: self._server.shutdown()

    def push_to_gateway(self, job_name: str = "dr_system") -> bool:
        if not self.push_gateway_url: return False
        try:
            import urllib.request
            content = self.generate_metrics_text().encode()
            req = urllib.request.Request(
                f"{self.push_gateway_url}/metrics/job/{job_name}",
                data=content, method="POST", headers={"Content-Type": "text/plain"})
            with urllib.request.urlopen(req, timeout=10): pass
            return True
        except Exception as e:
            logger.error(f"Push gateway error: {e}")
            return False

    def get_all_metrics(self) -> dict:
        with self._lock:
            return {name: [{"value": m["value"], "labels": m["labels"]} for m in vals]
                    for name, vals in self._metrics.items()}
