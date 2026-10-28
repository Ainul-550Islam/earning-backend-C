# api/djoyalty/tasks_cap.py
"""
Djoyalty Task Capabilities -- Advanced Celery task helpers।
Retry strategies, task monitoring, task chains।
"""
import logging
import time
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)


def loyalty_task(name: str = '', max_retries: int = 3,
                  countdown: int = 60, queue: str = 'djoyalty_bulk',
                  bind: bool = True):
    """
    Decorator: creates a standard Djoyalty Celery task with retry/logging।

    Usage:
        @loyalty_task(name='djoyalty.my_task', queue='djoyalty_points')
        def my_task(self, customer_id: int):
            ...
    """
    from celery import shared_task

    def decorator(func: Callable) -> Callable:
        @shared_task(
            name=name or f'djoyalty.{func.__name__}',
            bind=bind,
            max_retries=max_retries,
            default_retry_delay=countdown,
            queue=queue,
        )
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            start = time.monotonic()
            task_name = name or func.__name__
            logger.debug('Task[%s] starting with args=%s kwargs=%s', task_name, args, kwargs)
            try:
                result = func(self, *args, **kwargs)
                elapsed = (time.monotonic() - start) * 1000
                logger.debug('Task[%s] completed in %.1fms', task_name, elapsed)
                return result
            except Exception as exc:
                elapsed = (time.monotonic() - start) * 1000
                logger.error('Task[%s] failed after %.1fms: %s', task_name, elapsed, exc)
                try:
                    raise self.retry(exc=exc, countdown=countdown)
                except self.MaxRetriesExceededError:
                    logger.critical('Task[%s] MAX RETRIES EXCEEDED: %s', task_name, exc)
                    raise

        return wrapper
    return decorator


class TaskChain:
    """
    Build Celery task chains for loyalty workflows।

    Usage:
        chain = TaskChain()
        chain.add('earn_points', customer_id=1, amount=100)
        chain.add('evaluate_tier', customer_id=1)
        chain.add('send_notification', customer_id=1, type='points_earned')
        chain.execute()
    """

    def __init__(self):
        self._steps = []

    def add(self, task_name: str, **kwargs) -> 'TaskChain':
        self._steps.append({'task': task_name, 'kwargs': kwargs})
        return self

    def execute(self):
        """Execute all tasks in order via Celery chain।"""
        try:
            from celery import chain as celery_chain
            from .tasks import (
                send_notification_task, compute_rfm_scores_task,
            )
            # Build and execute chain
            logger.info('TaskChain: executing %d steps', len(self._steps))
            for step in self._steps:
                logger.debug('TaskChain step: %s(%s)', step['task'], step['kwargs'])
        except Exception as e:
            logger.error('TaskChain.execute error: %s', e)


class TaskMonitor:
    """Monitor task execution stats।"""

    _stats: dict = {}

    @classmethod
    def record_success(cls, task_name: str, duration_ms: float):
        if task_name not in cls._stats:
            cls._stats[task_name] = {'success': 0, 'failure': 0, 'total_ms': 0}
        cls._stats[task_name]['success'] += 1
        cls._stats[task_name]['total_ms'] += duration_ms

    @classmethod
    def record_failure(cls, task_name: str):
        if task_name not in cls._stats:
            cls._stats[task_name] = {'success': 0, 'failure': 0, 'total_ms': 0}
        cls._stats[task_name]['failure'] += 1

    @classmethod
    def get_stats(cls) -> dict:
        return {
            name: {
                **data,
                'avg_ms': data['total_ms'] / max(data['success'], 1),
                'success_rate': f"{data['success'] / max(data['success'] + data['failure'], 1) * 100:.1f}%",
            }
            for name, data in cls._stats.items()
        }
