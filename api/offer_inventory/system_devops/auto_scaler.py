# api/offer_inventory/system_devops/auto_scaler.py
"""
Auto Scaler Config — Load monitoring and scaling recommendations.
Works with Railway, Heroku, Kubernetes via environment variables.
"""
import logging
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)

THRESHOLDS = {
    'high'   : {'clicks_per_min': 500, 'queue_size': 1000},
    'medium' : {'clicks_per_min': 200, 'queue_size': 200},
    'low'    : {'clicks_per_min': 0,   'queue_size': 0},
}


class AutoScalerConfig:
    """Load monitoring and scaling decision support."""

    @staticmethod
    def get_current_load() -> dict:
        """Current system load metrics."""
        from api.offer_inventory.models import Click, TaskQueue
        since_1min = timezone.now() - timedelta(minutes=1)
        clicks_pm  = Click.objects.filter(created_at__gte=since_1min).count()
        queue_size = TaskQueue.objects.filter(status='pending').count()

        load_level = 'low'
        if clicks_pm >= THRESHOLDS['high']['clicks_per_min'] or queue_size >= THRESHOLDS['high']['queue_size']:
            load_level = 'high'
        elif clicks_pm >= THRESHOLDS['medium']['clicks_per_min'] or queue_size >= THRESHOLDS['medium']['queue_size']:
            load_level = 'medium'

        return {
            'clicks_per_minute': clicks_pm,
            'queue_size'       : queue_size,
            'load_level'       : load_level,
            'recommendation'   : AutoScalerConfig._recommendation(load_level),
            'checked_at'       : timezone.now().isoformat(),
        }

    @staticmethod
    def _recommendation(load_level: str) -> str:
        recs = {
            'high'  : 'Scale up: Add 2+ Celery workers, increase Redis memory.',
            'medium': 'Monitor: Consider adding 1 Celery worker.',
            'low'   : 'Current capacity is sufficient.',
        }
        return recs.get(load_level, 'Unknown load level.')

    @staticmethod
    def get_worker_stats() -> dict:
        """Celery worker status."""
        try:
            from celery import current_app
            inspector = current_app.control.inspect(timeout=3)
            active    = inspector.active() or {}
            return {
                'worker_count': len(active),
                'active_tasks': sum(len(v) for v in active.values()),
                'workers'     : list(active.keys()),
            }
        except Exception as e:
            return {'worker_count': 0, 'error': str(e)}

    @staticmethod
    def get_queue_depths() -> dict:
        """Depth of each Celery queue via Redis."""
        try:
            import redis
            from django.conf import settings
            r      = redis.from_url(getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/1'))
            queues = ['default', 'postback', 'fraud', 'analytics', 'notification', 'payout']
            return {q: r.llen(q) for q in queues}
        except Exception as e:
            logger.debug(f'Queue depth error: {e}')
            return {}

    @staticmethod
    def should_scale_up() -> bool:
        """Return True if additional workers are needed."""
        load = AutoScalerConfig.get_current_load()
        return load['load_level'] == 'high'

    @staticmethod
    def get_scaling_report() -> dict:
        """Complete scaling report for operations."""
        return {
            'load'       : AutoScalerConfig.get_current_load(),
            'workers'    : AutoScalerConfig.get_worker_stats(),
            'queues'     : AutoScalerConfig.get_queue_depths(),
            'scale_needed': AutoScalerConfig.should_scale_up(),
        }
