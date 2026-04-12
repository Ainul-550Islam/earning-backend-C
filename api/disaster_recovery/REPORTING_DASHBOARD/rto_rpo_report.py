"""
RTO/RPO Report — Tracks recovery time and recovery point objectives over time.
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RtoRpoReport:
    def __init__(self, db_session=None):
        self.db = db_session

    def generate(self, from_date: datetime = None, to_date: datetime = None) -> dict:
        from_date = from_date or (datetime.utcnow() - timedelta(days=90))
        to_date = to_date or datetime.utcnow()
        if not self.db:
            return {"report_type": "rto_rpo_report", "samples": 0}
        from ..sa_models import RTO_RPO_Metric
        from sqlalchemy import and_
        metrics = self.db.query(RTO_RPO_Metric).filter(
            and_(RTO_RPO_Metric.measured_at >= from_date, RTO_RPO_Metric.measured_at <= to_date)
        ).all()
        if not metrics:
            return {"report_type": "rto_rpo_report", "samples": 0,
                    "period": {"from": from_date.isoformat(), "to": to_date.isoformat()}}
        rtos = [m.rto_actual_seconds for m in metrics if m.rto_actual_seconds is not None]
        rpos = [m.rpo_actual_seconds for m in metrics if m.rpo_actual_seconds is not None]
        rto_met = sum(1 for m in metrics if m.rto_met)
        rpo_met = sum(1 for m in metrics if m.rpo_met)
        return {
            "report_type": "rto_rpo_report",
            "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
            "generated_at": datetime.utcnow().isoformat(),
            "samples": len(metrics),
            "rto": {
                "target_seconds": metrics[0].rto_target_seconds if metrics else 3600,
                "avg_actual_seconds": round(sum(rtos) / len(rtos), 2) if rtos else None,
                "min_seconds": round(min(rtos), 2) if rtos else None,
                "max_seconds": round(max(rtos), 2) if rtos else None,
                "compliance_percent": round(rto_met / len(metrics) * 100, 2),
            },
            "rpo": {
                "target_seconds": metrics[0].rpo_target_seconds if metrics else 900,
                "avg_actual_seconds": round(sum(rpos) / len(rpos), 2) if rpos else None,
                "min_seconds": round(min(rpos), 2) if rpos else None,
                "max_seconds": round(max(rpos), 2) if rpos else None,
                "compliance_percent": round(rpo_met / len(metrics) * 100, 2),
            },
        }
