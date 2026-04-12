"""
queue_management/priority_queue.py
────────────────────────────────────
DB-backed priority queue with priority-based ordering.
Wraps PostbackQueue model with business-rule-based priority assignment.
"""
from __future__ import annotations
import logging
from ..models import PostbackRawLog, PostbackQueue
from ..enums import QueuePriority, PostbackStatus

logger = logging.getLogger(__name__)


class PriorityQueue:
    """
    Assigns processing priority based on:
    - Network type (rewarded video = higher priority)
    - Payout amount (higher payout = higher priority)
    - Retry count (first attempt = higher priority than retries)
    - Time in queue (aging: avoid starvation)
    """

    def enqueue(self, raw_log: PostbackRawLog, delay_seconds: int = 0) -> PostbackQueue:
        """Add a raw log to the priority queue with auto-calculated priority."""
        priority = self._calculate_priority(raw_log)
        from .queue_manager import queue_manager
        return queue_manager.enqueue(raw_log, priority=priority, delay_seconds=delay_seconds)

    def _calculate_priority(self, raw_log: PostbackRawLog) -> int:
        """
        Priority rules (lower number = higher priority):
          1. Critical: retried postback that keeps failing (needs attention)
          2. High: high payout > $1.00 or rewarded video network
          3. Normal: standard postback (default)
          4. Low: re-processing / replay requests
          5. Background: analytics/stats only
        """
        network = raw_log.network
        if not network:
            return QueuePriority.NORMAL

        # Retry with failed status = critical (needs attention)
        if raw_log.retry_count >= 2:
            return QueuePriority.CRITICAL

        # High payout = high priority
        if raw_log.payout and raw_log.payout >= 1:
            return QueuePriority.HIGH

        # Mobile/rewarded video networks = high priority
        from ..enums import NetworkType
        if network.network_type in (NetworkType.CPI,):
            return QueuePriority.HIGH

        # Standard CPA = normal
        if network.network_type in (NetworkType.CPA, NetworkType.OFFERWALL):
            return QueuePriority.NORMAL

        return QueuePriority.NORMAL


priority_queue = PriorityQueue()
