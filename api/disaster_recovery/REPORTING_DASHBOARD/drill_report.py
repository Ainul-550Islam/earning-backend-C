"""
Drill Report — DR drill performance analytics and compliance tracking.
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DrillReport:
    def __init__(self, db_session=None):
        self.db = db_session

    def generate(self, from_date: datetime = None, to_date: datetime = None) -> dict:
        from_date = from_date or (datetime.utcnow() - timedelta(days=365))
        to_date = to_date or datetime.utcnow()
        if not self.db:
            return {"report_type": "drill_report", "total": 0}
        from ..sa_models import RecoveryDrill
        from ..enums import DrillStatus
        from sqlalchemy import and_
        drills = self.db.query(RecoveryDrill).filter(
            and_(RecoveryDrill.scheduled_at >= from_date, RecoveryDrill.scheduled_at <= to_date)
        ).all()
        completed = [d for d in drills if d.status == DrillStatus.COMPLETED]
        passed = [d for d in completed if d.passed]
        rtos = [d.achieved_rto_seconds for d in completed if d.achieved_rto_seconds]
        return {
            "report_type": "drill_report",
            "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
            "generated_at": datetime.utcnow().isoformat(),
            "total_drills": len(drills),
            "completed": len(completed),
            "passed": len(passed),
            "pass_rate_percent": round(len(passed) / max(len(completed), 1) * 100, 1),
            "avg_rto_seconds": round(sum(rtos) / len(rtos), 1) if rtos else None,
        }
