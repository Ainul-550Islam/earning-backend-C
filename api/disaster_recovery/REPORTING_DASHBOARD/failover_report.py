"""
Failover Report — Analysis of failover events, RTO metrics, and trends.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict

logger = logging.getLogger(__name__)


class FailoverReport:
    def __init__(self, db_session=None):
        self.db = db_session

    def generate(self, from_date: datetime = None, to_date: datetime = None) -> dict:
        from_date = from_date or (datetime.utcnow() - timedelta(days=90))
        to_date = to_date or datetime.utcnow()
        if not self.db:
            return {"report_type": "failover_report", "total_events": 0}
        from ..sa_models import FailoverEvent
        from ..enums import FailoverStatus
        from sqlalchemy import and_
        events = self.db.query(FailoverEvent).filter(
            and_(FailoverEvent.initiated_at >= from_date, FailoverEvent.initiated_at <= to_date)
        ).all()
        completed = [e for e in events if e.status == FailoverStatus.COMPLETED]
        rtos = [e.rto_achieved_seconds for e in completed if e.rto_achieved_seconds]
        avg_rto = sum(rtos) / len(rtos) if rtos else None
        by_type: Dict[str, int] = {}
        for event in events:
            ft = str(event.failover_type.value) if event.failover_type else "unknown"
            by_type[ft] = by_type.get(ft, 0) + 1
        return {
            "report_type": "failover_report",
            "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
            "generated_at": datetime.utcnow().isoformat(),
            "total_events": len(events),
            "completed": len(completed),
            "avg_rto_seconds": round(avg_rto, 2) if avg_rto else None,
            "min_rto_seconds": round(min(rtos), 2) if rtos else None,
            "max_rto_seconds": round(max(rtos), 2) if rtos else None,
            "by_type": by_type,
        }
