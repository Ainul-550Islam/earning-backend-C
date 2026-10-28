# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Distributed Lock
tasks/distributed_lock.py  (NEW FILE)

Prevents concurrent execution of critical Celery tasks across multiple
worker processes using Django's cache backend as the lock store.

Works with any Django cache backend: Redis (recommended), Memcached, or DB.

Usage:
    from .distributed_lock import DistributedLock

    # Context manager (recommended)
    with DistributedLock("aging-processor", timeout=600):
        run_expensive_task()

    # Non-blocking check
    lock = DistributedLock("aging-processor")
    if lock.acquire(blocking=False):
        try:
            run_expensive_task()
        finally:
            lock.release()
"""

import logging
import time
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger("ainul.webhooks.tasks")


class LockNotAcquired(Exception):
    """Raised when a non-blocking lock acquisition fails."""


class DistributedLock:
    """
    Distributed mutual-exclusion lock backed by Django cache.

    Args:
        name:    Unique lock identifier (e.g. "aging-processor")
        timeout: Seconds the lock is held before auto-expiry (safety valve)
    """

    PREFIX = "webhook_lock:"

    def __init__(self, name: str, timeout: int = 300):
        self.name     = name
        self.key      = f"{self.PREFIX}{name}"
        self.timeout  = timeout
        self._held    = False

    # ── Public interface ──────────────────────────────────────────────────────

    def acquire(self, blocking: bool = True, max_wait: Optional[int] = None) -> bool:
        """
        Acquire the lock.

        Args:
            blocking:  Wait until available (True) or fail immediately (False).
            max_wait:  Maximum seconds to wait when blocking=True.

        Returns:
            True if lock acquired; False otherwise (non-blocking only).
        """
        if self._held:
            return True  # Re-entrance guard — already owned by this object

        start = time.monotonic()

        while True:
            # cache.add() is atomic: sets key only if it doesn't exist
            if cache.add(self.key, "1", self.timeout):
                self._held = True
                logger.debug("[Lock] Acquired: %s (timeout=%ds)", self.key, self.timeout)
                return True

            if not blocking:
                logger.debug("[Lock] Unavailable (non-blocking): %s", self.key)
                return False

            elapsed = time.monotonic() - start
            if max_wait is not None and elapsed >= max_wait:
                logger.warning("[Lock] Timed out after %.1fs waiting for: %s", elapsed, self.key)
                return False

            time.sleep(0.2)   # poll every 200 ms

    def release(self):
        """Release the lock unconditionally."""
        if self._held:
            cache.delete(self.key)
            self._held = False
            logger.debug("[Lock] Released: %s", self.key)

    def is_locked(self) -> bool:
        """Return True if any process currently holds this lock."""
        return cache.get(self.key) is not None

    # ── Context-manager interface ─────────────────────────────────────────────

    def __enter__(self) -> "DistributedLock":
        if not self.acquire(blocking=True):
            raise LockNotAcquired(f"Could not acquire lock: {self.name}")
        return self

    def __exit__(self, *_):
        self.release()
        return False   # Don't suppress exceptions

    def __repr__(self) -> str:
        state = "held" if self._held else "free"
        return f"<DistributedLock name={self.name!r} state={state}>"
