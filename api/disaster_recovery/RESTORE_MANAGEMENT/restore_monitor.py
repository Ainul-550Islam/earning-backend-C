"""
Restore Monitor — Real-time progress monitoring for restore operations.
"""
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Callable

logger = logging.getLogger(__name__)


class RestoreProgress:
    """Tracks progress of a single restore operation."""
    def __init__(self, restore_id: str, total_bytes: int = 0):
        self.restore_id = restore_id
        self.total_bytes = total_bytes
        self.bytes_restored = 0
        self.current_step = "initializing"
        self.steps_completed = []
        self.started_at = datetime.utcnow()
        self.estimated_completion = None
        self.status = "running"
        self.error = None

    @property
    def percent_complete(self) -> float:
        if not self.total_bytes:
            return 0.0
        return round(min((self.bytes_restored / self.total_bytes) * 100, 100.0), 2)

    @property
    def elapsed_seconds(self) -> float:
        return (datetime.utcnow() - self.started_at).total_seconds()

    @property
    def throughput_mbps(self) -> float:
        elapsed = max(self.elapsed_seconds, 0.001)
        return round((self.bytes_restored / 1e6) / elapsed, 2)

    def update(self, bytes_done: int, step: str = None):
        self.bytes_restored = bytes_done
        if step:
            self.current_step = step
        if self.total_bytes and self.bytes_restored > 0:
            rate = self.bytes_restored / max(self.elapsed_seconds, 0.001)
            remaining_bytes = self.total_bytes - self.bytes_restored
            remaining_secs = remaining_bytes / max(rate, 1)
            self.estimated_completion = (
                datetime.utcnow() + timedelta(seconds=remaining_secs)
            ).isoformat()

    def complete(self):
        self.status = "completed"
        self.current_step = "completed"
        self.bytes_restored = self.total_bytes

    def fail(self, error: str):
        self.status = "failed"
        self.error = error

    def to_dict(self) -> dict:
        return {
            "restore_id": self.restore_id,
            "status": self.status,
            "current_step": self.current_step,
            "percent_complete": self.percent_complete,
            "bytes_restored": self.bytes_restored,
            "total_bytes": self.total_bytes,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "throughput_mbps": self.throughput_mbps,
            "estimated_completion": self.estimated_completion,
            "started_at": self.started_at.isoformat(),
            "error": self.error,
        }


class RestoreMonitor:
    """
    Monitors active restore operations and provides progress reporting.
    Supports callbacks for progress updates and completion events.
    """

    def __init__(self, db_session=None):
        self.db = db_session
        self._active: Dict[str, RestoreProgress] = {}
        self._history: Dict[str, dict] = {}
        self._callbacks: Dict[str, list] = {}
        self._lock = threading.Lock()

    def start_monitoring(self, restore_id: str, total_bytes: int = 0,
                          on_progress: Callable = None,
                          on_complete: Callable = None) -> RestoreProgress:
        """Register a new restore for monitoring."""
        progress = RestoreProgress(restore_id, total_bytes)
        with self._lock:
            self._active[restore_id] = progress
            self._callbacks[restore_id] = {
                "on_progress": on_progress,
                "on_complete": on_complete,
            }
        logger.info(
            f"Restore monitoring started: {restore_id} "
            f"(total={total_bytes / 1e6:.1f} MB)"
        )
        return progress

    def update_progress(self, restore_id: str, bytes_done: int, step: str = None):
        """Update progress for an active restore."""
        with self._lock:
            progress = self._active.get(restore_id)
        if not progress:
            logger.warning(f"RestoreMonitor: unknown restore_id {restore_id}")
            return
        progress.update(bytes_done, step)
        # Persist to DB if available
        if self.db:
            self._persist_progress(restore_id, progress)
        # Trigger callback
        cb = self._callbacks.get(restore_id, {})
        if cb.get("on_progress"):
            try:
                cb["on_progress"](progress.to_dict())
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    def mark_complete(self, restore_id: str, success: bool = True, error: str = None):
        """Mark a restore as complete or failed."""
        with self._lock:
            progress = self._active.pop(restore_id, None)
        if not progress:
            return
        if success:
            progress.complete()
        else:
            progress.fail(error or "Unknown error")
        final = progress.to_dict()
        self._history[restore_id] = final
        cb = self._callbacks.pop(restore_id, {})
        if cb.get("on_complete"):
            try:
                cb["on_complete"](final)
            except Exception as e:
                logger.warning(f"Completion callback error: {e}")
        logger.info(
            f"Restore {'completed' if success else 'FAILED'}: "
            f"{restore_id} in {progress.elapsed_seconds:.1f}s"
        )

    def get_progress(self, restore_id: str) -> Optional[dict]:
        """Get current progress for a restore."""
        with self._lock:
            if restore_id in self._active:
                return self._active[restore_id].to_dict()
        return self._history.get(restore_id)

    def get_all_active(self) -> list:
        """Get all currently running restores."""
        with self._lock:
            return [p.to_dict() for p in self._active.values()]

    def estimate_completion(self, restore_id: str) -> Optional[str]:
        """Get ETA for a restore."""
        with self._lock:
            progress = self._active.get(restore_id)
        return progress.estimated_completion if progress else None

    def _persist_progress(self, restore_id: str, progress: RestoreProgress):
        """Persist progress to database."""
        try:
            from ..sa_models import RestoreRequest
            from ..enums import RestoreStatus
            req = self.db.query(RestoreRequest).filter(
                RestoreRequest.id == restore_id
            ).first()
            if req:
                if not req.job_payload:
                    req.job_payload = {}
                req.job_payload["progress"] = progress.to_dict()
                self.db.commit()
        except Exception as e:
            logger.debug(f"Progress persist error: {e}")
