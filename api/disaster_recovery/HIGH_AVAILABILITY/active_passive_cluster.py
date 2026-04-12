"""
Active-Passive Cluster — One active node, others on standby
"""
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ActivePassiveCluster:
    """
    Manages an active-passive HA cluster:
    - One PRIMARY node handles all traffic
    - STANDBY nodes are ready to take over
    - Automatic promotion of standby on primary failure
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._primary: Optional[dict] = None
        self._standbys: List[dict] = []
        self._lock = threading.RLock()
        self._failover_history: List[dict] = []

    def set_primary(self, node_id: str, host: str, port: int,
                    zone: str = "default") -> dict:
        with self._lock:
            node = {"id": node_id, "host": host, "port": port,
                    "zone": zone, "status": "active",
                    "promoted_at": datetime.utcnow().isoformat()}
            self._primary = node
            logger.info(f"Active-Passive: PRIMARY set to {node_id} ({host}:{port})")
            return node

    def add_standby(self, node_id: str, host: str, port: int,
                    priority: int = 100, zone: str = "default") -> dict:
        """
        priority: higher = promoted first (0=lowest, 200=highest).
        """
        with self._lock:
            node = {"id": node_id, "host": host, "port": port,
                    "priority": priority, "zone": zone,
                    "status": "standby", "replication_lag_seconds": 0.0,
                    "added_at": datetime.utcnow().isoformat()}
            self._standbys.append(node)
            self._standbys.sort(key=lambda n: n["priority"], reverse=True)
            logger.info(f"Active-Passive: STANDBY added {node_id} priority={priority}")
            return node

    def remove_node(self, node_id: str):
        with self._lock:
            if self._primary and self._primary["id"] == node_id:
                logger.warning(f"Removing PRIMARY node {node_id}")
                self._primary = None
            else:
                self._standbys = [s for s in self._standbys if s["id"] != node_id]

    def promote_standby(self, reason: str = "manual", standby_id: str = None) -> Optional[dict]:
        """
        Promote the highest-priority standby to primary.
        If standby_id is given, promote that specific standby.
        """
        with self._lock:
            if not self._standbys:
                logger.error("Active-Passive: no standby nodes to promote!")
                return None

            if standby_id:
                candidate = next((s for s in self._standbys if s["id"] == standby_id), None)
                if not candidate:
                    logger.error(f"Standby {standby_id} not found")
                    return None
            else:
                candidate = self._standbys[0]   # highest priority

            old_primary = self._primary
            self._standbys.remove(candidate)
            # Demote old primary to standby (if it still exists)
            if old_primary:
                old_primary["status"] = "standby"
                old_primary["priority"] = 50
                self._standbys.append(old_primary)
                self._standbys.sort(key=lambda n: n["priority"], reverse=True)

            candidate["status"] = "active"
            candidate["promoted_at"] = datetime.utcnow().isoformat()
            candidate["promoted_reason"] = reason
            self._primary = candidate

            event = {
                "timestamp": datetime.utcnow().isoformat(),
                "old_primary": old_primary["id"] if old_primary else None,
                "new_primary": candidate["id"],
                "reason": reason,
            }
            self._failover_history.append(event)
            logger.critical(
                f"Active-Passive PROMOTION: {old_primary['id'] if old_primary else 'none'} "
                f"-> {candidate['id']} (reason={reason})"
            )
            return candidate

    def get_primary(self) -> Optional[dict]:
        return self._primary

    def get_best_standby(self) -> Optional[dict]:
        return self._standbys[0] if self._standbys else None

    def update_replication_lag(self, standby_id: str, lag_seconds: float):
        with self._lock:
            for s in self._standbys:
                if s["id"] == standby_id:
                    s["replication_lag_seconds"] = lag_seconds

    def get_cluster_status(self) -> dict:
        with self._lock:
            return {
                "mode": "active_passive",
                "primary": self._primary,
                "standbys": self._standbys,
                "standby_count": len(self._standbys),
                "is_healthy": self._primary is not None,
                "has_standbys": len(self._standbys) > 0,
                "failover_count": len(self._failover_history),
                "last_failover": self._failover_history[-1] if self._failover_history else None,
            }

    def get_failover_history(self) -> List[dict]:
        return list(self._failover_history)
