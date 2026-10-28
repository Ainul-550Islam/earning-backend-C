"""
utils/health_check.py – Programmatic postback system health checker.

Can be called from:
  • Management command (postback_health_check)
  • REST API endpoint (/api/postback/health/)
  • External monitoring (Datadog, Sentry, Uptime Robot)

Returns a structured HealthReport dataclass.
"""
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Dict, List, Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class HealthCheck:
    name: str
    ok: bool
    detail: str = ""
    critical: bool = False  # If True, system cannot process postbacks


@dataclass
class HealthReport:
    checks: List[HealthCheck] = field(default_factory=list)
    generated_at: Optional[object] = None

    @property
    def is_healthy(self) -> bool:
        return all(c.ok for c in self.checks if c.critical)

    @property
    def has_warnings(self) -> bool:
        return any(not c.ok for c in self.checks if not c.critical)

    def to_dict(self) -> dict:
        return {
            "healthy": self.is_healthy,
            "has_warnings": self.has_warnings,
            "generated_at": str(self.generated_at),
            "checks": [
                {
                    "name": c.name,
                    "ok": c.ok,
                    "detail": c.detail,
                    "critical": c.critical,
                }
                for c in self.checks
            ],
        }


def run_health_check(network_key: Optional[str] = None) -> HealthReport:
    """
    Run all postback health checks and return a HealthReport.
    Never raises — all exceptions are caught per-check.
    """
    report = HealthReport(generated_at=timezone.now())

    report.checks.append(_check_database())
    report.checks.append(_check_cache())
    report.checks.append(_check_active_networks(network_key))
    report.checks.append(_check_recent_failure_rate())
    report.checks.append(_check_stuck_postbacks())

    return report


def _check_database() -> HealthCheck:
    try:
        from postback.models import PostbackLog
        PostbackLog.objects.only("id").first()
        return HealthCheck(
            name="database",
            ok=True,
            detail="PostbackLog table accessible",
            critical=True,
        )
    except Exception as e:
        return HealthCheck(
            name="database",
            ok=False,
            detail=f"DB connection failed: {type(e).__name__}",
            critical=True,
        )


def _check_cache() -> HealthCheck:
    try:
        from django.core.cache import cache
        test_key = "postback:health:ping"
        cache.set(test_key, "pong", timeout=5)
        val = cache.get(test_key)
        cache.delete(test_key)
        ok = val == "pong"
        return HealthCheck(
            name="cache",
            ok=ok,
            detail="Cache read/write OK" if ok else "Cache returned wrong value",
            critical=True,  # Rate limit + nonce need cache
        )
    except Exception as e:
        return HealthCheck(
            name="cache",
            ok=False,
            detail=f"Cache error: {type(e).__name__}",
            critical=True,
        )


def _check_active_networks(network_key: Optional[str] = None) -> HealthCheck:
    try:
        from postback.models import NetworkPostbackConfig
        qs = NetworkPostbackConfig.objects.filter(status="active")
        if network_key:
            qs = qs.filter(network_key=network_key)
        count = qs.count()
        if count == 0:
            return HealthCheck(
                name="active_networks",
                ok=False,
                detail="No active NetworkPostbackConfig found — postbacks will be rejected",
                critical=False,
            )
        return HealthCheck(
            name="active_networks",
            ok=True,
            detail=f"{count} active network config(s)",
            critical=False,
        )
    except Exception as e:
        return HealthCheck(
            name="active_networks",
            ok=False,
            detail=str(e),
            critical=False,
        )


def _check_recent_failure_rate() -> HealthCheck:
    """
    Flag if >20% of last 100 postbacks are FAILED status.
    """
    try:
        from postback.models import PostbackLog
        since = timezone.now() - timedelta(hours=1)
        recent = PostbackLog.objects.filter(received_at__gte=since)
        total = recent.count()
        if total == 0:
            return HealthCheck(name="failure_rate", ok=True, detail="No recent postbacks")
        failed = recent.filter(status="failed").count()
        rate = failed / total
        ok = rate <= 0.20
        return HealthCheck(
            name="failure_rate",
            ok=ok,
            detail=f"Failure rate: {rate:.1%} ({failed}/{total} in last hour)",
            critical=False,
        )
    except Exception as e:
        return HealthCheck(name="failure_rate", ok=False, detail=str(e), critical=False)


def _check_stuck_postbacks() -> HealthCheck:
    """Flag postbacks stuck in RECEIVED state for >30 minutes."""
    try:
        from postback.models import PostbackLog
        stuck = PostbackLog.objects.filter(
            status="received",
            received_at__lt=timezone.now() - timedelta(minutes=30),
        ).count()
        ok = stuck == 0
        return HealthCheck(
            name="stuck_postbacks",
            ok=ok,
            detail=f"{stuck} postback(s) stuck in RECEIVED >30min" if stuck else "No stuck postbacks",
            critical=False,
        )
    except Exception as e:
        return HealthCheck(name="stuck_postbacks", ok=False, detail=str(e), critical=False)
