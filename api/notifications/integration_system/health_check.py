# integration_system/health_check.py
"""Health Check — Service health monitoring for all integrations and dependencies."""
import logging, threading, time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone
from .integ_constants import HealthStatus, CacheKeys, CacheTTL, ExternalServices
logger = logging.getLogger(__name__)

class ServiceHealth:
    def __init__(self, name: str):
        self.name = name
        self.status = HealthStatus.UNKNOWN
        self.last_checked = None
        self.last_success = None
        self.consecutive_failures = 0
        self.response_time_ms = 0
        self.details: Dict = {}

    def to_dict(self) -> Dict:
        return {
            "service": self.name, "status": self.status.value,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "consecutive_failures": self.consecutive_failures,
            "response_time_ms": round(self.response_time_ms, 2), "details": self.details,
        }


class HealthCheckService:
    """Monitors health of all integrated services."""

    CACHE_TTL = 30  # seconds

    def __init__(self):
        self._health: Dict[str, ServiceHealth] = {}
        self._lock = threading.Lock()
        self._init_default_services()

    def _init_default_services(self):
        services = ["database", "redis", "celery", "fcm", "sendgrid",
                    "twilio", "shoho_sms", "bkash", "nagad", "notifications_app"]
        for s in services:
            self._health[s] = ServiceHealth(s)

    def check(self, service: str) -> ServiceHealth:
        """Run health check for a specific service."""
        cache_key = f"health:{service}"
        cached = cache.get(cache_key)
        if cached:
            h = self._health.setdefault(service, ServiceHealth(service))
            h.status = HealthStatus(cached)
            return h

        h = self._health.setdefault(service, ServiceHealth(service))
        start = time.monotonic()

        try:
            status = self._run_check(service)
            h.response_time_ms = (time.monotonic() - start) * 1000
            h.status = status
            h.last_checked = timezone.now()
            if status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED):
                h.last_success = h.last_checked
                h.consecutive_failures = 0
            else:
                h.consecutive_failures += 1
        except Exception as exc:
            h.status = HealthStatus.UNHEALTHY
            h.consecutive_failures += 1
            h.details["error"] = str(exc)

        cache.set(cache_key, h.status.value, self.CACHE_TTL)
        return h

    def _run_check(self, service: str) -> HealthStatus:
        if service == "database":
            from django.db import connection
            connection.ensure_connection()
            return HealthStatus.HEALTHY
        elif service == "redis":
            from django.core.cache import cache
            cache.set("_health_ping", "1", 5)
            return HealthStatus.HEALTHY if cache.get("_health_ping") else HealthStatus.UNHEALTHY
        elif service == "celery":
            try:
                from celery import current_app
                current_app.control.inspect(timeout=2).ping()
                return HealthStatus.HEALTHY
            except Exception:
                return HealthStatus.DEGRADED
        elif service == "fcm":
            from notifications.services.providers.FCMProvider import fcm_provider
            return HealthStatus.HEALTHY if fcm_provider.is_available() else HealthStatus.UNKNOWN
        elif service == "sendgrid":
            from notifications.services.providers.SendGridProvider import sendgrid_provider
            return HealthStatus.HEALTHY if sendgrid_provider.is_available() else HealthStatus.UNKNOWN
        elif service == "twilio":
            from notifications.services.providers.TwilioProvider import twilio_provider
            return HealthStatus.HEALTHY if twilio_provider.is_available() else HealthStatus.UNKNOWN
        elif service == "shoho_sms":
            from notifications.services.providers.ShohoSMSProvider import shoho_sms_provider
            return HealthStatus.HEALTHY if shoho_sms_provider.is_available() else HealthStatus.UNKNOWN
        elif service == "notifications_app":
            from notifications.models import Notification
            Notification.objects.first()
            return HealthStatus.HEALTHY
        return HealthStatus.UNKNOWN

    def check_all(self) -> Dict[str, ServiceHealth]:
        for service in list(self._health.keys()):
            try:
                self.check(service)
            except Exception as exc:
                logger.warning(f"HealthCheck.check_all {service}: {exc}")
        return self._health

    def get_summary(self) -> Dict:
        from collections import Counter
        statuses = [h.status.value for h in self._health.values()]
        counts = Counter(statuses)
        all_healthy = counts.get("healthy", 0) == len(self._health)
        return {
            "overall": "healthy" if all_healthy else ("degraded" if not counts.get("unhealthy") else "unhealthy"),
            "services": {k: v.to_dict() for k, v in self._health.items()},
            "counts": dict(counts),
            "checked_at": timezone.now().isoformat(),
        }

    def is_healthy(self, service: str) -> bool:
        return self.check(service).status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)


health_checker = HealthCheckService()
