"""
Cost Report — Backup storage cost analysis and optimization recommendations.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict

logger = logging.getLogger(__name__)


class CostReport:
    # Approximate pricing per GB/month (USD)
    STORAGE_COSTS = {
        "aws_s3": {"standard": 0.023, "standard_ia": 0.0125, "glacier": 0.004, "glacier_ir": 0.01},
        "azure_blob": {"hot": 0.018, "cool": 0.01, "archive": 0.00099},
        "gcp": {"standard": 0.020, "nearline": 0.010, "coldline": 0.004, "archive": 0.0012},
        "local": {"default": 0.001},
    }

    def __init__(self, db_session=None):
        self.db = db_session

    def generate(self, from_date: datetime = None, to_date: datetime = None) -> dict:
        from_date = from_date or (datetime.utcnow() - timedelta(days=30))
        to_date = to_date or datetime.utcnow()
        costs = self._calculate_costs()
        return {
            "report_type": "cost_report",
            "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
            "generated_at": datetime.utcnow().isoformat(),
            **costs,
            "recommendations": self._generate_recommendations(costs),
        }

    def _calculate_costs(self) -> dict:
        if not self.db:
            return {"estimated_monthly_cost_usd": 0.0, "storage_breakdown": {}}
        from ..sa_models import StorageLocation, BackupJob
        from ..enums import BackupStatus
        locations = self.db.query(StorageLocation).filter(StorageLocation.is_active == True).all()
        storage_breakdown: Dict[str, dict] = {}
        total_cost = 0.0
        for loc in locations:
            provider = str(loc.provider.value) if loc.provider else "unknown"
            size_gb = loc.used_capacity_gb or 0
            rate = self.STORAGE_COSTS.get(provider, {}).get("standard", 0.02)
            monthly_cost = size_gb * rate
            storage_breakdown[loc.name] = {
                "provider": provider,
                "size_gb": size_gb,
                "rate_per_gb": rate,
                "monthly_cost_usd": round(monthly_cost, 4),
            }
            total_cost += monthly_cost
        return {
            "estimated_monthly_cost_usd": round(total_cost, 2),
            "estimated_annual_cost_usd": round(total_cost * 12, 2),
            "storage_breakdown": storage_breakdown,
        }

    def _generate_recommendations(self, costs: dict) -> list:
        recs = []
        total = costs.get("estimated_monthly_cost_usd", 0)
        if total > 1000:
            recs.append("Consider moving older backups to Glacier/Archive tier to reduce costs by 80%")
        recs.append("Enable compression to reduce backup storage by 40-60%")
        recs.append("Review retention policies — delete backups older than compliance minimum")
        return recs
