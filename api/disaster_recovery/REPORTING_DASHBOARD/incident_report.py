"""
Incident Report — DR incident analytics and post-mortem tracking.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict

logger = logging.getLogger(__name__)


class IncidentReport:
    def __init__(self, db_session=None):
        self.db = db_session

    def generate(self, from_date: datetime = None, to_date: datetime = None) -> dict:
        from_date = from_date or (datetime.utcnow() - timedelta(days=90))
        to_date = to_date or datetime.utcnow()
        if not self.db:
            return {"report_type": "incident_report", "total": 0}
        from ..sa_models import IncidentReport as IncidentModel
        from ..enums import IncidentStatus, IncidentSeverity
        from sqlalchemy import and_
        incidents = self.db.query(IncidentModel).filter(
            and_(IncidentModel.started_at >= from_date, IncidentModel.started_at <= to_date)
        ).all()
        resolved = [i for i in incidents if i.status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED)]
        by_severity: Dict[str, int] = {}
        for inc in incidents:
            sev = str(inc.severity.value) if inc.severity else "unknown"
            by_severity[sev] = by_severity.get(sev, 0) + 1
        durations = [i.duration_minutes for i in resolved if i.duration_minutes]
        mttr = sum(durations) / len(durations) if durations else None
        return {
            "report_type": "incident_report",
            "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
            "generated_at": datetime.utcnow().isoformat(),
            "total_incidents": len(incidents),
            "resolved": len(resolved),
            "unresolved": len(incidents) - len(resolved),
            "mttr_minutes": round(mttr, 1) if mttr else None,
            "by_severity": by_severity,
        }
