"""SLA Monitor — Tracks uptime against SLA targets."""
import logging
from datetime import datetime, timedelta
logger = logging.getLogger(__name__)

class SLAMonitor:
    def __init__(self, db_session=None):
        self.db = db_session

    def calculate_uptime(self, service: str, from_date: datetime, to_date: datetime) -> dict:
        from ..repository import MonitoringRepository
        from ..enums import HealthStatus
        if not self.db:
            return {"service": service, "uptime_percent": 100.0}
        repo = MonitoringRepository(self.db)
        uptime_pct = repo.get_uptime_percent(service, from_date, to_date)
        total_minutes = (to_date - from_date).total_seconds() / 60
        downtime_minutes = total_minutes * (1 - uptime_pct / 100)
        return {"service": service, "uptime_percent": uptime_pct,
                "downtime_minutes": round(downtime_minutes, 2),
                "period_start": from_date.isoformat(), "period_end": to_date.isoformat()}

    def check_sla_breach(self, service: str, target_pct: float = 99.9) -> dict:
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        result = self.calculate_uptime(service, month_start, now)
        actual = result["uptime_percent"]
        breached = actual < target_pct
        if breached:
            logger.warning(f"SLA BREACH: {service} actual={actual}% target={target_pct}%")
        return {"service": service, "target_percent": target_pct, "actual_percent": actual,
                "breached": breached, "period": "current_month"}
