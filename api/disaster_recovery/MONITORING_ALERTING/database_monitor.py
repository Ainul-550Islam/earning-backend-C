"""Database Monitor — Monitors PostgreSQL/MySQL health and performance."""
import logging
from datetime import datetime
logger = logging.getLogger(__name__)

class DatabaseMonitor:
    def __init__(self, db_url: str):
        self.db_url = db_url

    def collect(self) -> dict:
        metrics = {"timestamp": datetime.utcnow().isoformat()}
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(self.db_url, pool_size=1, pool_timeout=5)
            with engine.connect() as conn:
                # Connection count
                r = conn.execute(text("SELECT count(*) FROM pg_stat_activity;"))
                metrics["active_connections"] = r.scalar()
                # DB size
                r = conn.execute(text("SELECT pg_database_size(current_database());"))
                metrics["db_size_bytes"] = r.scalar()
                # Replication lag
                r = conn.execute(text("SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()));"))
                lag = r.scalar()
                metrics["replication_lag_seconds"] = float(lag) if lag else 0.0
                metrics["status"] = "healthy"
        except Exception as e:
            metrics["status"] = "error"
            metrics["error"] = str(e)
        return metrics
