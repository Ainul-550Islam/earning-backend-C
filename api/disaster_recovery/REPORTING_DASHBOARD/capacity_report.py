"""
Capacity Report — Storage capacity planning and trend analysis.
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CapacityReport:
    def __init__(self, db_session=None):
        self.db = db_session

    def generate(self, from_date: datetime = None, to_date: datetime = None) -> dict:
        from_date = from_date or (datetime.utcnow() - timedelta(days=90))
        to_date = to_date or datetime.utcnow()
        capacity = self._get_capacity_data()
        return {
            "report_type": "capacity_report",
            "generated_at": datetime.utcnow().isoformat(),
            **capacity,
            "forecast": self._forecast_capacity(capacity),
        }

    def _get_capacity_data(self) -> dict:
        if not self.db:
            return {"total_capacity_gb": 0, "used_capacity_gb": 0, "usage_percent": 0}
        from ..sa_models import StorageLocation
        locations = self.db.query(StorageLocation).filter(StorageLocation.is_active == True).all()
        total = sum(l.total_capacity_gb or 0 for l in locations)
        used = sum(l.used_capacity_gb or 0 for l in locations)
        return {
            "total_capacity_gb": round(total, 2),
            "used_capacity_gb": round(used, 2),
            "free_capacity_gb": round(total - used, 2),
            "usage_percent": round(used / max(total, 1) * 100, 2),
            "locations": [
                {"name": l.name, "total_gb": l.total_capacity_gb or 0,
                 "used_gb": l.used_capacity_gb or 0}
                for l in locations
            ],
        }

    def _forecast_capacity(self, current: dict) -> dict:
        growth_rate = 0.1  # 10% monthly growth assumption
        used = current.get("used_capacity_gb", 0)
        total = current.get("total_capacity_gb", 1)
        months_to_full = 0
        projected_used = used
        while projected_used < total and months_to_full < 24:
            projected_used *= (1 + growth_rate)
            months_to_full += 1
        return {
            "estimated_months_to_capacity": months_to_full,
            "monthly_growth_rate_assumed": f"{growth_rate*100:.0f}%",
            "recommendation": (
                "Plan capacity expansion within 3 months"
                if months_to_full <= 3 else
                f"Capacity sufficient for approximately {months_to_full} months"
            ),
        }
