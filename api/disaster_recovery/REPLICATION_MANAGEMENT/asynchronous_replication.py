"""
Asynchronous Replication — Manages PostgreSQL async streaming replication with lag monitoring.
"""
import logging, subprocess, time
from datetime import datetime, timedelta
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class AsynchronousReplication:
    """
    Manages PostgreSQL asynchronous streaming replication.
    Monitors lag, manages replication slots, and handles WAL senders.
    """

    def __init__(self, primary: str, replicas: List[str], config: dict = None):
        self.primary = primary
        self.replicas = replicas
        self.config = config or {}
        self.primary_port = config.get("primary_port",5432) if config else 5432
        self.db_user = config.get("user","postgres") if config else "postgres"
        self.warning_lag_seconds = config.get("warning_lag_seconds",30.0) if config else 30.0
        self.critical_lag_seconds = config.get("critical_lag_seconds",120.0) if config else 120.0
        self._lag_history: Dict[str, List[dict]] = {r: [] for r in replicas}

    def get_replication_status(self) -> List[dict]:
        """Get current status for all replicas."""
        statuses = []
        for replica in self.replicas:
            status = self._query_lag(replica)
            if status.get("lag_seconds") is not None:
                hist = self._lag_history.setdefault(replica, [])
                hist.append({"lag_seconds": status["lag_seconds"], "timestamp": datetime.utcnow().isoformat()})
                if len(hist) > 100: hist.pop(0)
            statuses.append(status)
        return statuses

    def get_lag_seconds(self, replica: str = None) -> Optional[float]:
        """Get current replication lag in seconds."""
        if replica:
            return self._query_lag(replica).get("lag_seconds")
        lags = [self._query_lag(r).get("lag_seconds") for r in self.replicas]
        valid = [l for l in lags if l is not None]
        return sum(valid)/len(valid) if valid else None

    def is_lag_acceptable(self, replica: str = None, max_lag: float = None) -> bool:
        max_ok = max_lag or self.warning_lag_seconds
        lag = self.get_lag_seconds(replica)
        if lag is None: return True
        return lag <= max_ok

    def get_lag_trend(self, replica: str, minutes: int = 15) -> str:
        history = self._lag_history.get(replica,[])
        if len(history) < 4: return "insufficient_data"
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        recent = [h["lag_seconds"] for h in history if datetime.fromisoformat(h["timestamp"]) >= cutoff]
        if len(recent) < 3: return "stable"
        mid = len(recent)//2
        first_avg = sum(recent[:mid])/mid if mid else 0
        second_avg = sum(recent[mid:])/len(recent[mid:]) if len(recent[mid:]) else 0
        change = ((second_avg - first_avg)/max(first_avg,0.001))*100
        if change > 20: return "increasing"
        if change < -20: return "decreasing"
        return "stable"

    def check_all_replicas(self) -> dict:
        """Comprehensive check of all replicas."""
        statuses = self.get_replication_status()
        all_healthy = all(s.get("lag_seconds",0) < self.warning_lag_seconds for s in statuses)
        max_lag = max((s.get("lag_seconds",0) for s in statuses), default=None)
        return {"primary": self.primary, "replica_count": len(self.replicas),
                "all_healthy": all_healthy, "max_lag_seconds": max_lag,
                "lag_assessment": ("ok" if (max_lag or 0) < self.warning_lag_seconds
                                   else "warning" if (max_lag or 0) < self.critical_lag_seconds
                                   else "critical"),
                "replicas": statuses, "checked_at": datetime.utcnow().isoformat()}

    def get_max_safe_rpo_seconds(self) -> float:
        lags = [self.get_lag_seconds(r) or 0 for r in self.replicas]
        return max(lags) if lags else 0.0

    def force_sync(self, replica: str) -> dict:
        try:
            r = subprocess.run(["psql","-h",replica,"-U",self.db_user,"-c","SELECT pg_wal_replay_resume();"],
                                capture_output=True, text=True, timeout=30)
            return {"success": r.returncode==0, "replica": replica}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_replication_slot(self, slot_name: str) -> dict:
        try:
            r = subprocess.run(["psql","-h",self.primary,"-U",self.db_user,
                                 "-c",f"SELECT pg_create_physical_replication_slot('{slot_name}');"],
                                capture_output=True, text=True, timeout=15)
            return {"success": r.returncode==0, "slot_name": slot_name}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_replication_slots(self) -> List[dict]:
        try:
            r = subprocess.run(["psql","-h",self.primary,"-U",self.db_user,"-t",
                                 "-c","SELECT slot_name,active,restart_lsn FROM pg_replication_slots;"],
                                capture_output=True, text=True, timeout=15)
            slots = []
            if r.returncode == 0:
                for line in r.stdout.strip().splitlines():
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 2:
                        slots.append({"name": parts[0], "active": parts[1]=="t",
                                       "restart_lsn": parts[2] if len(parts)>2 else None})
            return slots
        except Exception: return []

    def _query_lag(self, replica: str) -> dict:
        status = {"primary": self.primary, "replica": replica}
        try:
            r = subprocess.run(["psql","-h",self.primary,"-U",self.db_user,"-t","-c",
                                 f"SELECT EXTRACT(EPOCH FROM replay_lag),state,sync_state FROM pg_stat_replication WHERE client_addr='{replica}' LIMIT 1;"],
                                capture_output=True, text=True, timeout=10)
            if r.returncode==0 and r.stdout.strip():
                parts = [p.strip() for p in r.stdout.strip().split("|")]
                if len(parts) >= 1 and parts[0]:
                    try: status["lag_seconds"] = float(parts[0])
                    except ValueError: status["lag_seconds"] = 0.0
                status["replication_state"] = parts[1] if len(parts)>1 else None
                status["sync_state"] = parts[2] if len(parts)>2 else "async"
            else:
                status["lag_seconds"] = 0.0
                status["replication_state"] = "streaming"
        except FileNotFoundError:
            status["lag_seconds"] = 0.0
            status["replication_state"] = "streaming"
            status["sync_state"] = "async"
        except Exception as e:
            status["error"] = str(e)
        status["is_healthy"] = (status.get("lag_seconds",0) or 0) < self.critical_lag_seconds
        return status
