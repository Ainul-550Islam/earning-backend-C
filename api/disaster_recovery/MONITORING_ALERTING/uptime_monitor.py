"""Uptime Monitor — Continuously monitors service availability."""
import logging, time, threading
from datetime import datetime
logger = logging.getLogger(__name__)

class UptimeMonitor:
    def __init__(self, services: list, check_interval: int = 60, db_session=None):
        self.services = services
        self.interval = check_interval
        self.db = db_session
        self._running = False

    def check_service(self, service: dict) -> dict:
        from ..FAILOVER_MANAGEMENT.health_checker import HealthChecker
        checker = HealthChecker()
        kind = service.get("type", "http")
        if kind == "http":
            return checker.check_http(service["url"])
        return checker.check_tcp(service["host"], service["port"])

    def start(self):
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()
        logger.info(f"Uptime monitor started for {len(self.services)} services")

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            for svc in self.services:
                try:
                    result = self.check_service(svc)
                    if self.db:
                        from ..repository import MonitoringRepository
                        from ..enums import HealthStatus
                        repo = MonitoringRepository(self.db)
                        repo.save_health_check({"component_name": svc["name"],
                                                "component_type": svc.get("type","http"),
                                                "status": result.get("status", HealthStatus.UNKNOWN),
                                                "response_time_ms": result.get("response_time_ms")})
                except Exception as e:
                    logger.error(f"Uptime check error for {svc.get('name')}: {e}")
            time.sleep(self.interval)
