"""Replication Monitor — Tracks replication health and lag continuously."""
import logging
from datetime import datetime
logger = logging.getLogger(__name__)

class ReplicationMonitor:
    def __init__(self, failover_service=None, db_session=None):
        self.failover_service = failover_service
        self.db = db_session

    def check_all_replicas(self, primary: str, replicas: list) -> list:
        results = []
        for replica in replicas:
            lag = self._get_lag(primary, replica["host"])
            healthy = lag < replica.get("max_lag_seconds", 60)
            if self.failover_service:
                self.failover_service.save_replication_lag(primary, replica["host"], lag)
            results.append({"replica": replica["host"], "lag_seconds": lag, "healthy": healthy})
            if not healthy:
                logger.warning(f"Replication lag alert: {primary}->{replica['host']} = {lag}s")
        return results

    def _get_lag(self, primary: str, replica: str) -> float:
        import subprocess
        try:
            r = subprocess.run(
                ["psql", "-h", primary, "-c",
                 f"SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()));", "-t"],
                capture_output=True, text=True, timeout=5
            )
            return float(r.stdout.strip() or 0)
        except Exception:
            return 0.0
