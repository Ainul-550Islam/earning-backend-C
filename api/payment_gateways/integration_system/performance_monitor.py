# api/payment_gateways/integration_system/performance_monitor.py
# Performance monitoring for all integration operations

import time
import functools
import logging
from typing import Callable, Any
from django.core.cache import cache

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """
    Monitors performance of all integration operations.

    Tracks:
        - Handler execution time per event type
        - Gateway API response times
        - Queue depths and processing rates
        - Error rates per module
        - SLA compliance (e.g., deposit credited < 5s)

    Exposes:
        - /api/payment/status/ — public status page
        - /api/payment/admin-overview/ — admin metrics
    """

    CACHE_PREFIX = 'perf_mon'
    WINDOW       = 3600  # 1-hour rolling window

    def record(self, operation: str, duration_ms: int,
                success: bool = True, module: str = ''):
        """Record an operation's performance."""
        # Store in Redis as sorted set (timestamp + duration)
        cache_key = f'{self.CACHE_PREFIX}:{operation}'
        entry = {
            'duration_ms': duration_ms,
            'success':     success,
            'module':      module,
            'timestamp':   time.time(),
        }
        try:
            from django_redis import get_redis_connection
            import json
            conn = get_redis_connection('default')
            conn.rpush(cache_key, json.dumps(entry))
            conn.ltrim(cache_key, -1000, -1)  # Keep last 1000 entries
            conn.expire(cache_key, self.WINDOW)
        except Exception:
            # Fallback to simple cache
            existing = cache.get(cache_key, [])
            existing.append(entry)
            cache.set(cache_key, existing[-100:], self.WINDOW)

    def get_stats(self, operation: str) -> dict:
        """Get performance statistics for an operation."""
        cache_key = f'{self.CACHE_PREFIX}:{operation}'
        entries   = []

        try:
            from django_redis import get_redis_connection
            import json
            conn    = get_redis_connection('default')
            raw     = conn.lrange(cache_key, 0, -1)
            entries = [json.loads(r) for r in raw if r]
        except Exception:
            entries = cache.get(cache_key, [])

        if not entries:
            return {'operation': operation, 'count': 0}

        durations     = [e['duration_ms'] for e in entries]
        success_count = sum(1 for e in entries if e.get('success', True))

        return {
            'operation':    operation,
            'count':        len(entries),
            'success_rate': round(success_count / len(entries) * 100, 1),
            'avg_ms':       round(sum(durations) / len(durations), 1),
            'min_ms':       min(durations),
            'max_ms':       max(durations),
            'p95_ms':       sorted(durations)[int(len(durations) * 0.95)],
            'error_count':  len(entries) - success_count,
        }

    def get_all_stats(self) -> dict:
        """Get performance stats for all tracked operations."""
        operations = [
            'deposit.completed', 'withdrawal.processed', 'conversion.approved',
            'webhook.received', 'fraud.check', 'gateway.health',
            'wallet.credit', 'notification.send', 'postback.fire',
        ]
        return {op: self.get_stats(op) for op in operations}

    def check_sla(self) -> dict:
        """
        Check SLA compliance.

        SLA targets:
            - Deposit credited: < 30 seconds
            - Withdrawal processed: < 24 hours
            - Webhook verified: < 2 seconds
            - Fraud check: < 500ms
        """
        SLA_TARGETS = {
            'deposit.completed':    {'max_ms': 30000, 'label': 'Deposit credited'},
            'webhook.received':     {'max_ms': 2000,  'label': 'Webhook processed'},
            'fraud.check':          {'max_ms': 500,   'label': 'Fraud check'},
        }
        results = {}
        for op, target in SLA_TARGETS.items():
            stats = self.get_stats(op)
            avg   = stats.get('avg_ms', 0)
            p95   = stats.get('p95_ms', 0)
            results[op] = {
                'label':          target['label'],
                'target_ms':      target['max_ms'],
                'avg_ms':         avg,
                'p95_ms':         p95,
                'sla_met':        p95 <= target['max_ms'],
            }
        return results


def monitor(operation: str, module: str = ''):
    """
    Decorator to auto-record performance of any function.

    Usage:
        @monitor('deposit.completed', module='wallet')
        def credit_deposit(user, amount, ...):
            ...
    """
    perf = PerformanceMonitor()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start   = time.time()
            success = True
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration_ms = int((time.time() - start) * 1000)
                perf.record(operation, duration_ms, success, module)
                if duration_ms > 5000:
                    logger.warning(f'SLOW: {operation} took {duration_ms}ms')
        return wrapper
    return decorator
