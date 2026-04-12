"""
Restore Report — Analytics for restore operations and recovery performance.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict

logger = logging.getLogger(__name__)


class RestoreReport:
    def __init__(self, db_session=None):
        self.db = db_session

    def generate(self, from_date: datetime = None, to_date: datetime = None) -> dict:
        from_date = from_date or (datetime.utcnow() - timedelta(days=30))
        to_date = to_date or datetime.utcnow()
        if not self.db:
            return {"report_type": "restore_report", "total": 0, "message": "No DB session"}
        from ..sa_models import RestoreRequest
        from ..enums import RestoreStatus
        from sqlalchemy import and_
        requests = self.db.query(RestoreRequest).filter(
            and_(RestoreRequest.created_at >= from_date, RestoreRequest.created_at <= to_date)
        ).all()
        completed = [r for r in requests if r.status == RestoreStatus.COMPLETED]
        failed = [r for r in requests if r.status == RestoreStatus.FAILED]
        avg_duration = (
            sum(r.duration_seconds or 0 for r in completed) / len(completed)
            if completed else 0
        )
        total_bytes = sum(r.bytes_restored or 0 for r in completed)
        by_type: Dict[str, int] = {}
        for req in requests:
            rt = req.restore_type or "unknown"
            by_type[rt] = by_type.get(rt, 0) + 1
        return {
            "report_type": "restore_report",
            "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
            "generated_at": datetime.utcnow().isoformat(),
            "total_requests": len(requests),
            "completed": len(completed),
            "failed": len(failed),
            "success_rate_percent": round(len(completed) / max(len(requests), 1) * 100, 2),
            "avg_duration_seconds": round(avg_duration, 1),
            "total_bytes_restored_gb": round(total_bytes / 1e9, 3),
            "by_restore_type": by_type,
        }
