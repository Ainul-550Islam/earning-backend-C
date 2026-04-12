"""
Restore Scheduler — Manages scheduling and queuing of restore operations.
"""
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class RestoreScheduler:
    """
    Priority-based restore scheduler with conflict detection and background execution.
    """

    def __init__(self, db_session=None, config: dict = None, restore_service=None):
        self.db = db_session
        self.config = config or {}
        self.restore_svc = restore_service
        self._queue: List[dict] = []
        self._active: Dict[str, dict] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._max_concurrent = config.get("max_concurrent_restores", 2) if config else 2

    def schedule(self, restore_request: dict, scheduled_at: datetime = None, priority: int = 5) -> dict:
        """Schedule a restore operation."""
        import uuid
        rid = f"sched-{uuid.uuid4().hex[:8]}"
        conflict = self._check_conflict(restore_request.get("target_database",""))
        if conflict:
            raise ValueError(f"Restore conflict: {restore_request.get('target_database','')} already scheduled/running")
        entry = {"restore_id": rid, "scheduled_at": (scheduled_at or datetime.utcnow()).isoformat(),
                 "restore_type": restore_request.get("restore_type","full"),
                 "target_database": restore_request.get("target_database",""),
                 "backup_job_id": restore_request.get("backup_job_id"),
                 "point_in_time": str(restore_request.get("point_in_time","")) if restore_request.get("point_in_time") else None,
                 "created_by": restore_request.get("requested_by","system"),
                 "priority": priority, "status": "scheduled",
                 "created_at": datetime.utcnow().isoformat()}
        with self._lock:
            self._queue.append(entry)
            self._queue.sort(key=lambda r: (-r["priority"], r["scheduled_at"]))
        logger.info(f"Restore scheduled: {rid} type={entry['restore_type']} db={entry['target_database']}")
        return entry

    def schedule_pitr(self, database: str, target_time: datetime,
                      requested_by: str = "system", priority: int = 8) -> dict:
        """Schedule a PITR restore."""
        return self.schedule({"restore_type": "point_in_time", "target_database": database,
                              "point_in_time": target_time, "requested_by": requested_by}, priority=priority)

    def cancel(self, restore_id: str) -> bool:
        """Cancel a scheduled restore."""
        with self._lock:
            initial = len(self._queue)
            self._queue = [r for r in self._queue if r["restore_id"] != restore_id]
            cancelled = len(self._queue) < initial
        if cancelled: logger.info(f"Restore cancelled: {restore_id}")
        return cancelled

    def get_queue(self) -> List[dict]:
        """Get pending restores."""
        with self._lock: return list(self._queue)

    def get_active(self) -> List[dict]:
        """Get running restores."""
        with self._lock: return list(self._active.values())

    def start(self):
        """Start background scheduler."""
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="restore-scheduler")
        self._thread.start()
        logger.info("Restore scheduler started")

    def stop(self):
        """Stop scheduler."""
        self._running = False
        if self._thread: self._thread.join(timeout=10)
        logger.info("Restore scheduler stopped")

    def get_stats(self) -> dict:
        with self._lock:
            return {"queue_size": len(self._queue), "active_restores": len(self._active),
                    "max_concurrent": self._max_concurrent, "running": self._running}

    def _loop(self):
        while self._running:
            try:
                with self._lock:
                    if len(self._active) < self._max_concurrent and self._queue:
                        now = datetime.utcnow().isoformat()
                        due = next((r for r in self._queue
                                    if r["scheduled_at"] <= now and r["status"] == "scheduled"), None)
                        if due:
                            self._queue.remove(due)
                            due["status"] = "running"
                            due["started_at"] = datetime.utcnow().isoformat()
                            self._active[due["restore_id"]] = due
                            t = threading.Thread(target=self._run_restore, args=(due,), daemon=True)
                            t.start()
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
            time.sleep(10)

    def _run_restore(self, restore: dict):
        try:
            if self.restore_svc:
                self.restore_svc.execute_restore_directly(
                    restore_type=restore["restore_type"],
                    target_database=restore["target_database"],
                    backup_job_id=restore.get("backup_job_id"),
                    requested_by=restore.get("created_by","system"))
            restore["status"] = "completed"
        except Exception as e:
            restore["status"] = "failed"
            logger.error(f"Restore failed {restore['restore_id']}: {e}")
        finally:
            restore["completed_at"] = datetime.utcnow().isoformat()
            with self._lock: self._active.pop(restore["restore_id"], None)

    def _check_conflict(self, target_db: str) -> Optional[dict]:
        if not target_db: return None
        with self._lock:
            for r in self._queue:
                if r.get("target_database") == target_db: return r
            for r in self._active.values():
                if r.get("target_database") == target_db: return r
        return None
