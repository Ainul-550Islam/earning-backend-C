"""
tasks/rate_limit_queue.py
Bursting and queueing mechanisms for rate limiting.
Handles traffic spikes gracefully with queue-based throttling.
"""

import logging
import time
import threading
from queue import Queue, Full, Empty
from typing import Dict, List, Optional, Callable, Any
from django.core.cache import cache
from django.utils import timezone
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class RateLimitQueue:
    """
    Queue-based rate limiting for handling traffic bursts.
    Queues excess requests and processes them when capacity allows.
    """

    def __init__(self,
                 limit_type: str,
                 base_limit: int = 100,
                 burst_limit: int = 200,
                 window_seconds: int = 3600,
                 queue_size: int = 1000):
        self.limit_type = limit_type
        self.base_limit = base_limit
        self.burst_limit = burst_limit
        self.window_seconds = window_seconds
        self.queue_size = queue_size

        # Request queue
        self.request_queue = Queue(maxsize=queue_size)

        # Processing thread
        self.processing_thread = None
        self.stop_processing = False

        # Stats
        self.processed_count = 0
        self.queued_count = 0
        self.dropped_count = 0

        # Start processing thread
        self.start_processing()

    def start_processing(self):
        """Start the queue processing thread."""
        if self.processing_thread is None or not self.processing_thread.is_alive():
            self.stop_processing = False
            self.processing_thread = threading.Thread(target=self._process_queue, daemon=True)
            self.processing_thread.start()
            logger.info(f"[RATE_LIMIT_QUEUE] Started processing thread for {self.limit_type}")

    def stop_processing(self):
        """Stop the queue processing thread."""
        self.stop_processing = True
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
            logger.info(f"[RATE_LIMIT_QUEUE] Stopped processing thread for {self.limit_type}")

    def _process_queue(self):
        """Process queued requests."""
        while not self.stop_processing:
            try:
                # Get request from queue with timeout
                request_data = self.request_queue.get(timeout=1)

                # Process the request
                self._execute_request(request_data)

                self.processed_count += 1
                self.request_queue.task_done()

            except Empty:
                continue
            except Exception as e:
                logger.error(f"[RATE_LIMIT_QUEUE] Error processing queued request: {e}")

    def _execute_request(self, request_data: Dict):
        """Execute a queued request."""
        try:
            func = request_data['func']
            args = request_data.get('args', [])
            kwargs = request_data.get('kwargs', {})

            # Execute the function
            result = func(*args, **kwargs)

            # Handle result if callback provided
            callback = request_data.get('callback')
            if callback:
                callback(result)

        except Exception as e:
            logger.error(f"[RATE_LIMIT_QUEUE] Error executing request: {e}")

    def submit_request(self,
                      func: Callable,
                      args: List = None,
                      kwargs: Dict = None,
                      callback: Callable = None,
                      priority: int = 0) -> bool:
        """
        Submit a request to the queue.

        Returns True if queued, False if queue is full.
        """
        request_data = {
            'func': func,
            'args': args or [],
            'kwargs': kwargs or {},
            'callback': callback,
            'priority': priority,
            'submitted_at': time.time(),
        }

        try:
            self.request_queue.put_nowait(request_data)
            self.queued_count += 1
            return True
        except Full:
            self.dropped_count += 1
            logger.warning(
                f"[RATE_LIMIT_QUEUE] Queue full for {self.limit_type}, "
                f"dropped request (total dropped: {self.dropped_count})"
            )
            return False

    def check_and_queue(self,
                       identifier: str,
                       func: Callable,
                       args: List = None,
                       kwargs: Dict = None,
                       callback: Callable = None) -> Dict:
        """
        Check rate limit and queue request if at capacity.

        Returns:
        {
            'allowed': bool,
            'queued': bool,
            'remaining': int,
            'queue_size': int
        }
        """
        from .middleware_rate_limit import RateLimitService

        service = RateLimitService()
        is_allowed, remaining = service.check_limit(self.limit_type, identifier)

        result = {
            'allowed': is_allowed,
            'queued': False,
            'remaining': remaining,
            'queue_size': self.request_queue.qsize(),
        }

        # If not allowed but within burst limit, try to queue
        if not is_allowed:
            # Check if we're within burst capacity
            current_usage = self.base_limit - remaining
            if current_usage < self.burst_limit:
                # Try to queue the request
                queued = self.submit_request(func, args, kwargs, callback)
                result['queued'] = queued

        return result

    def get_stats(self) -> Dict:
        """Get queue statistics."""
        return {
            'limit_type': self.limit_type,
            'queue_size': self.request_queue.qsize(),
            'max_queue_size': self.queue_size,
            'processed_count': self.processed_count,
            'queued_count': self.queued_count,
            'dropped_count': self.dropped_count,
            'processing_active': self.processing_thread and self.processing_thread.is_alive(),
            'base_limit': self.base_limit,
            'burst_limit': self.burst_limit,
            'window_seconds': self.window_seconds,
        }


class BurstRateLimiter:
    """
    Burst-aware rate limiter with queueing support.
    """

    def __init__(self):
        self.queues = {}
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='burst_limiter')

    def get_or_create_queue(self,
                           limit_type: str,
                           base_limit: int = 100,
                           burst_limit: int = 200,
                           window_seconds: int = 3600) -> RateLimitQueue:
        """Get or create a rate limit queue."""
        if limit_type not in self.queues:
            self.queues[limit_type] = RateLimitQueue(
                limit_type=limit_type,
                base_limit=base_limit,
                burst_limit=burst_limit,
                window_seconds=window_seconds
            )
        return self.queues[limit_type]

    def check_with_burst(self,
                        limit_type: str,
                        identifier: str,
                        func: Callable = None,
                        args: List = None,
                        kwargs: Dict = None,
                        callback: Callable = None) -> Dict:
        """
        Check rate limit with burst handling.

        If func is provided and request is queued, it will be executed asynchronously.
        """
        queue = self.get_or_create_queue(limit_type)

        if func:
            return queue.check_and_queue(identifier, func, args, kwargs, callback)
        else:
            # Just check without queuing
            from .middleware_rate_limit import RateLimitService
            service = RateLimitService()
            is_allowed, remaining = service.check_limit(limit_type, identifier)

            return {
                'allowed': is_allowed,
                'queued': False,
                'remaining': remaining,
                'queue_size': queue.request_queue.qsize(),
            }

    def get_all_stats(self) -> Dict[str, Dict]:
        """Get statistics for all queues."""
        return {name: queue.get_stats() for name, queue in self.queues.items()}

    def cleanup_inactive_queues(self, max_age_seconds: int = 3600):
        """Remove queues that haven't been used recently."""
        current_time = time.time()
        to_remove = []

        for name, queue in self.queues.items():
            # Check if queue has been inactive
            if hasattr(queue, '_last_activity'):
                if current_time - queue._last_activity > max_age_seconds:
                    to_remove.append(name)

        for name in to_remove:
            queue = self.queues[name]
            queue.stop_processing()
            del self.queues[name]
            logger.info(f"[BURST_LIMITER] Cleaned up inactive queue: {name}")


# Global burst rate limiter
burst_limiter = BurstRateLimiter()


def check_rate_limit_with_burst(limit_type: str,
                               identifier: str,
                               func: Callable = None,
                               args: List = None,
                               kwargs: Dict = None,
                               callback: Callable = None) -> Dict:
    """
    Convenience function for burst-aware rate limiting.
    """
    return burst_limiter.check_with_burst(
        limit_type, identifier, func, args, kwargs, callback
    )