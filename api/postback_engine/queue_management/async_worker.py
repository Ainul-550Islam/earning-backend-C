"""
queue_management/async_worker.py
──────────────────────────────────
Async worker coordinator for postback processing.
Manages Celery worker health, concurrency, and graceful shutdown.
Provides worker-level metrics and monitoring hooks.
"""
from __future__ import annotations
import logging
import os
import socket
import time
import uuid
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

_WORKER_HEARTBEAT_KEY = "pe:worker:{worker_id}:heartbeat"
_WORKER_REGISTRY_KEY  = "pe:workers:active"
_HEARTBEAT_TTL        = 30   # seconds — worker considered dead if no heartbeat
_HEARTBEAT_INTERVAL   = 10   # seconds between heartbeats


class AsyncWorker:
    """
    Worker lifecycle manager for postback processing.

    Each Celery worker registers itself, sends periodic heartbeats,
    and deregisters on shutdown. The coordinator uses this to detect
    dead workers and release their locks.
    """

    def __init__(self):
        self.worker_id = self._generate_worker_id()
        self._running = False

    def register(self) -> str:
        """Register this worker in Redis. Returns worker_id."""
        info = {
            "worker_id": self.worker_id,
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "started_at": timezone.now().isoformat(),
            "status": "idle",
        }
        try:
            heartbeat_key = _WORKER_HEARTBEAT_KEY.format(worker_id=self.worker_id)
            cache.set(heartbeat_key, info, timeout=_HEARTBEAT_TTL)
            # Add to active workers set
            client = self._get_client()
            if client:
                import json
                client.sadd(_WORKER_REGISTRY_KEY, self.worker_id)
        except Exception as exc:
            logger.warning("AsyncWorker.register failed: %s", exc)
        logger.info("Worker registered: %s", self.worker_id)
        return self.worker_id

    def heartbeat(self, status: str = "processing") -> None:
        """Send heartbeat to keep worker registration alive."""
        try:
            heartbeat_key = _WORKER_HEARTBEAT_KEY.format(worker_id=self.worker_id)
            current = cache.get(heartbeat_key) or {}
            current.update({
                "last_heartbeat": timezone.now().isoformat(),
                "status": status,
            })
            cache.set(heartbeat_key, current, timeout=_HEARTBEAT_TTL)
        except Exception as exc:
            logger.debug("AsyncWorker.heartbeat failed: %s", exc)

    def deregister(self) -> None:
        """Deregister worker on shutdown."""
        try:
            cache.delete(_WORKER_HEARTBEAT_KEY.format(worker_id=self.worker_id))
            client = self._get_client()
            if client:
                client.srem(_WORKER_REGISTRY_KEY, self.worker_id)
        except Exception as exc:
            logger.warning("AsyncWorker.deregister failed: %s", exc)
        logger.info("Worker deregistered: %s", self.worker_id)

    def get_active_workers(self) -> list:
        """Return list of active worker IDs."""
        try:
            client = self._get_client()
            if not client:
                return []
            worker_ids = client.smembers(_WORKER_REGISTRY_KEY)
            active = []
            for wid in worker_ids:
                wid_str = wid.decode() if isinstance(wid, bytes) else wid
                info = cache.get(_WORKER_HEARTBEAT_KEY.format(worker_id=wid_str))
                if info:
                    active.append(info)
                else:
                    # Dead worker — remove from registry
                    client.srem(_WORKER_REGISTRY_KEY, wid)
            return active
        except Exception as exc:
            logger.warning("AsyncWorker.get_active_workers failed: %s", exc)
            return []

    def get_worker_count(self) -> int:
        """Return count of active workers."""
        return len(self.get_active_workers())

    def process_queue(self, batch_size: int = 10) -> dict:
        """
        Main processing loop for a single batch.
        Called by Celery task. Sends heartbeat + processes items.
        """
        self.heartbeat(status="processing")
        from .batch_processor import batch_processor
        result = batch_processor.process_batch(
            worker_id=self.worker_id,
            batch_size=batch_size,
        )
        self.heartbeat(status="idle")
        return result

    def get_metrics(self) -> dict:
        """Return worker and queue metrics for monitoring."""
        from .queue_manager import queue_manager
        from ..models import PostbackRawLog
        from ..enums import PostbackStatus
        return {
            "worker_id": self.worker_id,
            "active_workers": self.get_worker_count(),
            "queue_depth": queue_manager.get_stats(),
            "pending_postbacks": PostbackRawLog.objects.filter(
                status=PostbackStatus.RECEIVED
            ).count(),
            "failed_postbacks": PostbackRawLog.objects.filter(
                status=PostbackStatus.FAILED
            ).count(),
            "timestamp": timezone.now().isoformat(),
        }

    @staticmethod
    def _generate_worker_id() -> str:
        hostname = socket.gethostname()
        pid = os.getpid()
        short_id = str(uuid.uuid4())[:8]
        return f"{hostname}-{pid}-{short_id}"

    @staticmethod
    def _get_client():
        try:
            return cache.client.get_client()
        except Exception:
            return None


# Module-level singleton (one per process)
async_worker = AsyncWorker()
