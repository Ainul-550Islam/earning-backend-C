"""
Restore Audit — Audit trail for all restore operations.
"""
import logging
import json
import os
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


class RestoreAuditLog:
    """Maintains an immutable audit trail for restore operations."""

    AUDIT_FILE = "/var/log/dr/restore_audit.jsonl"

    def __init__(self, db_session=None):
        self.db = db_session
        self._buffer: List[dict] = []
        try:
            os.makedirs(os.path.dirname(self.AUDIT_FILE), exist_ok=True)
        except Exception: pass

    def log_restore_start(self, restore_id: str, restore_type: str,
                           requested_by: str, target_database: str,
                           backup_id: Optional[str] = None) -> dict:
        """Log the start of a restore operation."""
        entry = {
            "event": "restore_started",
            "restore_id": restore_id,
            "restore_type": restore_type,
            "requested_by": requested_by,
            "target_database": target_database,
            "backup_id": backup_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._write(entry)
        return entry

    def log_restore_complete(self, restore_id: str, success: bool,
                              duration_seconds: float = None,
                              error_message: str = None) -> dict:
        """Log restore completion."""
        entry = {
            "event": "restore_completed" if success else "restore_failed",
            "restore_id": restore_id,
            "success": success,
            "duration_seconds": duration_seconds,
            "error_message": error_message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._write(entry)
        return entry

    def log_restore_step(self, restore_id: str, step: str, details: dict = None) -> dict:
        """Log a step within a restore operation."""
        entry = {
            "event": "restore_step",
            "restore_id": restore_id,
            "step": step,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._write(entry)
        return entry

    def get_restore_history(self, restore_id: str = None, limit: int = 50) -> List[dict]:
        """Get restore audit history."""
        results = []
        if not os.path.exists(self.AUDIT_FILE):
            return results
        try:
            with open(self.AUDIT_FILE) as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if not restore_id or entry.get("restore_id") == restore_id:
                            results.append(entry)
                    except json.JSONDecodeError: pass
        except Exception as e:
            logger.error(f"Restore audit read error: {e}")
        return sorted(results, key=lambda x: x.get("timestamp",""), reverse=True)[:limit]

    def _write(self, entry: dict):
        """Write audit entry to file."""
        try:
            with open(self.AUDIT_FILE, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as e:
            logger.error(f"Restore audit write error: {e}")
        self._buffer.append(entry)
