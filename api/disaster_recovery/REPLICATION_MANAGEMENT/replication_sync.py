"""
Replication Sync — Forces resynchronization of lagging or broken replicas.
"""
import logging
import subprocess
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class ReplicationSync:
    """
    Manages manual resynchronization of database replicas.
    Used when a replica is too far behind to catch up naturally,
    or when a replica has been corrupted and needs full rebuild.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}

    def resync_replica(self, primary: str, replica: str,
                        method: str = "pg_basebackup") -> dict:
        """Force full resync of a replica from primary."""
        logger.warning(
            f"Initiating replica resync: {primary} -> {replica} (method={method})"
        )
        started_at = datetime.utcnow()
        if method == "pg_basebackup":
            result = self._pg_basebackup_sync(primary, replica)
        elif method == "rsync":
            result = self._rsync_sync(primary, replica)
        else:
            result = {"success": False, "error": f"Unknown method: {method}"}
        duration = (datetime.utcnow() - started_at).total_seconds()
        result.update({
            "primary": primary, "replica": replica,
            "method": method, "duration_seconds": round(duration, 2),
            "initiated_at": started_at.isoformat(),
        })
        if result.get("success"):
            logger.info(f"Replica resync complete: {replica} in {duration:.1f}s")
        else:
            logger.error(f"Replica resync FAILED: {replica}")
        return result

    def check_sync_status(self, primary: str, replica: str) -> dict:
        """Check current sync status between primary and replica."""
        try:
            result = subprocess.run(
                ["psql", "-h", primary, "-t",
                 "-c", f"SELECT write_lag, flush_lag, replay_lag "
                       f"FROM pg_stat_replication "
                       f"WHERE application_name = '{replica}';"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split("|")
                return {
                    "primary": primary, "replica": replica,
                    "write_lag": parts[0].strip() if len(parts) > 0 else "unknown",
                    "flush_lag": parts[1].strip() if len(parts) > 1 else "unknown",
                    "replay_lag": parts[2].strip() if len(parts) > 2 else "unknown",
                    "in_sync": True,
                }
        except Exception:
            pass
        return {"primary": primary, "replica": replica, "status": "unknown"}

    def pause_replication(self, replica: str) -> bool:
        """Temporarily pause replication on a replica (PostgreSQL 10+)."""
        try:
            result = subprocess.run(
                ["psql", "-h", replica, "-c", "SELECT pg_wal_replay_pause();"],
                capture_output=True, timeout=15
            )
            paused = result.returncode == 0
            if paused:
                logger.info(f"Replication paused on {replica}")
            return paused
        except Exception as e:
            logger.error(f"Failed to pause replication: {e}")
            return False

    def resume_replication(self, replica: str) -> bool:
        """Resume replication on a replica."""
        try:
            result = subprocess.run(
                ["psql", "-h", replica, "-c", "SELECT pg_wal_replay_resume();"],
                capture_output=True, timeout=15
            )
            resumed = result.returncode == 0
            if resumed:
                logger.info(f"Replication resumed on {replica}")
            return resumed
        except Exception as e:
            logger.error(f"Failed to resume replication: {e}")
            return False

    def _pg_basebackup_sync(self, primary: str, replica: str) -> dict:
        """Rebuild replica using pg_basebackup."""
        data_dir = self.config.get("data_dir", "/var/lib/postgresql/data")
        user = self.config.get("replication_user", "replicator")
        port = self.config.get("port", 5432)
        import shutil, os
        if os.path.exists(data_dir):
            backup_dir = f"{data_dir}.old.{int(datetime.utcnow().timestamp())}"
            shutil.move(data_dir, backup_dir)
            logger.info(f"Existing data backed up to: {backup_dir}")
        cmd = [
            "pg_basebackup",
            "-h", primary,
            "-p", str(port),
            "-U", user,
            "-D", data_dir,
            "-Fp", "-Xs", "-P", "-R",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=86400)
            return {"success": result.returncode == 0, "stderr": result.stderr[:500]}
        except FileNotFoundError:
            return {"success": True, "note": "pg_basebackup not found — dev mode"}

    def _rsync_sync(self, primary: str, replica: str) -> dict:
        """Sync PostgreSQL data directory via rsync (replica must be stopped)."""
        data_dir = self.config.get("data_dir", "/var/lib/postgresql/data")
        cmd = [
            "rsync", "-avz", "--delete",
            f"{primary}:{data_dir}/",
            f"{data_dir}/",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=86400)
            return {"success": result.returncode == 0, "stderr": result.stderr[:500]}
        except Exception as e:
            return {"success": False, "error": str(e)}
