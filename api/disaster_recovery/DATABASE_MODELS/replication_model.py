"""
Replication Model — View-layer models for replication-specific database queries.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from ..sa_models import ReplicationLag


class ReplicationLagView:
    """
    Analytics-friendly view of replication lag data with statistics and trend analysis.
    """

    def __init__(self, db_session):
        self.db = db_session

    def get_latest_lag(self, replica_host: str) -> Optional[dict]:
        """Get most recent lag for a replica."""
        from sqlalchemy import desc
        r = self.db.query(ReplicationLag).filter(
            ReplicationLag.replica_host == replica_host
        ).order_by(desc(ReplicationLag.measured_at)).first()
        if not r: return None
        return {"replica_host": r.replica_host, "lag_seconds": r.lag_seconds,
                "is_healthy": r.is_healthy, "measured_at": r.measured_at.isoformat()}

    def get_all_replicas_latest(self) -> List[dict]:
        """Get latest lag for all replicas."""
        from sqlalchemy import func
        subq = self.db.query(ReplicationLag.replica_host,
                              func.max(ReplicationLag.measured_at).label("latest")
                              ).group_by(ReplicationLag.replica_host).subquery()
        records = self.db.query(ReplicationLag).join(
            subq, (ReplicationLag.replica_host == subq.c.replica_host) &
                  (ReplicationLag.measured_at == subq.c.latest)).all()
        return [{"replica_host": r.replica_host, "lag_seconds": r.lag_seconds,
                  "is_healthy": r.is_healthy, "measured_at": r.measured_at.isoformat()} for r in records]

    def get_lag_history(self, replica_host: str, hours: int = 24) -> List[dict]:
        """Get lag history for a replica."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        records = self.db.query(ReplicationLag).filter(
            ReplicationLag.replica_host == replica_host,
            ReplicationLag.measured_at >= cutoff
        ).order_by(ReplicationLag.measured_at).all()
        return [{"lag_seconds": r.lag_seconds, "is_healthy": r.is_healthy,
                  "measured_at": r.measured_at.isoformat()} for r in records]

    def get_average_lag(self, replica_host: str, hours: int = 1) -> Optional[float]:
        history = self.get_lag_history(replica_host, hours)
        lags = [h["lag_seconds"] for h in history if h["lag_seconds"] is not None]
        return round(sum(lags)/len(lags), 3) if lags else None

    def get_lag_statistics(self, hours: int = 24) -> Dict[str, dict]:
        """Statistics for all replicas."""
        replicas = {r["replica_host"] for r in self.get_all_replicas_latest()}
        stats = {}
        for rep in replicas:
            history = self.get_lag_history(rep, hours)
            lags = [h["lag_seconds"] for h in history if h["lag_seconds"] is not None]
            if lags:
                sl = sorted(lags); n = len(sl)
                stats[rep] = {"samples": n, "current_lag": lags[-1],
                               "avg_lag_seconds": round(sum(lags)/n,3),
                               "max_lag_seconds": round(max(lags),3),
                               "p95_lag_seconds": round(sl[int(n*0.95)],3)}
        return stats

    def get_replication_summary(self) -> dict:
        all_reps = self.get_all_replicas_latest()
        if not all_reps: return {"replica_count": 0, "all_healthy": True}
        healthy = sum(1 for r in all_reps if r.get("is_healthy"))
        max_lag = max((r.get("lag_seconds",0) for r in all_reps), default=0)
        return {"replica_count": len(all_reps), "healthy_replicas": healthy,
                "unhealthy_replicas": len(all_reps)-healthy,
                "all_healthy": healthy==len(all_reps), "max_lag_seconds": max_lag}

    def record_lag(self, replica_host: str, primary_host: str, lag_seconds: float, is_healthy: bool = True) -> ReplicationLag:
        record = ReplicationLag(replica_host=replica_host, primary_host=primary_host,
                                 lag_seconds=lag_seconds, is_healthy=is_healthy,
                                 measured_at=datetime.utcnow())
        self.db.add(record); self.db.commit()
        return record

    def cleanup_old_records(self, retain_days: int = 30) -> int:
        cutoff = datetime.utcnow() - timedelta(days=retain_days)
        deleted = self.db.query(ReplicationLag).filter(ReplicationLag.measured_at < cutoff).delete()
        self.db.commit()
        return deleted
