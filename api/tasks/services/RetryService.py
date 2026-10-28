"""
tasks/services/RetryService.py
Smart retry with configurable backoff strategies.
"""
import logging
from typing import Dict, Any, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class RetryService:
    """
    Determines whether a failed task should be retried,
    computes the backoff delay, and dispatches the retry.
    Falls back to the dead-letter queue when retries are exhausted.
    """

    def __init__(self):
        self._config_cache: Dict[str, Any] = {}

    # ─── Public API ───────────────────────────────────────────────────

    def handle_failure(
        self,
        task_name: str,
        task_id: str,
        exception: Exception,
        traceback_str: str = '',
        retry_count: int = 0,
        payload: dict = None,
        queue_name: str = '',
        worker_hostname: str = '',
    ) -> Dict[str, Any]:
        """
        Main entry point called from Celery's on_failure signal.
        1. Load retry config for this task.
        2. Decide if we should retry or send to DLQ.
        3. If retrying, compute delay and re-enqueue.
        4. If not, send to DeadLetterService.
        """
        config = self._get_config(task_name)
        error  = str(exception)

        # Check if this exception type should be ignored (go straight to DLQ)
        if self._is_ignored_exception(exception, config):
            logger.warning(
                f"[RETRY] {task_name} – exception in ignore list, sending to DLQ immediately"
            )
            return self._send_to_dlq(
                task_name, task_id, error, traceback_str,
                payload, 'exception', retry_count, queue_name, worker_hostname
            )

        # Check if max retries exhausted
        max_retries = config.get('max_retries', 3)
        if retry_count >= max_retries:
            logger.warning(
                f"[RETRY] {task_name} – max retries ({max_retries}) exhausted, sending to DLQ"
            )
            return self._send_to_dlq(
                task_name, task_id, error, traceback_str,
                payload, 'max_retries', retry_count, queue_name, worker_hostname
            )

        # Compute backoff delay
        next_attempt = retry_count + 1
        delay_seconds = self._compute_delay(config, next_attempt)

        # Re-enqueue via Celery
        try:
            from celery import current_app

            args   = (payload or {}).get('args', [])
            kwargs = (payload or {}).get('kwargs', {})

            current_app.send_task(
                task_name,
                args=args,
                kwargs=kwargs,
                queue=queue_name or 'default',
                countdown=delay_seconds,
                headers={'retry_count': next_attempt},
            )

            logger.info(
                f"[RETRY] {task_name} retry {next_attempt}/{max_retries} "
                f"in {delay_seconds:.1f}s"
            )
            return {
                'action': 'retried',
                'attempt': next_attempt,
                'delay_seconds': delay_seconds,
                'max_retries': max_retries,
            }

        except Exception as dispatch_err:
            logger.error(f"[ERROR] RetryService dispatch failed: {dispatch_err}")
            return self._send_to_dlq(
                task_name, task_id, error, traceback_str,
                payload, 'exception', retry_count, queue_name, worker_hostname
            )

    def should_retry(
        self,
        task_name: str,
        exception: Exception,
        retry_count: int,
    ) -> bool:
        """Quick check: should this task be retried?"""
        config      = self._get_config(task_name)
        max_retries = config.get('max_retries', 3)

        if retry_count >= max_retries:
            return False
        if self._is_ignored_exception(exception, config):
            return False
        return True

    def compute_delay(self, task_name: str, attempt: int) -> float:
        """Compute the retry delay for a given attempt number."""
        config = self._get_config(task_name)
        return self._compute_delay(config, attempt)

    def get_config(self, task_name: str) -> Dict[str, Any]:
        """Return the retry configuration for a task."""
        return self._get_config(task_name)

    # ─── Private helpers ──────────────────────────────────────────────

    def _get_config(self, task_name: str) -> Dict[str, Any]:
        """Load TaskRetryConfig from DB (with simple in-memory cache)."""
        if task_name in self._config_cache:
            return self._config_cache[task_name]

        defaults = {
            'max_retries': 3,
            'retry_backoff': 'exponential',
            'retry_delay_seconds': 60,
            'backoff_multiplier': 2.0,
            'max_retry_delay_seconds': 3600,
            'jitter': True,
            'retry_on_exceptions': [],
            'ignore_exceptions': [],
            'send_to_dlq_on_exhaustion': True,
        }

        try:
            from api.tasks.models.queue import TaskRetryConfig

            cfg = TaskRetryConfig.objects.filter(
                task_name=task_name, is_active=True
            ).first()

            if cfg:
                defaults.update({
                    'max_retries': cfg.max_retries,
                    'retry_backoff': cfg.retry_backoff,
                    'retry_delay_seconds': cfg.retry_delay_seconds,
                    'backoff_multiplier': cfg.backoff_multiplier,
                    'max_retry_delay_seconds': cfg.max_retry_delay_seconds,
                    'jitter': cfg.jitter,
                    'retry_on_exceptions': cfg.retry_on_exceptions or [],
                    'ignore_exceptions': cfg.ignore_exceptions or [],
                    'send_to_dlq_on_exhaustion': cfg.send_to_dlq_on_exhaustion,
                    '_cfg_obj': cfg,
                })
        except Exception:
            pass

        self._config_cache[task_name] = defaults
        return defaults

    def _compute_delay(self, config: Dict[str, Any], attempt: int) -> float:
        """Compute delay from config dict. Delegates to model helper if available."""
        cfg_obj = config.get('_cfg_obj')
        if cfg_obj:
            return cfg_obj.compute_delay(attempt)

        import random
        import math

        base        = float(config.get('retry_delay_seconds', 60))
        strategy    = config.get('retry_backoff', 'exponential')
        multiplier  = float(config.get('backoff_multiplier', 2.0))
        max_delay   = float(config.get('max_retry_delay_seconds', 3600))
        use_jitter  = config.get('jitter', True)

        if strategy == 'constant':
            delay = base
        elif strategy == 'linear':
            delay = base * attempt * multiplier
        elif strategy == 'fibonacci':
            a, b = 1, 1
            for _ in range(attempt - 1):
                a, b = b, a + b
            delay = base * a
        else:  # exponential
            delay = base * (multiplier ** (attempt - 1))

        delay = min(delay, max_delay)
        if use_jitter:
            delay *= 1.0 + random.uniform(-0.25, 0.25)

        return round(max(delay, 1.0), 2)

    def _is_ignored_exception(self, exception: Exception, config: Dict) -> bool:
        ignore_list = config.get('ignore_exceptions', [])
        if not ignore_list:
            return False
        exc_class_name = type(exception).__name__
        return exc_class_name in ignore_list

    def _send_to_dlq(
        self,
        task_name, task_id, error, traceback_str,
        payload, failure_reason, retry_count,
        queue_name, worker_hostname,
    ) -> Dict[str, Any]:
        from api.tasks.services.DeadLetterService import DeadLetterService

        dlq_service = DeadLetterService()
        result = dlq_service.add_to_dlq(
            task_name=task_name,
            task_id=task_id,
            error=error,
            traceback=traceback_str,
            payload=payload or {},
            failure_reason=failure_reason,
            retry_count=retry_count,
            queue_name=queue_name,
            worker_hostname=worker_hostname,
        )
        return {'action': 'dlq', 'dlq_id': result.get('dlq_id'), 'error': error}
