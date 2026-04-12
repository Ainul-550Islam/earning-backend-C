# api/offer_inventory/optimization_scale/worker_pool.py
"""Worker Pool Manager — Monitor and scale Celery worker pools."""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

QUEUE_DEPTH_ALERT = 500
QUEUE_DEPTH_SCALE = 1000


class WorkerPoolManager:
    """Celery worker pool monitoring and scaling support."""

    @staticmethod
    def get_queue_depths() -> dict:
        """Get current task count in each Celery queue via Redis."""
        try:
            import redis
            from django.conf import settings
            r      = redis.from_url(getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/1'))
            queues = ['default', 'postback', 'fraud', 'analytics', 'notification', 'payout']
            return {q: r.llen(q) for q in queues}
        except Exception as e:
            logger.error(f'Queue depth error: {e}')
            return {}

    @staticmethod
    def get_worker_stats() -> dict:
        """Active Celery worker statistics."""
        try:
            from celery import current_app
            inspector = current_app.control.inspect(timeout=3)
            active    = inspector.active() or {}
            reserved  = inspector.reserved() or {}
            return {
                'worker_count': len(active),
                'active_tasks': sum(len(v) for v in active.values()),
                'reserved_tasks': sum(len(v) for v in reserved.values()),
                'workers'     : list(active.keys()),
            }
        except Exception as e:
            return {'worker_count': 0, 'active_tasks': 0, 'error': str(e)}

    @staticmethod
    def should_scale_up() -> bool:
        """True if any queue exceeds the scale threshold."""
        depths = WorkerPoolManager.get_queue_depths()
        return any(d >= QUEUE_DEPTH_SCALE for d in depths.values())

    @staticmethod
    def get_queue_alerts() -> list:
        """Get list of queues exceeding alert threshold."""
        depths = WorkerPoolManager.get_queue_depths()
        return [
            {'queue': q, 'depth': d, 'status': 'critical' if d >= QUEUE_DEPTH_SCALE else 'warning'}
            for q, d in depths.items()
            if d >= QUEUE_DEPTH_ALERT
        ]

    @staticmethod
    def get_full_report() -> dict:
        """Complete worker pool status report."""
        depths = WorkerPoolManager.get_queue_depths()
        stats  = WorkerPoolManager.get_worker_stats()
        alerts = WorkerPoolManager.get_queue_alerts()
        return {
            'queue_depths'  : depths,
            'workers'       : stats,
            'alerts'        : alerts,
            'scale_needed'  : WorkerPoolManager.should_scale_up(),
            'total_queued'  : sum(depths.values()),
        }

    @staticmethod
    def ping_workers() -> dict:
        """Ping all Celery workers to check responsiveness."""
        try:
            from celery import current_app
            responses = current_app.control.ping(timeout=3)
            return {
                'workers_responded': len(responses),
                'all_workers'      : responses,
            }
        except Exception as e:
            return {'workers_responded': 0, 'error': str(e)}
