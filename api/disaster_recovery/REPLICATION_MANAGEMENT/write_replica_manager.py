"""
Write Replica Manager — Routes write operations to the current primary database node.
"""
import logging, socket, time
from datetime import datetime
from typing import Optional, List, Callable

logger = logging.getLogger(__name__)


class WriteReplicaManager:
    """
    Ensures all writes go to the current primary database.
    Handles automatic failover and failback of write routing.
    """

    def __init__(self, primary_config: dict, failover_primary_config: dict = None, config: dict = None):
        self.primary_config = primary_config
        self.failover_config = failover_primary_config
        self.config = config or {}
        self._using_failover = False
        self._failover_at: Optional[datetime] = None
        self._write_count = 0
        self._failed_write_count = 0
        self._on_failover_cbs: List[Callable] = []
        self._on_recovery_cbs: List[Callable] = []

    def get_write_target(self) -> dict:
        """Get the current write target configuration."""
        if self._using_failover and self.failover_config:
            return {**self.failover_config, "_write_target": "failover_primary",
                    "_since": self._failover_at.isoformat() if self._failover_at else None}
        return {**self.primary_config, "_write_target": "primary"}

    def get_write_url(self) -> str:
        """Get database URL for current write target."""
        t = self.get_write_target()
        return f"postgresql://{t.get('user','postgres')}:{t.get('password','')}@{t.get('host','localhost')}:{t.get('port',5432)}/{t.get('database','')}"

    def switch_to_failover(self, reason: str = "primary_unavailable", triggered_by: str = "system") -> dict:
        """Switch writes to the failover primary."""
        if not self.failover_config: return {"success": False, "error": "No failover primary configured"}
        if self._using_failover: return {"success": True, "note": "Already using failover"}
        old = self.primary_config.get("host","?")
        new = self.failover_config.get("host","?")
        logger.critical(f"WRITE TARGET SWITCH: {old} -> {new} reason={reason}")
        self._using_failover = True
        self._failover_at = datetime.utcnow()
        for cb in self._on_failover_cbs:
            try: cb({"from": old, "to": new, "reason": reason, "at": self._failover_at.isoformat()})
            except Exception as e: logger.warning(f"Failover callback error: {e}")
        return {"success": True, "old_write_target": old, "new_write_target": new,
                "reason": reason, "switched_at": self._failover_at.isoformat()}

    def switch_to_primary(self, reason: str = "primary_restored", triggered_by: str = "system") -> dict:
        """Switch writes back to original primary."""
        if not self._using_failover: return {"success": True, "note": "Already using original primary"}
        old = (self.failover_config or {}).get("host","?")
        new = self.primary_config.get("host","?")
        duration = (datetime.utcnow() - self._failover_at).total_seconds() if self._failover_at else None
        logger.info(f"WRITE FAILBACK: {old} -> {new}")
        self._using_failover = False
        self._failover_at = None
        for cb in self._on_recovery_cbs:
            try: cb({"from": old, "to": new, "reason": reason, "failover_duration_seconds": duration})
            except Exception as e: logger.warning(f"Recovery callback error: {e}")
        return {"success": True, "old_write_target": old, "new_write_target": new,
                "failover_duration_seconds": duration}

    def verify_primary_health(self) -> dict:
        """Check if current write target is healthy."""
        target = self.get_write_target()
        host = target.get("host","localhost")
        port = target.get("port",5432)
        start = time.monotonic()
        try:
            with socket.create_connection((host, port), timeout=5): pass
            return {"healthy": True, "host": host, "port": port,
                    "response_time_ms": round((time.monotonic()-start)*1000,2),
                    "write_target": target.get("_write_target","primary")}
        except Exception as e:
            return {"healthy": False, "host": host, "port": port, "error": str(e)}

    def is_using_failover(self) -> bool:
        return self._using_failover

    def get_failover_duration_seconds(self) -> Optional[float]:
        if not self._using_failover or not self._failover_at: return None
        return (datetime.utcnow() - self._failover_at).total_seconds()

    def add_on_failover_callback(self, cb: Callable): self._on_failover_cbs.append(cb)
    def add_on_recovery_callback(self, cb: Callable): self._on_recovery_cbs.append(cb)
    def record_write(self, success: bool = True):
        self._write_count += 1
        if not success: self._failed_write_count += 1

    def get_stats(self) -> dict:
        return {"current_write_target": "failover" if self._using_failover else "primary",
                "primary_host": self.primary_config.get("host","?"),
                "failover_host": (self.failover_config or {}).get("host","?"),
                "using_failover": self._using_failover,
                "failover_duration_seconds": self.get_failover_duration_seconds(),
                "total_writes": self._write_count,
                "error_rate_percent": round(self._failed_write_count/max(self._write_count,1)*100,2)}
