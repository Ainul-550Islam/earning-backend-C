# api/support/integrations/message_queue.py  — WORLD #1 (New)
"""
Message Queue — High Traffic Manager।
Support system-এর heavy operations queue করে।
Celery available থাকলে async, না থাকলে thread pool।
"""
import logging
import threading
import queue
from typing import Any, Callable, Dict, Optional
from django.utils import timezone

from .integ_constants import (
    QUEUE_SUPPORT_EVENTS, QUEUE_DISPUTE_VERIFICATION,
    QUEUE_NOTIFICATIONS, QUEUE_SLA_CHECKS,
    QUEUE_MAX_RETRIES, QUEUE_RETRY_DELAY_SECONDS,
    QUEUE_HIGH_PRIORITY, QUEUE_NORMAL_PRIORITY, QUEUE_LOW_PRIORITY,
)

logger = logging.getLogger(__name__)


class SupportMessageQueue:
    """
    Message queue for high-traffic support operations.
    
    Priority levels:
        HIGH   = urgent SLA breaches, fraud alerts
        NORMAL = ticket events, notifications  
        LOW    = analytics, audit logs
    
    Usage:
        message_queue.enqueue('support.ticket.created', {'ticket_id': '...'})
        message_queue.enqueue_with_priority(QUEUE_HIGH_PRIORITY, 'sla.breach', data)
    """

    def __init__(self):
        self._celery_available = self._check_celery()
        self._fallback_queue   = queue.PriorityQueue(maxsize=10000)
        self._worker_thread    = None
        self._stats            = {
            'enqueued':   0,
            'processed':  0,
            'failed':     0,
            'retried':    0,
        }

    def _check_celery(self) -> bool:
        try:
            from celery import current_app
            return current_app.control is not None
        except Exception:
            return False

    def enqueue(self, event_type: str, data: dict, priority: int = QUEUE_NORMAL_PRIORITY) -> bool:
        """Enqueue an event for async processing."""
        self._stats['enqueued'] += 1
        if self._celery_available:
            return self._enqueue_celery(event_type, data, priority)
        return self._enqueue_thread(event_type, data, priority)

    def enqueue_high(self, event_type: str, data: dict) -> bool:
        """Enqueue with high priority (SLA breaches, fraud alerts)."""
        return self.enqueue(event_type, data, priority=QUEUE_HIGH_PRIORITY)

    def enqueue_low(self, event_type: str, data: dict) -> bool:
        """Enqueue with low priority (analytics, logs)."""
        return self.enqueue(event_type, data, priority=QUEUE_LOW_PRIORITY)

    def _enqueue_celery(self, event_type: str, data: dict, priority: int) -> bool:
        """Enqueue via Celery for distributed processing."""
        try:
            from celery import current_app
            current_app.send_task(
                'support.tasks.process_integration_event',
                kwargs={'event_type': event_type, 'data': data},
                priority=priority,
                countdown=0 if priority >= QUEUE_HIGH_PRIORITY else QUEUE_RETRY_DELAY_SECONDS,
            )
            return True
        except Exception as e:
            logger.warning(f'Celery enqueue failed, using thread fallback: {e}')
            return self._enqueue_thread(event_type, data, priority)

    def _enqueue_thread(self, event_type: str, data: dict, priority: int) -> bool:
        """Thread-based queue fallback when Celery unavailable."""
        try:
            # Priority queue: lower number = higher priority
            item = (QUEUE_HIGH_PRIORITY - priority, {'type': event_type, 'data': data, 'retries': 0})
            self._fallback_queue.put_nowait(item)
            self._ensure_worker()
            return True
        except queue.Full:
            logger.error('Support message queue is full! Event dropped.')
            return False

    def _ensure_worker(self):
        """Start background worker thread if not running."""
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._worker_thread = threading.Thread(
                target  = self._worker_loop,
                daemon  = True,
                name    = 'SupportQueueWorker',
            )
            self._worker_thread.start()

    def _worker_loop(self):
        """Background thread that processes queued events."""
        logger.info('Support message queue worker started.')
        while True:
            try:
                _, item = self._fallback_queue.get(timeout=5)
                self._process(item)
                self._fallback_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f'Queue worker error: {e}')

    def _process(self, item: dict):
        """Process a single queued event."""
        event_type = item['type']
        data       = item['data']
        retries    = item.get('retries', 0)
        try:
            from .event_bus import event_bus
            event_bus._publish_sync(event_type, data)
            self._stats['processed'] += 1
        except Exception as e:
            logger.error(f'Queue processing failed [{event_type}]: {e}')
            self._stats['failed'] += 1
            if retries < QUEUE_MAX_RETRIES:
                item['retries'] += 1
                self._stats['retried'] += 1
                import time
                time.sleep(QUEUE_RETRY_DELAY_SECONDS)
                try:
                    self._fallback_queue.put_nowait((0, item))
                except queue.Full:
                    pass

    def get_stats(self) -> dict:
        """Queue processing statistics."""
        return {
            **self._stats,
            'queue_size':      self._fallback_queue.qsize(),
            'celery_available':self._celery_available,
            'worker_alive':    self._worker_thread.is_alive() if self._worker_thread else False,
        }

    def clear(self):
        """Clear queue — for testing."""
        while not self._fallback_queue.empty():
            try:
                self._fallback_queue.get_nowait()
            except queue.Empty:
                break


message_queue = SupportMessageQueue()