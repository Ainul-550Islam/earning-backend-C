"""
Health Checker — Checks health of all system components
"""
import logging
import socket
import time
from datetime import datetime
from typing import Optional

from ..enums import HealthStatus

logger = logging.getLogger(__name__)


class HealthChecker:
    """
    Checks health of:
    - Database connections
    - HTTP/HTTPS endpoints
    - TCP ports
    - Disk space
    - Memory/CPU usage
    """

    def check_tcp(self, host: str, port: int, timeout: int = 5) -> dict:
        start = time.monotonic()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                pass
            response_ms = (time.monotonic() - start) * 1000
            return {"status": HealthStatus.HEALTHY, "response_time_ms": round(response_ms, 2),
                    "host": host, "port": port}
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            response_ms = (time.monotonic() - start) * 1000
            return {"status": HealthStatus.DOWN, "error": str(e),
                    "response_time_ms": round(response_ms, 2), "host": host, "port": port}

    def check_http(self, url: str, timeout: int = 10, expected_status: int = 200) -> dict:
        import urllib.request
        import urllib.error
        start = time.monotonic()
        try:
            req = urllib.request.urlopen(url, timeout=timeout)
            response_ms = (time.monotonic() - start) * 1000
            status = HealthStatus.HEALTHY if req.status == expected_status else HealthStatus.DEGRADED
            return {"status": status, "http_status": req.status, "response_time_ms": round(response_ms, 2), "url": url}
        except Exception as e:
            response_ms = (time.monotonic() - start) * 1000
            return {"status": HealthStatus.DOWN, "error": str(e), "response_time_ms": round(response_ms, 2), "url": url}

    def check_database(self, db_url: str) -> dict:
        start = time.monotonic()
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(db_url, pool_size=1, max_overflow=0, pool_timeout=5)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            response_ms = (time.monotonic() - start) * 1000
            return {"status": HealthStatus.HEALTHY, "response_time_ms": round(response_ms, 2)}
        except Exception as e:
            return {"status": HealthStatus.DOWN, "error": str(e),
                    "response_time_ms": (time.monotonic() - start) * 1000}

    def check_disk(self, path: str = "/", warning_pct: float = 80.0, critical_pct: float = 90.0) -> dict:
        import shutil
        total, used, free = shutil.disk_usage(path)
        used_pct = (used / total) * 100
        if used_pct >= critical_pct:
            status = HealthStatus.CRITICAL
        elif used_pct >= warning_pct:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY
        return {
            "status": status,
            "path": path,
            "total_gb": round(total / 1e9, 2),
            "used_gb": round(used / 1e9, 2),
            "free_gb": round(free / 1e9, 2),
            "used_percent": round(used_pct, 2),
        }

    def check_memory(self, warning_pct: float = 85.0, critical_pct: float = 95.0) -> dict:
        try:
            import psutil
            mem = psutil.virtual_memory()
            used_pct = mem.percent
            if used_pct >= critical_pct:
                status = HealthStatus.CRITICAL
            elif used_pct >= warning_pct:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY
            return {"status": status, "used_percent": used_pct, "available_gb": round(mem.available / 1e9, 2)}
        except ImportError:
            return {"status": HealthStatus.UNKNOWN, "error": "psutil not installed"}

    def check_cpu(self, warning_pct: float = 80.0, critical_pct: float = 95.0, interval: float = 1.0) -> dict:
        try:
            import psutil
            cpu_pct = psutil.cpu_percent(interval=interval)
            if cpu_pct >= critical_pct:
                status = HealthStatus.CRITICAL
            elif cpu_pct >= warning_pct:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY
            return {"status": status, "cpu_percent": cpu_pct, "core_count": psutil.cpu_count()}
        except ImportError:
            return {"status": HealthStatus.UNKNOWN, "error": "psutil not installed"}

    def check_all(self, components: list) -> dict:
        """Check all registered components and return summary."""
        results = {}
        overall = HealthStatus.HEALTHY
        for comp in components:
            name = comp["name"]
            kind = comp.get("type", "tcp")
            if kind == "http":
                result = self.check_http(comp["url"])
            elif kind == "database":
                result = self.check_database(comp["url"])
            elif kind == "disk":
                result = self.check_disk(comp.get("path", "/"))
            elif kind == "tcp":
                result = self.check_tcp(comp["host"], comp["port"])
            else:
                result = {"status": HealthStatus.UNKNOWN}
            results[name] = result
            if result["status"] == HealthStatus.DOWN:
                overall = HealthStatus.DOWN
            elif result["status"] in (HealthStatus.CRITICAL, HealthStatus.DEGRADED):
                if overall == HealthStatus.HEALTHY:
                    overall = HealthStatus.DEGRADED
        return {"overall": overall, "checked_at": datetime.utcnow().isoformat(), "components": results}
